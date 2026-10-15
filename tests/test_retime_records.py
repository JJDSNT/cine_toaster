"""C7 step 4 (CT-0080): retimes, offsets, trails and pins as a filmmaker writes them, compiled into the graph."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import numpy as np

from cine_toaster.compositing.layers import compile_layers
from cine_toaster.compositing.reference import evaluate
from cine_toaster.compositing.retime import HORIZON, compile_retime, map_keys, speed_keys
from cine_toaster.compositing.schema import validate

FPS = 10
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def numbered(count: int, size: tuple[int, int] = (2, 2)) -> np.ndarray:
    frames = np.zeros((count, size[1], size[0], 4), np.float32)
    frames[..., 3] = 1.0
    for index in range(count):
        frames[index, ..., 0] = index / 100
    return frames


def shown(graph: dict, frames: int = 10, source: int = 40) -> list[float]:
    out = evaluate(graph, {"picture": numbered(source)}, frames=frames, size=(2, 2), fps=FPS)
    return [round(float(frame[0, 0, 0]) * 100, 3) for frame in out]


class CompileTests(unittest.TestCase):
    def test_a_constant_speed_is_an_exact_map(self) -> None:
        graph, problems = compile_retime({"speed": 2})
        self.assertEqual((problems, validate(graph)), ([], []))
        self.assertEqual(graph["nodes"]["retime-map"]["keys"], [[0, 0], [int(HORIZON), int(2 * HORIZON)]])
        self.assertEqual(shown(graph), [1, 3, 5, 7, 9, 11, 13, 15, 17, 19])

    def test_held_speeds_are_exact_and_a_ramp_integrates_its_speed(self) -> None:
        keys, problems = speed_keys([{"t": 0, "speed": 1, "ease": "hold"}, {"t": 1, "speed": 3, "ease": "hold"}], None, "x")
        self.assertEqual(problems, [])
        self.assertEqual(map_keys(keys, Fraction(2)), [[0, 0], [1, 1], [2, 4]])
        ramp = map_keys([(Fraction(0), Fraction(1), "linear"), (Fraction(1), Fraction(3), "linear")], Fraction(1))
        self.assertEqual(ramp[-1], [1, 2])  # from 1x to 3x over a second: two seconds of source
        middle = dict((Fraction(str(t)).limit_denominator(1000), v) for t, v in ramp)[Fraction(1, 2)]
        self.assertAlmostEqual(middle, 0.5 + 2 * 0.25 / 2)  # v0 u + (v1 - v0) u^2 / (2 (t1 - t0)): 0.75

    def test_a_ramp_lands_on_a_beat(self) -> None:
        """1x until the shot's second beat, then 3x: the frame on that beat shows the source's own instant there,
        and the speed changes exactly at it."""

        beats = [0.5, 0.7]
        graph, problems = compile_retime({"speed": [{"t": 0, "speed": 1, "ease": "hold"},
                                                    {"beat": 2, "speed": 3, "ease": "hold"}]}, length=1.0, beats=beats)
        self.assertEqual(problems, [])
        frames = shown(graph)
        self.assertEqual(frames[:7], [0, 1, 2, 3, 4, 5, 6])  # 1x to the beat at 0.7 s
        self.assertEqual(frames[7:], [7 + 3 * k + 1 for k in range(3)])  # 3x from it: 8, 11, 14

    def test_a_beat_the_shot_does_not_have_is_refused(self) -> None:
        _, problems = compile_retime({"speed": [{"beat": 3, "speed": 2}]}, length=1.0, beats=[0.5])
        self.assertTrue(problems and "beat 3" in problems[0])

    def test_reverse_and_freeze(self) -> None:
        graph, _ = compile_retime({"reverse": True}, length=1.0)
        self.assertEqual(shown(graph), [9, 8, 7, 6, 5, 4, 3, 2, 1, 0])
        graph, _ = compile_retime({"freeze": 0.42}, length=1.0)
        self.assertEqual(shown(graph), [4] * 10)
        _, problems = compile_retime({"reverse": True})
        self.assertTrue(problems)  # backwards from where it would end: needs the length

    def test_mistakes_are_named(self) -> None:
        self.assertTrue(compile_retime({"sped": 2})[1])
        self.assertTrue(compile_retime({"interpolation": "optical"})[1])
        self.assertTrue(compile_retime({"speed": [{"t": 0}]})[1])


class LayerTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def layered(self, layers: list, frames: int = 10, size: tuple[int, int] = (2, 2), inputs: dict | None = None):
        graph, problems = compile_layers(layers)
        self.assertEqual(problems, [])
        self.assertEqual(validate(graph), [])
        return evaluate(graph, inputs or {}, frames=frames, size=size, fps=FPS)

    def clip(self, count: int = 40) -> str:
        """A numbered PNG sequence: frame i's red is i * 6 (display encoded)."""

        from PIL import Image

        folder = self.root / "clip"
        folder.mkdir(exist_ok=True)
        for index in range(count):
            Image.new("RGB", (4, 4), (index * 6, 0, 0)).save(folder / f"f_{index + 1:04d}.png")
        return str(folder / "f_%04d.png")

    def reds(self, out: np.ndarray) -> list[int]:
        from cine_toaster.compositing.reference import encode_srgb

        return [round(float(encode_srgb(frame[0, 0, :3])[0]) * 255 / 6) for frame in out]

    @unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
    def test_a_layer_is_retimed_and_offset(self) -> None:
        clip = self.clip()
        fast = self.layered([{"source": clip, "retime": {"speed": 2}}], size=(4, 4))
        self.assertEqual(self.reds(fast), [1, 3, 5, 7, 9, 11, 13, 15, 17, 19])
        late = self.layered([{"source": clip, "offset": 0.3}], size=(4, 4))
        self.assertEqual(self.reds(late), [0, 0, 0, 0, 1, 2, 3, 4, 5, 6])  # three frames late, held before

    def test_a_layer_s_retime_takes_no_beats_or_reverse(self) -> None:
        for spec in ({"speed": [{"beat": 1, "speed": 2}]}, {"reverse": True}):
            _, problems = compile_layers([{"source": "CUT"}, {"source": "plates/a.mp4", "retime": spec}])
            self.assertTrue(any("belong to a shot" in problem for problem in problems), problems)

    def test_trails_follow_a_moving_layer(self) -> None:
        """A white square moving right with an echo laid after its move: earlier positions trail on its left."""

        moving = {"source": "plate", "place": {"translate": {"keys": [[0, [-0.4, 0]], [1, [0.4, 0]]]}, "scale": 0.1},
                  "echo": {"count": 3, "spacing": 1, "decay": 0.6}}
        graph, problems = compile_layers([{"source": "plate"}, moving])
        self.assertEqual(problems, [])
        graph["nodes"]["L1"] = {"op": "generate.solid", "colour": [0, 0, 0, 1]}
        graph["nodes"]["L2"] = {"op": "generate.solid", "colour": [1, 1, 1, 1]}
        out = evaluate(graph, {}, frames=10, size=(100, 10), fps=FPS)
        frame = out[6, 5, :, 0]
        lit = np.nonzero(frame > 0.05)[0]
        brightest = int(np.argmax(frame))
        self.assertLess(lit.min(), brightest - 5)  # a trail to the left of where it is now
        self.assertGreater(frame[brightest], frame[lit.min()])  # fading behind it

    def test_a_layer_is_pinned_by_a_track_of_the_layer_below(self) -> None:
        track = self.root / "plate.track.json"
        track.write_text(json.dumps({"kind": "point", "clock": {"rate": "10", "origin": {"ticks": 0}},
                                     "frames": [{"points": [[0.1 + index / 100, 0.5]]} for index in range(40)]}))
        layers = [{"source": "plate"},
                  {"source": "window", "pin": {"track": str(track), "corners": [[0, 0], [0.1, 0], [0.1, 1], [0, 1]]}}]
        graph, problems = compile_layers(layers)
        self.assertEqual(problems, [])
        self.assertEqual(graph["nodes"]["L2-track"]["of"], "L1")
        graph["nodes"]["L1"] = {"op": "generate.solid", "colour": [0, 0, 0, 1]}
        graph["nodes"]["L2"] = {"op": "generate.solid", "colour": [1, 1, 1, 1]}
        out = evaluate(graph, {}, frames=10, size=(100, 4), fps=FPS)
        lefts = [int(np.nonzero(frame[2, :, 0] > 0.5)[0].min()) for frame in out]
        self.assertEqual(lefts, list(range(10)))  # one pixel a frame, as the track moves one hundredth

    def test_a_plane_track_carries_given_corners_or_fills_its_plane(self) -> None:
        """With corners, a layer moves as the plane moves (a window kept on a moving wall); without, it fills the
        tracked plane (a screen replaced)."""

        track = self.root / "plane.track.json"
        track.write_text(json.dumps({"kind": "plane", "clock": {"rate": "10", "origin": {"ticks": 0}}, "frames": [
            {"corners": [[0.4 + i / 100, 0.3], [0.6 + i / 100, 0.3], [0.6 + i / 100, 0.7], [0.4 + i / 100, 0.7]]}
            for i in range(40)]}))
        lefts = {}
        for name, corners in (("carried", [[0, 0], [0.1, 0], [0.1, 1], [0, 1]]), ("filled", None)):
            pin = {"track": str(track), **({"corners": corners} if corners else {})}
            graph, problems = compile_layers([{"source": "plate"}, {"source": "window", "pin": pin}])
            self.assertEqual(problems, [])
            graph["nodes"]["L1"] = {"op": "generate.solid", "colour": [0, 0, 0, 1]}
            graph["nodes"]["L2"] = {"op": "generate.solid", "colour": [1, 1, 1, 1]}
            out = evaluate(graph, {}, frames=6, size=(100, 4), fps=FPS)
            lefts[name] = [int(np.nonzero(frame[2, :, 0] > 0.5)[0].min()) for frame in out]
        self.assertEqual(lefts["carried"], [0, 1, 2, 3, 4, 5])  # from the frame's left edge, moved with the plane
        self.assertEqual(lefts["filled"], [40, 41, 42, 43, 44, 45])  # the plane's own place

    def test_a_pin_says_what_it_follows(self) -> None:
        for spec, wanted in (({"track": "t.json", "of": 2}, "layer below"), ({"measure": "camera"}, "point or a plane"),
                             ({"of": 1}, "track: file")):
            _, problems = compile_layers([{"source": "plate"}, {"source": "window", "pin": spec}])
            self.assertTrue(any(wanted in problem for problem in problems), (spec, problems))
        _, problems = compile_layers([{"source": "plate"}, {"source": "w", "pin": {"track": "t.json"},
                                                            "place": {"scale": 0.5}}])
        self.assertTrue(any("pinned or placed" in problem for problem in problems))


