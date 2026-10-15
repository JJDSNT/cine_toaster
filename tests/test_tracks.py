"""C7 step 5 (CT-0080): tracks as production records -- measured on media, corrected apart, refused when stale,
reused by any shot under any retime."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock

import numpy as np

from cine_toaster import tracks
from cine_toaster.compositing.reference import evaluate
from cine_toaster.errors import ValidationError
from cine_toaster.events import tail_events
from cine_toaster.state import Actor

HAS_TOOLS = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
W, H, FPS, FRAMES = 160, 90, 24, 48
PERSON = Actor(id="editor")


def pan(path: Path, *, occluded: range = range(0), seed: int = 4) -> Path:
    """A camera panning over texture, 2 px a frame to the left (what is seen moves 2 px left); `occluded`
    frames are flat grey (the view covered). Lossless."""

    texture = np.random.default_rng(seed).integers(0, 255, (H, W + 2 * FRAMES + 10), dtype=np.uint8)
    texture = np.kron(texture[:, ::2], np.ones((1, 2), np.uint8))[:, : W + 2 * FRAMES + 10]  # 2-px grain
    frames = []
    for index in range(FRAMES):
        grey = texture[:, 2 * index:2 * index + W].copy()
        if index in occluded:
            grey[:, :] = 128
        frames.append(np.stack([grey] * 3, axis=-1))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                    "-r", str(FPS), "-i", "-", "-c:v", "ffv1", "-pix_fmt", "bgr0", str(path)],
                   input=np.stack(frames).tobytes(), check=True)
    return path


@unittest.skipUnless(HAS_TOOLS, "FFmpeg is missing")
class TrackRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "film"
        (self.root / "plates").mkdir(parents=True)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
        pan(self.root / "plates" / "pan.mkv")

    def measure(self, track_id: str = "window", **more) -> dict:
        return tracks.measure_track(self.root, track_id=track_id, media="plates/pan.mkv", kind=more.pop("kind", "point"),
                                    region=more.pop("region", [0.35, 0.3, 0.65, 0.7]), actor=PERSON, **more)

    def test_a_track_is_a_record_of_its_media_with_its_clock_and_confidence(self) -> None:
        self.measure()
        folder = self.root / "tracks" / "window"
        self.assertTrue((folder / "track.yaml").is_file() and (folder / "measurements" / "0001.json").is_file())
        track = tracks.load_track(self.root, "window")
        self.assertEqual(track["clock"], {"rate": "24", "origin": {"ticks": 0}})
        self.assertEqual(len(track["frames"]), FRAMES)
        xs = [entry["points"][0][0] * W for entry in track["frames"]]
        self.assertAlmostEqual((xs[0] - xs[-1]) / (FRAMES - 1), 2.0, delta=0.1)  # what is seen moves 2 px left
        self.assertTrue(all(0.0 <= entry["confidence"] <= 1.0 for entry in track["frames"]))
        self.assertGreater(min(entry["confidence"] for entry in track["frames"]), 0.5)
        self.assertEqual(tracks.status(self.root, "window")["stale"], [])

    def test_an_occlusion_is_weak_and_the_track_is_found_again_where_it_really_is(self) -> None:
        """The view covered for six frames while the camera pans on: those entries are weak (held, worth
        nothing), and the track is found again by its last appearance -- where the texture has moved to, not
        where it was."""

        pan(self.root / "plates" / "pan.mkv", occluded=range(20, 26))
        for kind in ("point", "plane"):
            with self.subTest(kind=kind):
                self.measure(kind, kind=kind)
                self.assertEqual(tracks.status(self.root, kind)["weak"], [(20, 25)])
                frames = tracks.load_track(self.root, kind)["frames"]
                found = frames[26]
                self.assertTrue(found.get("reacquired"))
                x = (found["points"][0][0] if "points" in found else sum(c[0] for c in found["corners"]) / 4) * W
                self.assertAlmostEqual(x, 42 - 2 * 7, delta=0.5)  # moved on 14 px while hidden

    def test_corrections_are_kept_apart_and_reverted_without_losing_the_measurement(self) -> None:
        self.measure()
        measured = (self.root / "tracks" / "window" / "measurements" / "0001.json").read_bytes()
        original = tracks.load_track(self.root, "window")["frames"][5]
        tracks.correct_track(self.root, track_id="window", index=5, points=[[0.5, 0.5]], actor=PERSON, note="drifted")
        corrected = tracks.load_track(self.root, "window")["frames"][5]
        self.assertEqual((corrected["points"], corrected["confidence"]), ([[0.5, 0.5]], 1.0))
        self.assertTrue(corrected["corrected"].startswith("cor_"))
        self.assertEqual((self.root / "tracks" / "window" / "measurements" / "0001.json").read_bytes(), measured)
        tracks.revert_corrections(self.root, track_id="window", index=5, actor=PERSON, note="it was right")
        self.assertEqual(tracks.load_track(self.root, "window")["frames"][5], original)
        kept = json.loads((self.root / "tracks" / "window" / "corrections.json").read_text())
        self.assertEqual([(item["index"], item["active"]) for item in kept], [(5, False)])  # reverted, kept
        types = [event["type"] for event in tail_events(self.root)]
        self.assertEqual([t for t in types if t.startswith("track.")], ["track.measured", "track.corrected",
                                                                        "track.reverted"])

    def test_a_correction_is_checked(self) -> None:
        self.measure()
        with self.assertRaises(ValidationError):
            tracks.correct_track(self.root, track_id="window", index=FRAMES, points=[[0.5, 0.5]], actor=PERSON)
        with self.assertRaises(ValidationError):
            tracks.correct_track(self.root, track_id="window", index=1, corners=[[0, 0]], actor=PERSON)
        with self.assertRaises(ValidationError):
            tracks.correct_track(self.root, track_id="window", index=1, points=[[0.5, 0.5]], actor=PERSON,
                                 expected_revision=99)

    def test_a_track_whose_media_or_measuring_changed_is_stale_and_refused(self) -> None:
        self.measure()
        pan(self.root / "plates" / "pan.mkv", seed=9)  # other content under the same name
        state = tracks.status(self.root, "window")
        self.assertTrue(any("has changed" in reason for reason in state["stale"]), state)
        with self.assertRaises(ValidationError) as caught:
            tracks.load_track(self.root, "window")
        self.assertIn("toast track measure", str(caught.exception))
        self.measure()  # measured again: in use, fresh
        self.assertEqual(tracks.status(self.root, "window")["stale"], [])
        record = self.root / "tracks" / "window" / "track.yaml"
        record.write_text(record.read_text().replace("- 0.35", "- 0.3"))  # the region asked is now another
        self.assertTrue(any("region" in reason for reason in tracks.status(self.root, "window")["stale"]))

    def test_a_new_tracker_makes_old_tracks_stale(self) -> None:
        self.measure()
        from cine_toaster.compositing import tracking

        with mock.patch.object(tracking, "TRACKER_VERSION", tracking.TRACKER_VERSION + 1):
            self.assertTrue(any("tracking is now" in reason for reason in tracks.status(self.root, "window")["stale"]))

    def test_corrections_on_an_earlier_measurement_are_kept_not_applied(self) -> None:
        self.measure()
        tracks.correct_track(self.root, track_id="window", index=3, points=[[0.1, 0.1]], actor=PERSON)
        self.measure()  # measurement 2
        state = tracks.status(self.root, "window")
        self.assertEqual((state["measurement"], state["corrections"], state["corrections_on_earlier_measurements"]),
                         (2, 0, 1))
        self.assertNotEqual(tracks.load_track(self.root, "window")["frames"][3]["points"], [[0.1, 0.1]])

    def test_one_track_serves_every_shot_and_every_retime(self) -> None:
        """The same production track read by shots cut at different points of the take, offset, ramped and
        reversed: each reads the entry of the media instant it shows."""

        self.measure()
        entries = tracks.load_track(self.root, "window")["frames"]

        def read(nodes: dict, origin: Fraction, frames: int = 6) -> list[int]:
            graph = {"ports": {"plate": "picture"}, "output": "out", "nodes": {
                "t": {"op": "track.read", "track": "window", "of": "plate"},
                "x": {"op": "curve.from_track", "track": "t", "field": "x"},
                "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
                "dot": {"op": "colour.grade", "in": "white", "gain": {"curve": "x"}}, **nodes}}
            plate = np.zeros((60, 2, 2, 4), np.float32)
            out = evaluate(graph, {"plate": plate}, frames=frames, size=(2, 2), fps=FPS, root=self.root,
                           origins={"plate": origin})
            xs = [round(float(frame[0, 0, 0]), 5) for frame in out]
            table = {round(entry["points"][0][0], 5): index for index, entry in enumerate(entries)}
            return [table[min(table, key=lambda value: abs(value - x))] for x in xs]

        over = lambda back: {"out": {"op": "merge.over", "front": "dot", "back": back}}  # noqa: E731
        self.assertEqual(read(over("plate"), Fraction(0)), [0, 1, 2, 3, 4, 5])  # cut at the take's start
        self.assertEqual(read(over("plate"), Fraction(10, 24)), [10, 11, 12, 13, 14, 15])  # cut later
        offset = {"late": {"op": "time.offset", "in": "plate", "frames": 2}, **over("late")}
        self.assertEqual(read(offset, Fraction(10, 24)), [8, 9, 10, 11, 12, 13])
        fast = {"m": {"op": "curve.keys", "keys": [[0, 0], [10, 20]]},
                "fast": {"op": "time.remap", "in": "plate", "map": {"curve": "m"}}, **over("fast")}
        self.assertEqual(read(fast, Fraction(10, 24)), [11, 13, 15, 17, 19, 21])
        back = {"m": {"op": "curve.keys", "keys": [[0, 0.25], [0.25, 0]]},
                "back": {"op": "time.remap", "in": "plate", "map": {"curve": "m"}}, **over("back")}
        self.assertEqual(read(back, Fraction(10, 24)), [15, 14, 13, 12, 11, 10])

    def test_a_layer_pins_by_a_production_track(self) -> None:
        from cine_toaster.compositing.layers import compile_layers

        graph, problems = compile_layers([{"source": "plates/pan.mkv"},
                                          {"source": "plates/pan.mkv", "pin": {"track": "window", "of": 1}}])
        self.assertEqual(problems, [])
        self.assertEqual(graph["nodes"]["L2-track"], {"op": "track.read", "track": "window", "of": "L1"})

    def test_the_command_line_sees_a_track(self) -> None:
        self.measure()
        import sys

        shown = subprocess.run([sys.executable, "-m", "cine_toaster.cli", "track", "status", str(self.root), "window"],
                               capture_output=True, text=True, env={"PYTHONPATH": str(Path(__file__).parents[1] / "src"),
                                                                     "PATH": "/usr/bin:/bin"})
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(shown.stdout)["stale"], [])


if __name__ == "__main__":
    unittest.main()
