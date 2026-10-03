"""Joins in an assembly: transitions from the catalog, and J/L-cuts with the takes' handles (SPEC-0007)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cine_toaster.assembly import Plan, Segment, probe, render

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run(command, expected_seconds=None, message="", span=None):
    subprocess.run(command, check=True, capture_output=True)


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class JoinTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def take(self, name: str, colour: str, sound: str) -> str:
        """A 4 s take at 24 fps: a flat colour, and the given audio expression."""

        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color={colour}:s=160x90:r=24:d=4",
                        "-f", "lavfi", "-i", f"aevalsrc='{sound}':s=48000:d=4", "-c:v", "libx264", "-pix_fmt",
                        "yuv420p", "-c:a", "aac", "-shortest", str(self.root / name)], check=True)
        return name

    def plan(self, second: Segment) -> Plan:
        first = Segment("P1", "A", self.take("a.mp4", "red", "0"), 1.0, 3.0, normalize=False)
        return Plan(scene="SC-1", segments=[first, second])

    def mean(self, path: Path, start: float, length: float) -> float:
        completed = subprocess.run(["ffmpeg", "-hide_banner", "-ss", str(start), "-t", str(length), "-i", str(path),
                                    "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
        return float(completed.stderr.split("mean_volume: ")[1].split(" dB")[0])

    def colour(self, path: Path, at: float) -> tuple[int, int, int]:
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1",
                              "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        return raw[0], raw[1], raw[2]

    def test_a_transition_takes_its_length_from_both_shots_and_mixes_them(self) -> None:
        for transition in ({"id": "cross-dissolve", "seconds": 0.5, "mode": "fade"},
                           {"id": "cross-dissolve", "seconds": 0.5, "shader": str(self.shader())}):
            with self.subTest(engine="shader" if "shader" in transition else "ffmpeg"):
                second = Segment("P2", "B", self.take("b.mp4", "blue", "0"), 1.0, 3.0, normalize=False,
                                 transition=transition)
                plan = self.plan(second)
                out = self.root / "cut.mp4"
                render(self.root, plan, out, self.root / "work", run)
                self.assertEqual(plan.duration, 3.5)
                self.assertAlmostEqual(probe(out)["duration"], 3.5, delta=0.1)
                red, _, blue = self.colour(out, 1.75)  # the middle of the dissolve
                self.assertTrue(40 < red < 215 and 40 < blue < 215, (red, blue))
                self.assertGreater(self.colour(out, 0.5)[0], 200)
                self.assertGreater(self.colour(out, 3.2)[2], 200)

    def shader(self) -> Path:
        from cine_toaster.transitions import list_transitions

        return next(item["asset_path"] for item in list_transitions() if item["id"] == "cross-dissolve")

    def test_a_j_cut_leads_with_the_incoming_takes_sound_from_before_its_cut_point(self) -> None:
        # B speaks (a tone) from 0.4 s to 0.9 s of its take, before its picture starts at 1.0 s.
        tone = "0.5*sin(2*PI*440*t)*between(t,0.4,0.9)"
        second = Segment("P2", "B", self.take("b.mp4", "blue", tone), 1.0, 3.0, join="j", normalize=False, split=0.8)
        plan = self.plan(second)
        out = self.root / "cut.mp4"
        render(self.root, plan, out, self.root / "work", run)
        self.assertEqual(plan.notes, [])
        # The cut is at 2.0 s; B's sound starts 0.8 s before it, so its tone is heard at 1.2-1.7 s, over A's picture.
        self.assertGreater(self.mean(out, 1.3, 0.3), -30)
        self.assertGreater(self.colour(out, 1.4)[0], 200)  # still A on screen
        self.assertLess(self.mean(out, 0.3, 0.6), -60)

    def test_an_l_cut_lets_the_outgoing_sound_run_on_and_a_short_handle_is_said(self) -> None:
        tone = "0.5*sin(2*PI*440*t)*gt(t,3.0)"  # A's sound after its picture ends at 3.0 s
        first = Segment("P1", "A", self.take("a.mp4", "red", tone), 1.0, 3.0, normalize=False)
        second = Segment("P2", "B", self.take("b.mp4", "blue", "0"), 1.0, 3.0, join="l", normalize=False, split=1.5)
        plan = Plan(scene="SC-1", segments=[first, second])
        out = self.root / "cut.mp4"
        render(self.root, plan, out, self.root / "work", run)
        self.assertGreater(self.mean(out, 2.2, 0.5), -30)  # A's sound over B's picture
        self.assertGreater(self.colour(out, 2.4)[2], 200)
        # A's take has 1.0 s of sound beyond its cut point, so a 1.5 s split is shortened, and said.
        self.assertEqual(second.split, 1.0)
        self.assertTrue(any("runs 1.00 s across the cut, not 1.50" in note for note in plan.notes))


DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class PlannedJoinTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "film"
        shutil.copytree(DEMO, self.root)

    def plan(self) -> Plan:
        from cine_toaster.assembly import plan_scene
        from cine_toaster.project import load_scene

        return plan_scene(self.root, load_scene(self.root, "SC-030"))

    def test_the_breakdowns_transition_is_resolved_and_an_unknown_one_said(self) -> None:
        scene_file = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        text = scene_file.read_text(encoding="utf-8")
        scene_file.write_text(text.replace("  - n: 2\n", "  - n: 2\n    transition: {id: dip-to-black, duration_ms: 200}\n", 1),
                              encoding="utf-8")
        second = self.plan().segments[1]
        self.assertEqual((second.transition["id"], second.transition["seconds"]), ("dip-to-black", 0.2))
        self.assertTrue(second.transition.get("shader") or second.transition.get("mode") == "fadeblack")
        # The demo's takes are short: a long transition is cut to half the shorter shot, and said.
        scene_file.write_text(text.replace("  - n: 2\n", "  - n: 2\n    transition: {id: dip-to-black}\n", 1),
                              encoding="utf-8")
        plan = self.plan()
        self.assertLess(plan.segments[1].transition["seconds"], 1.4)
        self.assertTrue(any("is shortened to" in note for note in plan.notes))

    def test_a_decided_split_reaches_the_cut(self) -> None:
        from cine_toaster.commands import Actor, set_cut
        from cine_toaster.errors import ValidationError

        with self.assertRaisesRegex(ValidationError, "Only a J- or L-cut has a split"):
            set_cut(self.root, scene_id="SC-030", shot_id="P3", actor=Actor(id="editor"),
                    cut={"type": "hard", "split": 0.5})
        set_cut(self.root, scene_id="SC-030", shot_id="P3", actor=Actor(id="editor"),
                cut={"type": "j", "split": 0.4, "reason": "the stack first"})
        self.assertEqual(self.plan().segments[2].split, 0.4)


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class SceneJoinTests(unittest.TestCase):
    """Joins between scenes: declared on the incoming scene, rendered by the sequence's assembly (CT-0051)."""

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

    def versions(self, sound: str) -> None:
        """Each scene of the demo's sequence gets a recorded 2 s version: SC-010 red, SC-030 blue."""

        from cine_toaster.commands import Actor, record_assembly

        for scene, colour in (("SC-010", "red"), ("SC-030", "blue")):
            media = self.root / "renders" / f"{scene}.mp4"
            media.parent.mkdir(exist_ok=True)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color={colour}:s=160x90:r=24:d=2",
                            "-f", "lavfi", "-i", sound, "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-shortest", str(media)], check=True)
            record_assembly(self.root, scene_id=scene, assembly_id="v1", actor=Actor(id="editor"),
                            media=media.relative_to(self.root).as_posix(), summary="a test version",
                            duration_seconds=2.0, takes={})

    def test_music_runs_over_the_scenes_and_ducks_under_a_versions_speech(self) -> None:
        from cine_toaster.jobs import JobManager, JobStore, _sequence_plan

        manifest = self.root / "project.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace(
            'scenes: ["SC-010", "SC-030"]',
            'scenes: ["SC-010", "SC-030"]\n    music: {id: tension-drone, from: SC-010, at: 0.5, fade_in: 0, fade_out: 0}'),
            encoding="utf-8")
        self.versions("anullsrc=r=48000:cl=stereo")
        # The scene job writes this beside every version: where its speech is heard.
        (self.root / "renders" / "SC-030.mp4.speech.json").write_text('{"speech": [[0.8, 1.4]]}', encoding="utf-8")
        plan = _sequence_plan(self.root, "the-reply")
        self.assertEqual([(cue["id"], cue["start"], cue["length"]) for cue in plan.cues], [("tension-drone", 0.5, 3.5)])
        self.assertEqual(plan.segments[1].speech_spans, [(0.8, 1.4)])
        manager = JobManager(store=JobStore(self.root.parent / "state" / "jobs.sqlite"))
        self.addCleanup(manager.shutdown, wait=False)
        job = manager.wait(manager.submit("assemble_sequence", self.root, {"sequence": "the-reply"})["id"], timeout=180)
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.assertEqual([item["id"] for item in job["result"]["summary"]["sound"]], ["tension-drone"])
        manager.adopt(job["id"])
        output = self.root / "sequences" / "the-reply" / "versions" / "v1.mp4"
        clear = JoinTests.mean(None, output, 1.0, 0.6)  # music in SC-010
        under = JoinTests.mean(None, output, 2.9, 0.4)  # SC-030's line, 0.8-1.4 s into it
        self.assertGreater(clear - under, 7.0)

    def enter(self, text: str) -> None:
        scene_file = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene_file.write_text(scene_file.read_text(encoding="utf-8").replace("shots:\n", text + "shots:\n", 1),
                              encoding="utf-8")

    def test_a_scene_is_entered_through_a_transition_in_the_sequence(self) -> None:
        from cine_toaster.jobs import JobManager, JobStore, _sequence_plan
        from cine_toaster.project import load_scene

        self.enter("enter: {transition: {id: dip-to-black, duration_ms: 400, reason: night falls between them}}\n")
        self.assertEqual(load_scene(self.root, "SC-030")["enter"]["transition"]["id"], "dip-to-black")
        manager = JobManager(store=JobStore(self.root.parent / "state" / "jobs.sqlite"))
        self.addCleanup(manager.shutdown, wait=False)
        self.versions("sine=f=220:d=2")
        plan = _sequence_plan(self.root, "the-reply")
        self.assertEqual(plan.segments[1].transition["id"], "dip-to-black")
        job = manager.wait(manager.submit("assemble_sequence", self.root, {"sequence": "the-reply"})["id"], timeout=180)
        self.assertEqual(job["state"], "succeeded", job["error"])
        lengths = [segment.end for segment in plan.segments]
        self.assertAlmostEqual(job["result"]["summary"]["duration_seconds"], sum(lengths) - 0.4, delta=0.05)

    def test_an_unknown_way_in_is_said(self) -> None:
        from cine_toaster.project import load_scene

        self.enter("enter: {type: wipe, transition: {id: no-such-transition}}\n")
        codes = {finding["code"] for finding in load_scene(self.root, "SC-030")["findings"]}
        self.assertTrue({"cut_type_unknown", "transition_unknown"} <= codes)


if __name__ == "__main__":
    unittest.main()
