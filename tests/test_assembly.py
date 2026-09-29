"""A scene assembled from its chosen takes becomes a kept version (fase de produção)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.assembly import _trim, plan_scene
from cine_toaster.commands import Actor, select_take
from cine_toaster.errors import ValidationError
from cine_toaster.jobs import JobError, JobManager, JobStore
from cine_toaster.project import load_scene

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class TrimTests(unittest.TestCase):
    def test_in_and_out(self) -> None:
        self.assertEqual(_trim({"in": 1.0, "out": 3.5}, 10.0, 0)[:2], (1.0, 3.5))

    def test_head_and_tail(self) -> None:
        self.assertEqual(_trim({"head": 0.5, "tail": 1.0}, 10.0, 0)[:2], (0.5, 9.0))

    def test_without_a_trim_the_shot_duration_is_used(self) -> None:
        self.assertEqual(_trim(None, 10.0, 4.0)[:2], (0.0, 4.0))

    def test_a_cut_past_the_take_is_clamped_and_noted(self) -> None:
        start, end, note = _trim(None, 1.0, 6.0)
        self.assertEqual((start, end), (0.0, 1.0))
        self.assertIn("past the end", note)

    def test_a_cut_that_leaves_nothing_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            _trim({"in": 2.0, "out": 2.0}, 5.0, 0)


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class AssemblyTests(unittest.TestCase):
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
        self.manager = JobManager(store=JobStore(base / "state" / "jobs.sqlite"))
        self.addCleanup(self.manager.shutdown, wait=False)

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def scene(self) -> dict:
        return load_scene(self.root, "SC-030")

    def test_the_plan_uses_the_selected_take_or_the_current_one(self) -> None:
        select_take(self.root, scene_id="SC-030", shot_id="P3", take_id="ONE-BLINK", actor=Actor(id="editor"))
        plan = plan_scene(self.root, self.scene())
        self.assertEqual(plan.takes, {"P1": "CUT", "P2": "CUT", "P3": "ONE-BLINK"})
        self.assertTrue(any("J-cut is rendered as a straight cut" in note for note in plan.notes))

    def test_an_adopted_assembly_is_a_kept_version_with_its_takes(self) -> None:
        select_take(self.root, scene_id="SC-030", shot_id="P3", take_id="ONE-BLINK", actor=Actor(id="editor"))
        job = self.manager.wait(self.manager.submit("assemble", self.root, {"scene": "SC-030"})["id"], timeout=120)
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.assertEqual(job["params"]["version"], "v1")
        self.manager.adopt(job["id"])
        versions = {item["id"]: item for item in self.scene()["assemblies"]}
        self.assertEqual(versions["v1"]["media"], "renders/assemblies/SC-030/v1.mp4")
        self.assertEqual(versions["v1"]["takes"]["P3"], "ONE-BLINK")
        self.assertTrue((self.root / versions["v1"]["media"]).is_file())
        # The next assembly is the next version; an existing one is never replaced.
        second = self.manager.submit("assemble", self.root, {"scene": "SC-030"})
        self.assertEqual(second["params"]["version"], "v2")
        with self.assertRaises(ValidationError):
            self.manager.submit("assemble", self.root, {"scene": "SC-030", "version": "v1"})

    def test_a_version_file_is_never_overwritten(self) -> None:
        job = self.manager.wait(self.manager.submit("assemble", self.root, {"scene": "SC-030", "version": "cut-a"})["id"], timeout=120)
        target = self.root / "renders" / "assemblies" / "SC-030" / "cut-a.mp4"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"someone's render")
        with self.assertRaises(JobError):
            self.manager.adopt(job["id"])
        self.assertEqual(target.read_bytes(), b"someone's render")


if __name__ == "__main__":
    unittest.main()
