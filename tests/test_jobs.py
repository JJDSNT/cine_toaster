"""Jobs outlive the interface that started them (SPEC-0008)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from cine_toaster.application import ProjectManager
from cine_toaster.errors import ValidationError
from cine_toaster.events import tail_events
from cine_toaster.jobs import KINDS, JobError, JobKind, JobManager, JobStore, register

EXAMPLES = Path(__file__).parents[1] / "examples"
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _any(root: Path, params: dict) -> dict:
    return params


def _steps(context) -> dict:
    """A job that takes its time and checks for cancellation as it goes."""

    for step in range(int(context.params.get("steps", 5))):
        context.progress(step / 5, f"step {step}")
        time.sleep(float(context.params.get("pause", 0.05)))
    (context.staging / "out.txt").write_text("made by a job", encoding="utf-8")
    return {"files": [{"staged": "out.txt", "destination": context.params.get("destination", "renders/out.txt")}]}


def _process(context) -> dict:
    """A job whose work is an external process, as an FFmpeg job's is."""

    context.run_process([sys.executable, "-c", "import time; time.sleep(30)", str(context.staging)])
    return {"files": []}


def _boom(context) -> dict:
    raise RuntimeError("the render exploded")


for kind in (JobKind("test-steps", _any, _steps), JobKind("test-process", _any, _process), JobKind("test-boom", _any, _boom)):
    register(kind)


class JobTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        base = Path(self.directory.name)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        self.addCleanup(self._restore)
        self.film = base / "the-last-signal"
        shutil.copytree(EXAMPLES / "demo-project", self.film)
        self.reel = base / "amiga"
        shutil.copytree(EXAMPLES / "amiga-demo-reel", self.reel)
        self.store = JobStore(base / "state" / "jobs.sqlite")
        self.manager = self.runtime()

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def runtime(self, **options) -> JobManager:
        manager = JobManager(store=self.store, **options)
        self.addCleanup(manager.shutdown, wait=False)
        return manager

    def finish(self, job: dict, manager: JobManager | None = None) -> dict:
        return (manager or self.manager).wait(job["id"], timeout=60)


class LifecycleTests(JobTestCase):
    def test_a_job_runs_stages_and_reports(self) -> None:
        job = self.finish(self.manager.submit("test-steps", self.film))
        self.assertEqual((job["state"], job["progress"]), ("succeeded", 1.0))
        self.assertTrue((self.manager.staging_dir(job["id"]) / "out.txt").is_file())
        # Staged, not adopted: nothing has been written into the production.
        self.assertFalse((self.film / "renders" / "out.txt").exists())
        types = [event["type"] for event in tail_events(self.film)]
        self.assertEqual([t for t in types if t != "job.progress"], ["job.queued", "job.started", "job.succeeded"])

    def test_a_failure_is_recorded_not_raised(self) -> None:
        job = self.finish(self.manager.submit("test-boom", self.film))
        self.assertEqual(job["state"], "failed")
        self.assertIn("exploded", job["error"])

    def test_an_unknown_kind_is_refused_before_anything_is_queued(self) -> None:
        with self.assertRaises(ValidationError):
            self.manager.submit("nonsense", self.film)
        self.assertEqual(self.manager.list(), [])


class AdoptionTests(JobTestCase):
    def test_adoption_is_the_only_write_into_the_project(self) -> None:
        job = self.finish(self.manager.submit("test-steps", self.film))
        adopted = self.manager.adopt(job["id"])
        self.assertIsNotNone(adopted["adopted_at"])
        self.assertEqual((self.film / "renders" / "out.txt").read_text(encoding="utf-8"), "made by a job")
        self.assertIn("job.adopted", [event["type"] for event in tail_events(self.film)])

    def test_adoption_never_overwrites_unless_told(self) -> None:
        (self.film / "renders").mkdir()
        (self.film / "renders" / "out.txt").write_text("the editor's file", encoding="utf-8")
        job = self.finish(self.manager.submit("test-steps", self.film))
        with self.assertRaises(JobError):
            self.manager.adopt(job["id"])
        self.assertEqual((self.film / "renders" / "out.txt").read_text(encoding="utf-8"), "the editor's file")
        self.manager.adopt(job["id"], overwrite=True)
        self.assertEqual((self.film / "renders" / "out.txt").read_text(encoding="utf-8"), "made by a job")

    def test_a_declared_destination_stays_inside_the_project(self) -> None:
        job = self.finish(self.manager.submit("test-steps", self.film, {"destination": "../escaped.txt"}))
        with self.assertRaises(ValueError):
            self.manager.adopt(job["id"])
        self.assertFalse((self.film.parent / "escaped.txt").exists())

    def test_only_a_succeeded_job_is_adopted(self) -> None:
        job = self.finish(self.manager.submit("test-boom", self.film))
        with self.assertRaises(JobError):
            self.manager.adopt(job["id"])


