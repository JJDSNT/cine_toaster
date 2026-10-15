"""C7 step 6 (CT-0080): time operations and tracks drawn by GL as the reference draws them -- one semantics."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import numpy as np

from cine_toaster.compositing.gl import gl_unavailable_reason, renderer_for
from cine_toaster.compositing.reference import evaluate

W, H, FPS = 64, 36, 10
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def plate(count: int = 40) -> np.ndarray:
    """Every frame its own: a texture rolled one pixel a frame, its red raised by its number."""

    rng = np.random.default_rng(3)
    base = rng.random((H, W, 3)).astype(np.float32) * 0.7
    frames = np.zeros((count, H, W, 4), np.float32)
    for index in range(count):
        frames[index, ..., :3] = np.roll(base, index, axis=1)
        frames[index, ..., 0] += index / 100
        frames[index, ..., 3] = 1.0
    return frames


def graph(nodes: dict, output: str = "out", ports: dict | None = None) -> dict:
    return {"ports": ports if ports is not None else {"plate": "picture"}, "output": output, "nodes": nodes}


def keys(name: str, points: list) -> dict:
    return {name: {"op": "curve.keys", "keys": points}}


MOVE = keys("move", [[0, [-0.3, 0]], [1, [0.3, 0.1]]])


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class ConformanceTests(unittest.TestCase):
    """Each graph drawn by both renderers: GL must hold it (no fallback) and agree with the reference."""

    def same(self, nodes: dict, frames: int = 10, inputs: dict | None = None, strict: bool = False, **more) -> None:
        """As the GL conformance tests bound a drawing (`test_compositing_gl`): the mean and the 99th percentile,
        since a GPU samples a warped picture's edges with its own precision; `strict` for time operations
        alone, which choose and mix frames without resampling them -- there, every pixel."""

        g = graph(nodes, **{k: v for k, v in more.items() if k in ("output", "ports")})
        options = {k: v for k, v in more.items() if k in ("root", "origins")}
        given = {"plate": plate()} if inputs is None else inputs
        fast = renderer_for(g)
        self.assertIsNotNone(fast, "GL falls back to the reference")
        exact = evaluate(g, given, frames=frames, size=(W, H), fps=FPS, **options)
        drawn = np.stack(list(fast.evaluate(g, given, frames=frames, size=(W, H), fps=FPS, stream=True, **options)))
        difference = np.abs(exact - drawn)
        self.assertLess(float(difference.mean()), 5e-4)
        self.assertLess(float(np.quantile(difference, 0.99)), 2e-3)
        if strict:
            self.assertLess(float(difference.max()), 1e-4)

    def test_retimes(self) -> None:
        cases = {
            "2x": [[0, 0], [10, 20]], "half": [[0, 0], [10, 5]], "reverse": [[0, 1], [1, 0]],
            "freeze": [[0, 0.45], [1, 0.45]], "ramp": [{"t": 0, "value": 0, "ease": "in"}, {"t": 1, "value": 2}],
            "turning": [[0, 0], [0.5, 1.5], [1, 0.5]], "before the start": [[0, -0.5], [1, 0.5]],
        }
        for name, points in cases.items():
            for interpolation in ("nearest", "blend"):
                with self.subTest(case=name, interpolation=interpolation):
                    self.same({**keys("m", points), "out": {"op": "time.remap", "in": "plate", "map": {"curve": "m"},
                                                            "interpolation": interpolation}}, strict=True)

    def test_a_blend_on_the_last_frame_holds_it(self) -> None:
        self.same({**keys("m", [[0, 0.95], [1, 0.97]]),
                   "out": {"op": "time.remap", "in": "plate", "map": {"curve": "m"}, "interpolation": "blend"}},
                  inputs={"plate": plate(10)}, strict=True)

    def test_offsets_and_the_shutter(self) -> None:
        for frames in (3, -2, 0):
            with self.subTest(offset=frames):
                self.same({"out": {"op": "time.offset", "in": "plate", "frames": frames}}, strict=True)
        for span in (2, 3, 5):
            with self.subTest(shutter=span):
                self.same({"out": {"op": "time.blend", "in": "plate", "frames": span}}, strict=True)

    def test_trails_follow_a_moving_layer(self) -> None:
        for count, spacing, decay in ((3, 1, 0.5), (4, 2, 0.7), (0, 1, 0.5)):
            with self.subTest(count=count, spacing=spacing):
                self.same({**MOVE, "small": {"op": "warp.transform", "in": "plate", "scale": 0.3,
                                             "translate": {"curve": "move"}},
                           "out": {"op": "time.echo", "in": "small", "count": count, "spacing": spacing,
                                   "decay": decay}})

    def test_nested_and_combined(self) -> None:
        self.same({**keys("double", [[0, 0], [10, 20]]), **keys("back", [[0, 2], [2, 0]]), **MOVE,
                   "inner": {"op": "time.remap", "in": "plate", "map": {"curve": "back"}, "interpolation": "blend"},
                   "outer": {"op": "time.remap", "in": "inner", "map": {"curve": "double"}},
                   "late": {"op": "time.offset", "in": "outer", "frames": 2},
                   "small": {"op": "warp.transform", "in": "late", "scale": 0.4, "translate": {"curve": "move"}},
                   "out": {"op": "time.echo", "in": "small", "count": 2, "spacing": 2, "decay": 0.6}})


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class TrackConformanceTests(unittest.TestCase):
    same = ConformanceTests.same

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.plane = self.root / "plane.track.json"
        self.plane.write_text(json.dumps({"kind": "plane", "clock": {"rate": "10", "origin": {"ticks": 0}}, "frames": [
            {"corners": [[0.2 + i / 100, 0.2], [0.5 + i / 100, 0.25], [0.55 + i / 100, 0.7], [0.18 + i / 100, 0.66]]}
            for i in range(60)]}))
        self.point = self.root / "point.track.json"
        self.point.write_text(json.dumps({"kind": "point", "clock": {"rate": "10", "origin": {"ticks": 0}},
                                          "frames": [{"points": [[0.3 + i / 80, 0.5]]} for i in range(60)]}))

    def pin(self, track: Path, back: str = "plate", extra: dict | None = None, **more) -> None:
        self.same({"t": {"op": "track.read", "file": str(track), "of": "plate"},
                   "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
                   "pinned": {"op": "warp.corner_pin", "in": "white", "track": "t",
                              "corners": [[0, 0], [0.2, 0], [0.2, 0.3], [0, 0.3]]},
                   **(extra or {}), "out": {"op": "merge.over", "front": "pinned", "back": back}}, **more)

    def test_a_pin_by_a_plane_or_a_point_track(self) -> None:
        for track in (self.plane, self.point):
            with self.subTest(track=track.stem):
                self.pin(track, origins={"plate": Fraction(1, 2)})

    def test_a_pin_over_a_retimed_plate_follows_the_plate(self) -> None:
        for points in ([[0, 0], [10, 20]], [[0, 1], [1, 0]], [[0, 0], [0.5, 1.5], [1, 0.5]]):
            with self.subTest(map=points):
                self.pin(self.plane, back="shown", extra={**keys("m", points), "shown": {
                    "op": "time.remap", "in": "plate", "map": {"curve": "m"}}})

    def test_a_curve_from_a_track_drives_a_move(self) -> None:
        self.same({"t": {"op": "track.read", "file": str(self.point), "of": "plate"},
                   "x": {"op": "curve.from_track", "track": "t", "field": "x"},
                   "out": {"op": "warp.transform", "in": "plate", "translate": {"curve": "x"}, "scale": 0.5}},
                  origins={"plate": Fraction(1)})

    def test_a_measured_track(self) -> None:
        self.same({"t": {"op": "track.measure", "in": "plate", "kind": "point", "region": [0.3, 0.3, 0.7, 0.7]},
                   "x": {"op": "curve.from_track", "track": "t", "field": "x"},
                   "out": {"op": "warp.transform", "in": "plate", "translate": {"curve": "x"}}})

    @unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
    def test_a_production_track_with_a_correction(self) -> None:
        """GL reads the production's record as the reference does: validated, the person's correction in force."""

        from cine_toaster import tracks
        from cine_toaster.state import Actor

        film = self.root / "film"
        (film / "plates").mkdir(parents=True)
        (film / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
        frames = (plate(20)[..., :3] * 255).astype(np.uint8)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                        "-r", str(FPS), "-i", "-", "-c:v", "ffv1", "-pix_fmt", "bgr0", str(film / "plates" / "p.mkv")],
                       input=frames.tobytes(), check=True)
        person = Actor(id="editor")
        tracks.measure_track(film, track_id="p", media="plates/p.mkv", kind="point", region=[0.3, 0.3, 0.7, 0.7],
                             actor=person)
        tracks.correct_track(film, track_id="p", index=4, points=[[0.9, 0.1]], actor=person)
        self.same({"t": {"op": "track.read", "track": "p", "of": "plate"},
                   "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
                   "pinned": {"op": "warp.corner_pin", "in": "white", "track": "t",
                              "corners": [[0, 0], [0.2, 0], [0.2, 0.3], [0, 0.3]]},
                   "out": {"op": "merge.over", "front": "pinned", "back": "plate"}},
                  root=film, origins={"plate": Fraction(0)})

    @unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
    def test_a_source_read_back_past_its_start(self) -> None:
        """A pre-roll on GL: a file source whose remap runs back before its start reads the file's earlier frames,
        as the reference does."""

        clip = self.root / "n.mkv"
        frames = (plate(30)[..., :3] * 255).astype(np.uint8)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                        "-r", str(FPS), "-i", "-", "-c:v", "ffv1", "-pix_fmt", "bgr0", str(clip)],
                       input=frames.tobytes(), check=True)
        self.same({"src": {"op": "generate.source", "file": str(clip), "start": 1.0},
                   **keys("m", [[0, -0.5], [1, 0.5]]),
                   "out": {"op": "time.remap", "in": "src", "map": {"curve": "m"}}}, ports={}, inputs={})


if __name__ == "__main__":
    unittest.main()
