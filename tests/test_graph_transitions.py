"""Transitions as recipes of SPEC-0012 primitives (ADR 0022): the warp wipe, drawn by the reference."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cine_toaster.assembly import Plan, Segment, _resolve_join, probe, render
from cine_toaster.transitions import TransitionFormatError, list_transitions

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run(command, expected_seconds=None, message="", span=None):
    subprocess.run(command, check=True, capture_output=True)


class CatalogTests(unittest.TestCase):
    def test_the_warp_wipe_is_a_checked_recipe_with_its_pictures_and_preview(self) -> None:
        item = {entry["id"]: entry for entry in list_transitions()}["warp-wipe"]
        self.assertEqual((item["kind"], item["category"]), ("graph", "warp-wipe"))
        self.assertEqual(sorted(item["inputs"]), ["map_picture", "order_picture"])
        self.assertTrue(item["preview_path"].is_file())
        self.assertEqual(item["graph"]["output"], "out")

    def test_a_recipe_that_is_not_a_valid_graph_is_refused_when_the_catalog_loads(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw) / "transitions" / "broken"
            folder.mkdir(parents=True)
            (folder / "transition.toml").write_text(
                'id = "broken"\nname = "Broken"\nkind = "graph"\ndescription = "x"\nlicense = "MIT"\n'
                '[graph]\nports = {from = "picture", to = "picture", progress = "curve"}\noutput = "out"\n'
                '[graph.nodes]\nout = {op = "matte.threshold", matte = "from", progress = "progress"}\n')
            with self.assertRaisesRegex(TransitionFormatError, "not valid"):
                list_transitions(Path(raw))


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class AssemblyTests(unittest.TestCase):
    def test_a_warp_wipe_join_is_drawn_in_the_version_with_both_pictures_playing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name, colour in (("a.mp4", "red"), ("b.mp4", "blue")):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                                f"color={colour}:s=160x90:r=24:d=4", "-f", "lavfi", "-i", "anullsrc", "-shortest",
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(root / name)], check=True)
            catalog = {item["id"]: item for item in list_transitions()}
            plan = Plan(scene="S", segments=[Segment("P1", "A", "a.mp4", 0.0, 4.0, normalize=False)])
            incoming = Segment("P2", "B", "b.mp4", 0.0, 4.0, normalize=False)
            _resolve_join(root, plan, {"transition": {"id": "warp-wipe", "duration_ms": 2000}}, incoming,
                          {"catalog": catalog, "gl": None})
            self.assertIn("graph", incoming.transition)
            plan.segments.append(incoming)
            out = root / "cut.mp4"
            render(root, plan, out, root / "work", run)
            self.assertAlmostEqual(probe(out)["duration"], 6.0, delta=0.1)
            frames = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(out), "-f", "rawvideo", "-pix_fmt",
                                     "rgb24", "-"], capture_output=True).stdout
            import numpy as np

            pictures = np.frombuffer(frames, np.uint8).reshape(-1, 90, 160, 3)
            middle = pictures[72]  # the middle of the join
            self.assertGreater(middle[45, 80, 2], 200)  # the centre already shows the incoming picture
            self.assertGreater(middle[4, 4, 0], 200)    # a corner still the outgoing one
            self.assertGreater(pictures[20, 45, 80, 0], 200)
            self.assertGreater(pictures[130, 4, 4, 2], 200)


if __name__ == "__main__":
    unittest.main()
