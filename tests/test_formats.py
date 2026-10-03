"""A format's rules on the cut: its aspect, and burned-in captions (CT-0049)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cine_toaster.formats import groups, ratio, reframe_filter, spread, target_size

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


class RuleTests(unittest.TestCase):
    def test_sizes_and_windows(self) -> None:
        self.assertEqual((ratio("9:16"), ratio("2.39:1"), ratio("nonsense")), (0.5625, 2.39, None))
        self.assertEqual(target_size(1280, 720, "9:16"), (720, 1280))
        self.assertEqual(target_size(1280, 720, "16:9"), (1280, 720))
        self.assertEqual(target_size(1280, 720, "2.39:1"), (1280, 536))
        # A 9:16 window of a 16:9 take, pushed to the right edge, never past it.
        self.assertEqual(reframe_filter(1280, 720, (720, 1280), x=1.0), "crop=404:720:876:0,scale=720:1280,setsar=1")

    def test_captions_are_short_and_break_at_pauses(self) -> None:
        words = [(0.0, 0.3, "That's"), (0.3, 0.5, "it."), (1.5, 1.8, "That's"), (1.8, 2.0, "my"), (2.0, 2.2, "own"),
                 (2.2, 2.5, "voice"), (2.5, 2.8, "again")]
        self.assertEqual([text for _, _, text in groups(words)], ["That's it.", "That's my own voice", "again"])
        self.assertEqual(len(spread("one two three four five six", 0.0, 3.0)), 2)


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class CutTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def run_process(self, command, expected_seconds=None, message="", span=None):
        subprocess.run(command, check=True, capture_output=True)

    def test_a_vertical_version_reframes_the_takes_and_burns_the_captions(self) -> None:
        from cine_toaster.assembly import Plan, Segment, probe, render

        # A wide take: red on the left half, blue on the right.
        take = self.root / "take.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=red:s=160x90:r=24:d=3",
                        "-f", "lavfi", "-i", "color=blue:s=160x90:r=24:d=3", "-f", "lavfi", "-i", "anullsrc=r=48000",
                        "-filter_complex", "[0:v]crop=80:90:0:0[l];[1:v]crop=80:90:0:0[r];[l][r]hstack[v]",
                        "-map", "[v]", "-map", "2:a", "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(take)],
                       check=True)
        (self.root / "take.words.json").write_text(json.dumps(
            [{"start": 0.5, "end": 0.9, "word": "Hello"}, {"start": 0.9, "end": 1.4, "word": "there"}]))
        segment = Segment("P1", "A", "take.mp4", 0.0, 3.0, normalize=False, reframe={"x": 0.9},
                          captions=groups([(0.5, 0.9, "Hello"), (0.9, 1.4, "there")]))
        plan = Plan(scene="SC-1", segments=[segment], format={"aspect": "9:16", "captions": True})
        out = self.root / "vertical.mp4"
        render(self.root, plan, out, self.root / "work", self.run_process)
        info = probe(out)
        self.assertEqual((info["width"], info["height"]), (90, 160))
        self.assertTrue((self.root / "take.mp4").is_file())  # the take itself is untouched

        def pixel(at: float, x: int, y: int) -> tuple[int, int, int]:
            raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(at), "-i", str(out), "-frames:v", "1",
                                  "-vf", f"format=rgb24,crop=1:1:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 capture_output=True).stdout
            return raw[0], raw[1], raw[2]

        self.assertGreater(pixel(2.5, 45, 20)[2], 150)  # reframed to the right: blue
        # The caption is white text in the lower part while it is spoken, and gone after.
        def brightest(at: float) -> int:
            raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(at), "-i", str(out), "-frames:v", "1",
                                  "-vf", "crop=90:50:0:100,format=gray", "-f", "rawvideo", "-"],
                                 capture_output=True).stdout
            return max(raw)
        self.assertGreater(brightest(1.0), 200)
        self.assertLess(brightest(2.6), 120)


DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class DeliveryTests(unittest.TestCase):
    """One cut, delivered in several formats at once."""

    def setUp(self) -> None:
        import os

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"], os.environ["XDG_STATE_HOME"] = str(base / "cache"), str(base / "state")
        self.addCleanup(self._restore)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)

    def _restore(self) -> None:
        import os

        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_a_version_is_delivered_in_every_format_it_names(self) -> None:
        from cine_toaster.assembly import probe
        from cine_toaster.jobs import JobManager, JobStore
        from cine_toaster.project import load_scene

        manifest = self.root / "project.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8")
                            + '\ndeliver: [TikTok, {name: square, aspect: "1:1"}]\n', encoding="utf-8")
        scene = load_scene(self.root, "SC-030")
        self.assertEqual([(item["id"], item["aspect"], item["captions"]) for item in scene["deliver"]],
                         [("viral-vertical", "9:16", True), ("square", "1:1", False)])
        manager = JobManager(store=JobStore(self.root.parent / "state" / "jobs.sqlite"))
        self.addCleanup(manager.shutdown, wait=False)
        job = manager.wait(manager.submit("assemble", self.root, {"scene": "SC-030"})["id"], timeout=300)
        self.assertEqual(job["state"], "succeeded", job["error"])
        manager.adopt(job["id"])
        version = load_scene(self.root, "SC-030")["assemblies"][0]
        self.assertEqual(set(version["renditions"]), {"viral-vertical", "square"})
        main = probe(self.root / version["media"])
        vertical = probe(self.root / version["renditions"]["viral-vertical"])
        square = probe(self.root / version["renditions"]["square"])
        self.assertGreater(main["width"], main["height"])
        self.assertLess(vertical["width"], vertical["height"])
        self.assertEqual(square["width"], square["height"])
        self.assertAlmostEqual(vertical["duration"], main["duration"], delta=0.1)

    def test_the_window_follows_the_shots_subject_on_the_plan(self) -> None:
        from cine_toaster.assembly import plan_scene
        from cine_toaster.formats import subject_window
        from cine_toaster.project import load_scene

        scene = load_scene(self.root, "SC-030")
        shots = {shot["id"]: shot for shot in scene["shots"]}
        window, note = subject_window(scene, shots["P3"])
        self.assertEqual((window["subject"], window["x"]), ("MARA", 0.5))
        self.assertIn("reframed on Mara Vale", note)
        # P2 made to follow the stack, which stands at the left edge of its frame.
        window, _ = subject_window(scene, {**shots["P2"], "subject": "SPEAKER"})
        self.assertLess(window["x"], 0.1)
        # The cut uses it when a format asks for a frame, and a hand-set reframe wins.
        manifest = self.root / "project.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8") + "\nstyle: TikTok\n", encoding="utf-8")
        scene_file = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene_file.write_text(scene_file.read_text(encoding="utf-8").replace(
            "  - n: 2\n", "  - n: 2\n    reframe: {x: 0.8}\n", 1), encoding="utf-8")
        plan = plan_scene(self.root, load_scene(self.root, "SC-030"))
        frames = {segment.shot: segment.reframe for segment in plan.segments}
        self.assertEqual(frames["P2"], {"x": 0.8})
        self.assertEqual(frames["P3"]["from"], "plan")

    def test_a_sequence_is_delivered_from_its_scenes_renditions(self) -> None:
        from cine_toaster.assembly import probe
        from cine_toaster.commands import Actor, record_assembly
        from cine_toaster.jobs import JobManager, JobStore
        from cine_toaster.project import load_production

        manifest = self.root / "project.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8") + '\ndeliver: [{name: square, aspect: "1:1"}]\n',
                            encoding="utf-8")
        renders = self.root / "renders"
        renders.mkdir()
        for name, size in (("SC-010", "160x90"), ("SC-030", "160x90"), ("SC-030.square", "90x90")):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=gray:s={size}:r=24:d=2",
                            "-f", "lavfi", "-i", "anullsrc=r=48000", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", str(renders / f"{name}.mp4")], check=True)
        record_assembly(self.root, scene_id="SC-010", assembly_id="v1", actor=Actor(id="editor"),
                        media="renders/SC-010.mp4", duration_seconds=2.0, takes={})
        record_assembly(self.root, scene_id="SC-030", assembly_id="v1", actor=Actor(id="editor"),
                        media="renders/SC-030.mp4", duration_seconds=2.0, takes={},
                        renditions={"square": "renders/SC-030.square.mp4"})
        manager = JobManager(store=JobStore(self.root.parent / "state" / "jobs.sqlite"))
        self.addCleanup(manager.shutdown, wait=False)
        job = manager.wait(manager.submit("assemble_sequence", self.root, {"sequence": "the-reply"})["id"], timeout=300)
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.assertTrue(any("SC-010's version v1 has no square rendition" in note
                            for note in job["result"]["summary"]["notes"]))
        manager.adopt(job["id"])
        version = next(item for item in load_production(self.root)["sequences"] if item["id"] == "the-reply")["versions"][0]
        square = probe(self.root / version["renditions"]["square"])
        self.assertEqual(square["width"], square["height"])

    def test_a_rendition_that_is_not_a_format_is_said(self) -> None:
        from cine_toaster.project import load_scene

        scene_file = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene_file.write_text(scene_file.read_text(encoding="utf-8").replace(
            "shots:\n", 'deliver: [noir, {aspect: "wide"}]\nshots:\n', 1), encoding="utf-8")
        messages = [f["message"] for f in load_scene(self.root, "SC-030")["findings"] if f["code"] == "deliver_problem"]
        self.assertEqual(len(messages), 2)


if __name__ == "__main__":
    unittest.main()