class PlanTests(unittest.TestCase):
    """Found by C7's films (step 7): a shot made only of layers never read its retime, and its fields were taken
    for unknown ones."""

    def test_a_shot_of_layers_alone_keeps_its_retime_and_its_fields_are_known(self) -> None:
        from cine_toaster.assembly import plan_scene
        from cine_toaster.project import load_production

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
            (root / "plates").mkdir()
            (root / "scenes" / "010").mkdir(parents=True)
            (root / "scenes" / "010" / "scene.yaml").write_text(
                "scene: S1\nshots:\n  - n: 1\n    duration: 2\n    label: Layers alone.\n"
                "    layers:\n      - source: plates/a.mp4\n    retime: {speed: 2}\n    retime_sound: stretch\n"
                "    stretch_with: anchored\n")
            scene = load_production(root)["scenes"][0]
            self.assertFalse([f for f in scene["findings"] if f["code"] == "shot_field_undeclared"], scene["findings"])
            self.assertEqual(plan_scene(root, scene).segments[0].retime, {"speed": 2})


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class ShotTests(unittest.TestCase):
    def test_a_shot_s_retime_is_drawn_and_its_sound_follows_its_policy(self) -> None:
        import importlib.util

        from cine_toaster.assembly import plan_scene, render
        from cine_toaster.project import load_production

        spec = importlib.util.spec_from_file_location(
            "time_drift", Path(__file__).parents[1] / "scripts" / "research" / "time_drift.py")
        drift = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(drift)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "film"
            drift.make_film(root, 2, "24")
            scene = root / "scenes" / "010" / "scene.yaml"
            scene.write_text(scene.read_text().replace(
                "    label: Shot 1.\n", "    label: Shot 1.\n    retime: {speed: 2}\n    retime_sound: stretch\n"))
            plan = plan_scene(root, load_production(root)["scenes"][0])
            self.assertEqual(plan.segments[0].retime, {"speed": 2})
            render(root, plan, root / "cut.mp4", root / "work",
                   lambda command, **_: subprocess.run(command, check=True, capture_output=True))
            self.assertTrue(any("P1: retimed -- its take's sound stretched" in note for note in plan.notes), plan.notes)
            raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(root / "work" / "sound.wav"), "-ac", "1",
                                  "-f", "f32le", "-"], capture_output=True, check=True).stdout
            sound = np.abs(np.frombuffer(raw, np.float32))
            first = int(np.argmax(sound > 0.5 * sound.max()))
            self.assertEqual(first, round((Fraction(20, 24) - Fraction(8, 24)) / 2 * 48000))  # 2x: at 12,000


if __name__ == "__main__":
    unittest.main()