class CancellationTests(JobTestCase):
    def test_cancelling_stops_the_external_process(self) -> None:
        job = self.manager.submit("test-process", self.film)
        pid = None
        for _ in range(100):
            pid = self.store.get(job["id"])["process_pid"]
            if pid:
                break
            time.sleep(0.05)
        self.assertIsNotNone(pid)
        self.manager.cancel(job["id"])
        self.assertEqual(self.finish(job)["state"], "cancelled")
        time.sleep(0.2)
        self.assertFalse(Path(f"/proc/{pid}").exists() and "sleep" in Path(f"/proc/{pid}/cmdline").read_text(errors="ignore"))

    def test_another_runtime_can_ask_a_job_to_stop(self) -> None:
        job = self.manager.submit("test-steps", self.film, {"steps": 100, "pause": 0.05})
        other = self.runtime(reconcile=False)
        time.sleep(0.2)
        other.cancel(job["id"])
        self.assertEqual(self.finish(job)["state"], "cancelled")

    def test_a_queued_job_is_cancelled_before_it_starts(self) -> None:
        manager = self.runtime(max_workers=1)
        blocker = manager.submit("test-steps", self.film, {"steps": 20, "pause": 0.05})
        waiting = manager.submit("test-steps", self.film)
        manager.cancel(waiting["id"])
        self.assertEqual(self.finish(waiting, manager)["message"], "Cancelled before it started.")
        self.assertEqual(self.finish(blocker, manager)["state"], "succeeded")

    def test_a_finished_job_cannot_be_cancelled(self) -> None:
        job = self.finish(self.manager.submit("test-steps", self.film))
        with self.assertRaises(JobError):
            self.manager.cancel(job["id"])

    def test_retry_starts_a_new_attempt(self) -> None:
        failed = self.finish(self.manager.submit("test-boom", self.film))
        again = self.manager.retry(failed["id"])
        self.assertEqual((again["attempt"], again["retry_of"]), (2, failed["id"]))
        self.assertNotEqual(again["id"], failed["id"])


class ReconcileTests(JobTestCase):
    def dead_pid(self) -> int:
        process = subprocess.Popen([sys.executable, "-c", "pass"])
        process.wait()
        return process.pid

    def orphan_job(self, *, runtime_pid: int, heartbeat: float, process: subprocess.Popen | None = None) -> str:
        job_id = f"job_test{len(self.store.list()):04d}"
        self.store.insert({
            "id": job_id, "kind": "test-steps", "project_id": "the-last-signal", "project_root": str(self.film),
            "params": {}, "state": "running", "progress": 0.4, "message": "", "attempt": 1,
            "runtime_id": "rt_elsewhere", "runtime_pid": runtime_pid,
            "process_pid": process.pid if process else None, "cancel_requested": False,
            "created_at": "2026-09-29T00:00:00+00:00", "heartbeat_at": heartbeat,
        })
        return job_id

    def test_work_whose_runtime_died_is_interrupted_and_its_orphan_stopped(self) -> None:
        staging = self.store.path.parent / "jobs" / "job_test0000"
        staging.mkdir(parents=True)
        orphan = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", str(staging)])
        self.addCleanup(lambda: (orphan.kill(), orphan.wait()))
        job_id = self.orphan_job(runtime_pid=self.dead_pid(), heartbeat=time.time(), process=orphan)
        restarted = self.runtime()
        self.assertEqual([job["id"] for job in restarted.reconciled], [job_id])
        job = self.store.get(job_id)
        self.assertEqual(job["state"], "interrupted")
        self.assertIn("orphaned process", job["message"])
        self.assertEqual(orphan.wait(timeout=5), -15)

    def test_a_process_that_is_not_the_jobs_own_is_left_alone(self) -> None:
        stranger = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(lambda: (stranger.kill(), stranger.wait()))
        self.orphan_job(runtime_pid=self.dead_pid(), heartbeat=time.time(), process=stranger)
        self.runtime()
        self.assertIsNone(stranger.poll())

    def test_a_live_runtime_keeps_its_jobs(self) -> None:
        job_id = self.orphan_job(runtime_pid=os.getpid(), heartbeat=time.time())
        self.runtime()
        self.assertEqual(self.store.get(job_id)["state"], "running")

    def test_a_silent_runtime_loses_its_jobs(self) -> None:
        job_id = self.orphan_job(runtime_pid=os.getpid(), heartbeat=time.time() - 600)
        self.runtime()
        self.assertEqual(self.store.get(job_id)["state"], "interrupted")


class IsolationTests(JobTestCase):
    def test_a_job_finishes_while_another_project_is_active_and_its_own_is_closed(self) -> None:
        projects = ProjectManager()
        film = projects.open_project(self.film)
        job = self.manager.submit("test-steps", self.film, {"steps": 10, "pause": 0.05})
        projects.open_project(self.reel)
        projects.close_project(film.project_id)
        other = self.manager.submit("test-steps", self.reel)
        self.assertEqual(self.finish(job)["state"], "succeeded")
        self.assertEqual(self.finish(other)["state"], "succeeded")
        self.assertEqual([j["id"] for j in self.manager.list(project_id="the-last-signal")], [job["id"]])
        self.assertEqual([j["id"] for j in self.manager.list(project_id=other["project_id"])], [other["id"]])


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg is missing")
class PrevisJobTests(JobTestCase):
    def test_the_previs_job_renders_and_adopts(self) -> None:
        job = self.finish(self.manager.submit("previs", self.film, {"scene": "SC-030", "shot": "P2"}))
        if job["state"] == "failed" and "librsvg" in (job["error"] or "").lower() + "svg":
            self.skipTest("this FFmpeg cannot read SVG")
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.manager.adopt(job["id"])
        self.assertTrue((self.film / "renders" / "previs" / "SC-030-P2.mp4").is_file())

    def test_a_shot_without_a_camera_is_refused_up_front(self) -> None:
        with self.assertRaises(ValidationError):
            self.manager.submit("previs", self.film, {"scene": "SC-010", "shot": "P1"})


if __name__ == "__main__":
    unittest.main()
