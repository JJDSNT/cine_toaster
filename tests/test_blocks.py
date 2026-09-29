"""A block's clip is sliced where the model really cut, not where it was asked to (CT-0037)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cine_toaster.blocks import assign, decide, requested_cuts
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.project import load_scene

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
FPS = 24


def clip(path: Path, colours: list[tuple[str, int]]) -> Path:
    """A clip of solid colours, each for a number of frames, with sound."""

    inputs, filters = [], []
    for index, (colour, frames) in enumerate(colours):
        inputs += ["-f", "lavfi", "-i", f"color=c={colour}:s=64x36:r={FPS}:d={frames / FPS}"]
        filters.append(f"[{index}:v]")
    graph = "".join(filters) + f"concat=n={len(colours)}:v=1:a=0[v]"
    total = sum(frames for _, frames in colours) / FPS
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={total}",
                    "-filter_complex", graph, "-map", "[v]", "-map", f"{len(colours)}:a", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def picture(path: Path, colour: str) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s=64x36", "-frames:v", "1",
                    str(path)], check=True)
    return path


class AssignTests(unittest.TestCase):
    def test_an_extra_stretch_joins_the_shot_it_resembles(self) -> None:
        # Stretches look like A, B, A, A; the shots are A, B, A.
        costs = [[0, 9, 0], [9, 0, 9], [0, 9, 0], [1, 9, 1]]
        self.assertEqual(assign(costs, 3), [0, 1, 2, 2])

    def test_too_few_stretches_cannot_be_assigned(self) -> None:
        self.assertIsNone(assign([[0, 1]], 2))

    def test_requested_cuts_fall_on_multiples_of_eight(self) -> None:
        self.assertEqual(requested_cuts([5, 6, 4], 24), [0, 120, 264])


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class DecideTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)

    def test_content_matching_handles_an_extra_cut_and_a_returning_shot(self) -> None:
        # The model cut at 48, 96 and an extra 120; the last shot returns to A.
        block = clip(self.base / "b1.mp4", [("red", 48), ("blue", 48), ("red", 24), ("0xB00000", 24)])
        refs = [picture(self.base / "a.png", "red"), picture(self.base / "b.png", "blue"), self.base / "a.png"]
        slicing = decide(block, [2, 2, 2], refs, FPS)
        self.assertEqual(slicing.method, "content")
        self.assertEqual(slicing.starts, [0, 48, 96])

    def test_without_pictures_one_cut_per_shot_is_trusted(self) -> None:
        block = clip(self.base / "b1.mp4", [("red", 50), ("blue", 46)])
        slicing = decide(block, [2, 2], [None, None], FPS)
        self.assertEqual((slicing.method, slicing.starts), ("detected", [0, 50]))

    def test_without_pictures_an_ambiguous_clip_falls_back_to_the_request(self) -> None:
        block = clip(self.base / "b1.mp4", [("red", 30), ("blue", 30), ("green", 36)])
        slicing = decide(block, [2, 2], [None, None], FPS)
        self.assertEqual((slicing.method, slicing.starts), ("requested", [0, 48]))
        self.assertIn("3 stretches for 2 shots", slicing.note)


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class SliceJobTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        self.addCleanup(self._restore)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        text = scene.read_text(encoding="utf-8")
        for number in ("1", "2"):
            text = text.replace(f"  - n: {number}\n", f"  - n: {number}\n    block: A\n", 1)
        scene.write_text(text, encoding="utf-8")
        work = self.root / "scenes" / "030-echo-chamber" / "work"
        clip(work / "bA.mp4", [("red", 50), ("blue", 94)])
        self.work = work
        self.manager = JobManager(store=JobStore(base / "state" / "jobs.sqlite"))
        self.addCleanup(self.manager.shutdown, wait=False)

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_the_scene_knows_its_blocks(self) -> None:
        blocks = load_scene(self.root, "SC-030")["blocks"]
        self.assertEqual([(b["id"], b["shots"], b["clip"].endswith("work/bA.mp4")) for b in blocks], [("A", ["P1", "P2"], True)])

    def test_slices_become_takes_with_their_lineage(self) -> None:
        job = self.manager.wait(self.manager.submit("slice_block", self.root, {"scene": "SC-030", "block": "A"})["id"], timeout=120)
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.manager.adopt(job["id"])
        shots = {shot["id"]: shot for shot in load_scene(self.root, "SC-030")["shots"]}
        take = next(item for item in shots["P2"]["takes"] if item["id"] == "BLOCK-A")
        self.assertEqual(take["provenance"]["block"], "A")
        self.assertEqual(take["provenance"]["frames"][0], 50)
        self.assertEqual(take["provenance"]["method"], "detected")
        # The existing take is untouched, and a second slicing makes a new take.
        self.assertIn("CUT", [item["id"] for item in shots["P2"]["takes"]])
        again = self.manager.wait(self.manager.submit("slice_block", self.root, {"scene": "SC-030", "block": "A"})["id"], timeout=120)
        self.manager.adopt(again["id"])
        ids = [item["id"] for item in load_scene(self.root, "SC-030")["shots"][1]["takes"]]
        self.assertIn("BLOCK-A-2", ids)

    def test_a_block_that_is_not_consecutive_is_reported(self) -> None:
        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        text = scene.read_text(encoding="utf-8").replace("  - n: 2\n    block: A\n", "  - n: 2\n", 1)
        text = text.replace("  - n: 3\n", "  - n: 3\n    block: A\n", 1)
        scene.write_text(text, encoding="utf-8")
        codes = [finding["code"] for finding in load_scene(self.root, "SC-030")["findings"]]
        self.assertIn("block_not_contiguous", codes)


if __name__ == "__main__":
    unittest.main()
