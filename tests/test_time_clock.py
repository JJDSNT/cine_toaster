"""C7 step 2 (CT-0080): timeline time against source time -- composed, with origins, pre-rolls and track clocks."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import numpy as np

from cine_toaster.compositing import clock
from cine_toaster.compositing.reference import curve_factory, evaluate, preroll, retimed, source_extents
from cine_toaster.errors import ValidationError

FPS = 10
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def numbered(count: int) -> np.ndarray:
    frames = np.zeros((count, 2, 2, 4), np.float32)
    frames[..., 3] = 1.0
    for index in range(count):
        frames[index, ..., 0] = index / 100
    return frames


def curves(nodes: dict) -> object:
    return curve_factory(nodes, {}, fps=FPS, length=1.0, beats=None, tracks=lambda reference: {})


class CompositionTests(unittest.TestCase):
    """Every time operation on the way from a node to a source, composed, exactly."""

    def test_an_offset_under_a_remap_composes(self) -> None:
        nodes = {"m": {"op": "curve.keys", "keys": [[0, 0], [1, 2]]},
                 "late": {"op": "time.offset", "in": "plate", "frames": 2},
                 "out": {"op": "time.remap", "in": "late", "map": {"curve": "m"}}}
        # Output frame 0's centre (0.05 s): the remap reads 0.1 s, the offset two frames earlier, -0.1 s.
        self.assertEqual(clock.instants(nodes, curves(nodes), FPS, "out", "plate", clock.centre(0, FPS)),
                         [Fraction(-1, 10)])

    def test_nested_remaps_compose(self) -> None:
        nodes = {"double": {"op": "curve.keys", "keys": [[0, 0], [1, 2]]},
                 "back": {"op": "curve.keys", "keys": [[0, 2], [2, 0]]},
                 "inner": {"op": "time.remap", "in": "plate", "map": {"curve": "back"}},
                 "out": {"op": "time.remap", "in": "inner", "map": {"curve": "double"}}}
        # 0.25 s -> 0.5 s (double) -> 1.5 s (reverse over two seconds).
        self.assertEqual(clock.instants(nodes, curves(nodes), FPS, "out", "plate", Fraction(1, 4)), [Fraction(3, 2)])

    def test_two_paths_at_two_times_are_both_kept_and_a_single_instant_is_refused(self) -> None:
        nodes = {"m": {"op": "curve.keys", "keys": [[0, 0], [1, 2]]},
                 "fast": {"op": "time.remap", "in": "plate", "map": {"curve": "m"}},
                 "out": {"op": "merge.over", "front": "fast", "back": "plate"}}
        found = clock.instants(nodes, curves(nodes), FPS, "out", "plate", clock.centre(2, FPS))
        self.assertEqual(sorted(found), [Fraction(1, 4), Fraction(1, 2)])
        with self.assertRaises(ValidationError):
            clock.instant(nodes, curves(nodes), FPS, "out", "plate", clock.centre(2, FPS))

    def test_extents_follow_every_path_and_reach_back(self) -> None:
        graph = {"ports": {"plate": "picture"}, "output": "out",
                 "nodes": {"m": {"op": "curve.keys", "keys": [[0, -0.5], [1, 0.5]]},
                           "out": {"op": "time.remap", "in": "plate", "map": {"curve": "m"}}}}
        self.assertEqual(source_extents(graph, 10, FPS)["plate"], (-5, 9))
        self.assertEqual(preroll(graph, 10, FPS), 5)


class RetimeTests(unittest.TestCase):
    def graph(self, keys: list) -> dict:
        return {"ports": {"plate": "picture"}, "output": "out",
                "nodes": {"m": {"op": "curve.keys", "keys": keys},
                          "out": {"op": "time.remap", "in": "plate", "map": {"curve": "m"}}}}

    def test_a_shot_is_retimed_only_when_a_source_is_shown_at_another_time(self) -> None:
        self.assertTrue(retimed(self.graph([[0, 0], [1, 2]]), 10, FPS))
        self.assertFalse(retimed(self.graph([[0, 0], [1, 1]]), 10, FPS))  # a remap that changes nothing
        still = {"ports": {"plate": "picture"}, "output": "out",
                 "nodes": {"out": {"op": "colour.grade", "in": "plate", "gain": [1, 1, 1]}}}
        self.assertFalse(retimed(still, 10, FPS))


class TrackClockTests(unittest.TestCase):
    """A track is data of its source: read by its own clock at the instant its source shows."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        # Made on the whole take at 10 fps: entry i at the take's 0.1 i s, its x the entry's number.
        track = {"kind": "point", "clock": {"rate": "10", "origin": {"ticks": 0}},
                 "frames": [{"points": [[index / 100, 0.5]]} for index in range(40)]}
        self.track = self.root / "plate.track.json"
        self.track.write_text(json.dumps(track))

    def xs(self, nodes: dict, output: str, origins: dict | None = None, frames: int = 5) -> list[float]:
        graph = {"ports": {"plate": "picture"}, "output": output, "nodes": {
            "t": {"op": "track.read", "file": str(self.track), "of": "plate"},
            "x": {"op": "curve.from_track", "track": "t", "field": "x"},
            "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
            "dot": {"op": "colour.grade", "in": "white", "gain": {"curve": "x"}}, **nodes}}
        out = evaluate(graph, {"plate": numbered(40)}, frames=frames, size=(2, 2), fps=FPS, origins=origins)
        return [round(float(frame[0, 0, 0]) * 100, 3) for frame in out]

    def test_a_track_of_the_whole_take_lands_on_the_cut(self) -> None:
        """The shot starts at the take's 1 s (the cut point): the track is read from its entry 10, not 0."""

        nodes = {"out": {"op": "merge.over", "front": "dot", "back": "plate"}}
        self.assertEqual(self.xs(nodes, "out", origins={"plate": Fraction(1)}), [10, 11, 12, 13, 14])
        self.assertEqual(self.xs(nodes, "out"), [0, 1, 2, 3, 4])  # no origin given: the take from its start

    def test_a_reader_over_a_retimed_plate_follows_the_plate(self) -> None:
        """The plate at 2x under a dot that reads its track: the dot follows the frames the plate shows."""

        nodes = {"m": {"op": "curve.keys", "keys": [[0, 0], [1, 2]]},
                 "fast": {"op": "time.remap", "in": "plate", "map": {"curve": "m"}},
                 "out": {"op": "merge.over", "front": "dot", "back": "fast"}}
        self.assertEqual(self.xs(nodes, "out"), [1, 3, 5, 7, 9])

    def test_a_reader_whose_source_is_shown_at_two_times_is_refused(self) -> None:
        nodes = {"m": {"op": "curve.keys", "keys": [[0, 0], [1, 2]]},
                 "fast": {"op": "time.remap", "in": "plate", "map": {"curve": "m"}},
                 "both": {"op": "merge.over", "front": "fast", "back": "plate"},
                 "out": {"op": "merge.over", "front": "dot", "back": "both"}}
        with self.assertRaises(ValidationError):
            self.xs(nodes, "out")

    def test_a_measured_track_keeps_its_clock(self) -> None:
        from cine_toaster.compositing.tracking import measure  # noqa: F401 - OpenCV is needed

        textured = np.stack([np.roll(np.random.default_rng(1).uniform(0, 1, (24, 32, 1)).repeat(4, -1)
                                     .astype(np.float32), 2 * frame, axis=1) for frame in range(6)])
        textured[..., 3] = 1.0
        graph = {"ports": {"plate": "picture"}, "output": "out", "nodes": {
            "t": {"op": "track.measure", "in": "plate", "kind": "point", "region": [0.3, 0.3, 0.7, 0.7]},
            "x": {"op": "curve.from_track", "track": "t", "field": "x"},
            "out": {"op": "warp.transform", "in": "plate", "translate": {"curve": "x"}}}}
        out = evaluate(graph, {"plate": textured}, frames=6, size=(32, 24), fps=FPS, origins={"plate": Fraction(3)})
        self.assertEqual(out.shape[0], 6)  # read by its clock from the plate's origin: lands on its own frames


