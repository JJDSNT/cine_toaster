"""A scene assembled from its chosen takes becomes a kept version (fase de produção)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.assembly import _cut, _speaks, _trim, plan_scene, words_for
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


class SpeechCutTests(unittest.TestCase):
    """Rules reimplemented from SINGULAR's montage; its own cuts matched on 20 of 21 shots (CT-0039)."""

    WORDS = [(1.8, 2.2), (2.3, 3.1)]

    def test_speech_is_kept_whole_with_air_around_it(self) -> None:
        self.assertEqual(_cut({}, 8.0, 3.0, self.WORDS, 0.35)[:3], (0.8, 4.0, "speech"))

    def test_the_opening_is_never_used_even_before_early_speech(self) -> None:
        self.assertEqual(_cut({}, 8.0, 3.0, [(0.5, 1.0)], 0.35)[:2], (0.35, 1.9))

    def test_declared_margins_win(self) -> None:
        self.assertEqual(_cut({"before": 0.4, "after": 0.2}, 8.0, 3.0, self.WORDS, 0.35)[:2], (1.4, 3.3))

    def test_an_explicit_in_keeps_the_words_for_the_end(self) -> None:
        self.assertEqual(_cut({"in": 0.0}, 8.0, 3.0, self.WORDS, 0.35)[:3], (0.0, 4.0, "trim+speech"))

    def test_a_silent_take_uses_its_duration_after_the_opening(self) -> None:
        self.assertEqual(_cut({}, 8.0, 3.0, [], 0.35)[:3], (0.35, 3.35, "duration"))

    def test_a_line_added_in_the_mix_is_not_spoken_in_the_take(self) -> None:
        self.assertFalse(_speaks({"lines": [{"who": "LIRA", "in_take": False}]}))
        self.assertTrue(_speaks({"lines": [{"who": "LIRA", "in_take": True}]}))

    def test_word_timings_are_read_from_a_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            take = Path(raw) / "c08.mp4"
            (Path(raw) / "c08.palavras.json").write_text("[[1.0, 1.5, \" Hello\"], [0.2, 0.4, \" Oh\"]]", encoding="utf-8")
            self.assertEqual(words_for(take, "{stem}.palavras.json"), [(0.2, 0.4), (1.0, 1.5)])
            self.assertEqual(words_for(take, "{stem}.words.json"), [])


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
        # SC-030 P3 is a J-cut: its sound will lead the picture by the default split.
        self.assertEqual((plan.segments[2].join, plan.segments[2].split), ("j", 0.8))

    def test_an_adopted_assembly_is_a_kept_version_with_its_takes(self) -> None:
        select_take(self.root, scene_id="SC-030", shot_id="P3", take_id="ONE-BLINK", actor=Actor(id="editor"))
        job = self.manager.wait(self.manager.submit("assemble", self.root, {"scene": "SC-030"})["id"], timeout=120)
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.assertEqual(job["params"]["version"], "v1")
        self.manager.adopt(job["id"])
        versions = {item["id"]: item for item in self.scene()["assemblies"]}
        self.assertEqual(versions["v1"]["media"], "scenes/030-echo-chamber/versions/v1.mp4")
        self.assertEqual(versions["v1"]["takes"]["P3"], "ONE-BLINK")
        self.assertTrue((self.root / versions["v1"]["media"]).is_file())
        # Beside it, the breakdown that made it and the index a person reads (ADR 0021).
        folder = self.root / "scenes" / "030-echo-chamber" / "versions"
        self.assertEqual((folder / "v1.scene.yaml").read_text(encoding="utf-8"),
                         (self.root / "scenes" / "030-echo-chamber" / "scene.yaml").read_text(encoding="utf-8"))
        index = (folder / "VERSIONS.md").read_text(encoding="utf-8")
        self.assertIn("| [v1](v1.mp4) |", index)
        from cine_toaster.commands import review_assembly

        review_assembly(self.root, scene_id="SC-030", assembly_id="v1", verdict="approved", note="the blink works",
                        actor=Actor(id="director"))
        index = (folder / "VERSIONS.md").read_text(encoding="utf-8")
        self.assertIn("Approved: **v1**", index)
        self.assertIn("✅ approved | the blink works |", index)
        # The next assembly is the next version; an existing one is never replaced.
        second = self.manager.submit("assemble", self.root, {"scene": "SC-030"})
        self.assertEqual(second["params"]["version"], "v2")
        with self.assertRaises(ValidationError):
            self.manager.submit("assemble", self.root, {"scene": "SC-030", "version": "v1"})

    def test_a_version_file_is_never_overwritten(self) -> None:
        job = self.manager.wait(self.manager.submit("assemble", self.root, {"scene": "SC-030", "version": "cut-a"})["id"], timeout=120)
        target = self.root / "scenes" / "030-echo-chamber" / "versions" / "cut-a.mp4"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"someone's render")
        with self.assertRaises(JobError):
            self.manager.adopt(job["id"])
        self.assertEqual(target.read_bytes(), b"someone's render")


if __name__ == "__main__":
    unittest.main()
