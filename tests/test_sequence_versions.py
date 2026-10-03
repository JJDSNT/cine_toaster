"""A sequence is assembled from its scenes' versions, and kept as versions too."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.commands import Actor, review_assembly, review_sequence_version
from cine_toaster.errors import ValidationError
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.project import load_production

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class SequenceVersionTests(unittest.TestCase):
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

    def run_job(self, kind: str, params: dict) -> dict:
        job = self.manager.wait(self.manager.submit(kind, self.root, params)["id"], timeout=120)
        self.assertEqual(job["state"], "succeeded", job["error"])
        return self.manager.adopt(job["id"])

    def sequence(self) -> dict:
        return next(item for item in load_production(self.root)["sequences"] if item["id"] == "the-reply")

    def test_nothing_to_assemble_is_refused_up_front(self) -> None:
        with self.assertRaises(ValidationError):
            self.manager.submit("assemble_sequence", self.root, {"sequence": "the-reply"})

    def test_the_approved_scene_version_is_used_and_the_result_is_kept(self) -> None:
        self.run_job("assemble", {"scene": "SC-030"})
        self.run_job("assemble", {"scene": "SC-030"})
        review_assembly(self.root, scene_id="SC-030", assembly_id="v1", verdict="approved", actor=Actor(id="director"))
        job = self.run_job("assemble_sequence", {"sequence": "the-reply"})
        self.assertEqual(job["result"]["summary"]["scenes"], {"SC-030": "v1"})
        self.assertTrue(any("SC-010" in note for note in job["result"]["summary"]["notes"]))
        version = self.sequence()["versions"][0]
        self.assertEqual((version["id"], version["media"]), ("v1", "sequences/the-reply/versions/v1.mp4"))
        self.assertTrue((self.root / version["media"]).is_file())
        self.assertTrue((self.root / "sequences.state.json").is_file())

    def test_a_verdict_is_recorded_on_the_version(self) -> None:
        self.run_job("assemble", {"scene": "SC-030"})
        self.run_job("assemble_sequence", {"sequence": "the-reply"})
        review_sequence_version(self.root, sequence_id="the-reply", version_id="v1", verdict="approved",
                                actor=Actor(id="director"), note="The reply lands.")
        version = self.sequence()["versions"][0]
        self.assertEqual((version["verdict"], version["note"]), ("approved", "The reply lands."))
        with self.assertRaises(ValidationError):
            review_sequence_version(self.root, sequence_id="the-reply", version_id="v1", verdict="great",
                                    actor=Actor(id="director"))


if __name__ == "__main__":
    unittest.main()