class ScenarioTests(unittest.TestCase):
    """The user's review: three scenarios covered explicitly, and a trim never taken for a retime."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        # A track of the whole take at 10 fps: entry i's x is i / 100.
        self.track = Path(directory.name) / "take.track.json"
        self.track.write_text(json.dumps({"kind": "point", "clock": {"rate": "10", "origin": {"ticks": 0}},
                                          "frames": [{"points": [[index / 100, 0.5]]} for index in range(60)]}))

    def read(self, nodes: dict, origin: Fraction, frames: int = 10) -> list[float]:
        graph = {"ports": {"plate": "picture"}, "output": "out", "nodes": {
            "t": {"op": "track.read", "file": str(self.track), "of": "plate"},
            "x": {"op": "curve.from_track", "track": "t", "field": "x"},
            "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
            "dot": {"op": "colour.grade", "in": "white", "gain": {"curve": "x"}}, **nodes}}
        out = evaluate(graph, {"plate": numbered(60)}, frames=frames, size=(2, 2), fps=FPS,
                       origins={"plate": origin})
        return [round(float(frame[0, 0, 0]) * 100, 3) for frame in out]

    def test_a_whole_take_track_stays_right_after_a_trim_an_offset_and_a_reverse(self) -> None:
        trim = Fraction(2)  # the cut point: the take's 2 s, entry 20
        plain = {"out": {"op": "merge.over", "front": "dot", "back": "plate"}}
        self.assertEqual(self.read(plain, trim, 3), [20, 21, 22])
        offset = {"late": {"op": "time.offset", "in": "plate", "frames": 3},
                  "out": {"op": "merge.over", "front": "dot", "back": "late"}}
        self.assertEqual(self.read(offset, trim, 3), [17, 18, 19])  # three frames earlier of the plate
        reverse = {"m": {"op": "curve.keys", "keys": [[0, 1], [1, 0]]},
                   "back": {"op": "time.remap", "in": "plate", "map": {"curve": "m"}},
                   "out": {"op": "merge.over", "front": "dot", "back": "back"}}
        self.assertEqual(self.read(reverse, trim, 10), [29, 28, 27, 26, 25, 24, 23, 22, 21, 20])

    def test_a_source_in_two_branches_at_two_times_composes_without_complaint(self) -> None:
        """Several instants are legitimate for pictures (an echo, two remaps): only a single reference refuses."""

        graph = {"ports": {"plate": "picture"}, "output": "out", "nodes": {
            "fast": {"op": "curve.keys", "keys": [[0, 0], [1, 2]]},
            "slow": {"op": "curve.keys", "keys": [[0, 0], [1, 0.5]]},
            "a": {"op": "time.remap", "in": "plate", "map": {"curve": "fast"}},
            "b": {"op": "time.remap", "in": "plate", "map": {"curve": "slow"}},
            "mix": {"op": "merge.mix", "a": "a", "b": "b", "by": "half"},
            "half": {"op": "curve.keys", "keys": [[0, 0.5]]},
            "out": {"op": "time.echo", "in": "mix", "count": 2, "spacing": 1, "decay": 0.5}}}
        out = evaluate(graph, {"plate": numbered(30)}, frames=10, size=(2, 2), fps=FPS, origins={"plate": Fraction(1)})
        self.assertEqual(out.shape[0], 10)

    def test_a_corner_pin_after_a_turning_retime_follows_the_plate(self) -> None:
        """A strip pinned by the plate's point track over a plate remapped forward then back: it moves with
        the entries the plate shows, frame by frame, from where it was at the shot's first frame."""

        keys = [[0, 0], [0.5, 1.5], [1, 0.5]]  # forward at 3x, then back at 2x
        graph = {"ports": {"plate": "picture"}, "output": "out", "nodes": {
            "t": {"op": "track.read", "file": str(self.track), "of": "plate"},
            "m": {"op": "curve.keys", "keys": keys},
            "shown": {"op": "time.remap", "in": "plate", "map": {"curve": "m"}},
            "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
            "strip": {"op": "warp.corner_pin", "in": "white", "track": "t",
                      "corners": [[0, 0], [0.1, 0], [0.1, 1], [0, 1]]},
            "out": {"op": "merge.over", "front": "strip", "back": "shown"}}}
        plate = np.zeros((60, 4, 100, 4), np.float32)
        plate[..., 3] = 1.0
        out = evaluate(graph, {"plate": plate}, frames=10, size=(100, 4), fps=FPS, origins={"plate": Fraction(0)})
        lefts = [int(np.nonzero(frame[2, :, 0] > 0.5)[0].min()) for frame in out]

        def entry(frame: int) -> int:  # the plate's frame at output frame `frame`, from the map by hand
            t = Fraction(2 * frame + 1, 2 * FPS)
            at = 3 * t if t < Fraction(1, 2) else Fraction(3, 2) - 2 * (t - Fraction(1, 2))
            return int(at * FPS)

        self.assertEqual(lefts, [entry(frame) - entry(0) for frame in range(10)])
        self.assertLess(lefts[-1], max(lefts))  # it turned back with the plate

    def test_a_trim_is_not_a_retime(self) -> None:
        """A shot cut later in its take (an origin) or a graph with no time operation is not retimed; nor is a
        zero offset or a remap that maps each frame to itself."""

        plain = {"ports": {"plate": "picture"}, "output": "out",
                 "nodes": {"out": {"op": "colour.grade", "in": "plate", "gain": [1, 1, 1]}}}
        self.assertFalse(retimed(plain, 10, FPS))
        zero = {"ports": {"plate": "picture"}, "output": "out",
                "nodes": {"out": {"op": "time.offset", "in": "plate", "frames": 0}}}
        self.assertFalse(retimed(zero, 10, FPS))
        late = {"ports": {"plate": "picture"}, "output": "out",
                "nodes": {"out": {"op": "time.offset", "in": "plate", "frames": 3}}}
        self.assertTrue(retimed(late, 10, FPS))  # shown three frames late: its sound would not be its picture's


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class PrerollTests(unittest.TestCase):
    def test_a_remap_back_past_the_start_reads_the_file_before_it(self) -> None:
        """A source starting at 1 s, read half a second back: frames of the file before its start, not its
        first frame held."""

        with tempfile.TemporaryDirectory() as directory:
            clip = Path(directory) / "numbered.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            f"color=c=black:s=16x16:r={FPS}:d=3,geq=r='N*8':g=0:b=0", "-c:v", "libx264", "-qp", "0",
                            "-pix_fmt", "yuv444p", str(clip)], check=True)
            graph = {"ports": {}, "output": "out",
                     "nodes": {"src": {"op": "generate.source", "file": str(clip), "start": 1.0},
                               "m": {"op": "curve.keys", "keys": [[0, -0.5], [1, 0.5]]},
                               "out": {"op": "time.remap", "in": "src", "map": {"curve": "m"}}}}
            from cine_toaster.compositing.reference import encode_srgb

            out = evaluate(graph, {}, frames=10, size=(16, 16), fps=FPS)
            numbers = [round(float(encode_srgb(frame[8, 8, :3])[0]) * 255 / 8) for frame in out]
            self.assertEqual(numbers[:3], [5, 6, 7])  # the file's frames 5, 6, 7: before the source's start (10)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class MuteTests(unittest.TestCase):
    def test_a_retimed_shot_is_muted_and_a_shot_without_a_retime_is_not(self) -> None:
        import importlib.util

        from cine_toaster.assembly import plan_scene, render
        from cine_toaster.project import load_production

        spec = importlib.util.spec_from_file_location(
            "time_drift", Path(__file__).parents[1] / "scripts" / "research" / "time_drift.py")
        drift = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(drift)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "film"
            drift.make_film(root, 2, "24")  # two takes, each with a flash and a click
            scene = root / "scenes" / "010" / "scene.yaml"
            scene.write_text(scene.read_text().replace("    label: Shot 1.\n", (
                "    label: Shot 1.\n    composite:\n      nodes:\n        room: {op: generate.source, take: CUT}\n"
                "        m: {op: curve.keys, keys: [[0, 0], [1, 2]]}\n"
                "        out: {op: time.remap, in: room, map: {curve: m}}\n      output: out\n")))
            plan = plan_scene(root, load_production(root)["scenes"][0])
            render(root, plan, root / "cut.mp4", root / "work",
                   lambda command, **_: subprocess.run(command, check=True, capture_output=True))
            self.assertTrue(any("P1: retimed" in note for note in plan.notes), plan.notes)
            self.assertFalse(any("P2: retimed" in note for note in plan.notes))
            clicks = drift._clicks(root / "work" / "sound.wav")
            self.assertEqual(len(clicks), 1)  # only the second shot's click is heard
            self.assertGreater(clicks[0], 48000 * (plan.segments[0].end - plan.segments[0].start) - 1)
