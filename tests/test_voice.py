"""A take's speech converted to the cast member's voice, as a new take (CT-0040)."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from cine_toaster.errors import ValidationError
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.project import load_production, load_scene
from cine_toaster.voice import plan_conversion, voice_python

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_FFMPEG = shutil.which("ffmpeg") is not None

#: Stands in for the voice environment: called as `python worker take ref out work report`.
FAKE_WORKER = """#!/bin/sh
echo "$2" >> "$XDG_STATE_HOME/voice-calls"
ffmpeg -v error -y -f lavfi -i "sine=frequency=220:duration=2" -ar 44100 -ac 2 "$4"
printf '{"engine": "chatterbox-vc", "similarity": {"before": 0.5, "after": 0.8}}' > "$6"
"""


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class RevoiceTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        keys = ("XDG_CACHE_HOME", "XDG_STATE_HOME", "CINE_TOASTER_VOICE_PYTHON")
        self.previous = {key: os.environ.get(key) for key in keys}
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        self.addCleanup(self._restore)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        text = scene.read_text(encoding="utf-8")
        text = text.replace("  - n: 3\n", "  - n: 3\n    lines: {who: MARA, text: That's it}\n", 1)
        scene.write_text(text, encoding="utf-8")
        sheet = self.root / "cast" / "mara" / "character.yaml"
        sheet.write_text(sheet.read_text(encoding="utf-8").replace(
            "  language: en-GB\n", "  language: en-GB\n  references: [reference/voice.wav]\n"), encoding="utf-8")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=180:duration=5",
                        str(sheet.parent / "reference" / "voice.wav")], check=True)
        worker = base / "fake-python"
        worker.write_text(FAKE_WORKER, encoding="utf-8")
        worker.chmod(worker.stat().st_mode | stat.S_IEXEC)
        os.environ["CINE_TOASTER_VOICE_PYTHON"] = str(worker)
        self.manager = JobManager(store=JobStore(base / "state" / "jobs.sqlite"))
        self.addCleanup(self.manager.shutdown, wait=False)

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_the_voice_comes_from_the_cast_sheet(self) -> None:
        plan = plan_conversion(self.root, load_production(self.root), "SC-030", "P3")
        self.assertEqual((plan.speaker, plan.member), ("MARA", "MARA"))
        self.assertTrue(plan.speakers[0]["reference"].name == "voice.wav")
        self.assertEqual(len(plan.public_dict(self.root)["reference_digest"]), 16)

    def test_what_cannot_be_converted_is_said(self) -> None:
        production = load_production(self.root)
        with self.assertRaisesRegex(ValidationError, "no line spoken in the take"):
            plan_conversion(self.root, production, "SC-030", "P1")
        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene.write_text(scene.read_text(encoding="utf-8").replace(
            "    lines: {who: MARA, text: That's it}\n",
            "    lines: [{who: MARA, text: That's it}, {who: SPEAKER, text: That's it}]\n"), encoding="utf-8")
        # Two speakers: each needs a recording of their own (the stack has none).
        with self.assertRaisesRegex(ValidationError, "Speaker stack's cast sheet has no voice recording"):
            plan_conversion(self.root, load_production(self.root), "SC-030", "P3")
        scene.write_text(scene.read_text(encoding="utf-8").replace(", {who: SPEAKER, text: That's it}", "").replace(
            "who: MARA", "who: NOBODY"), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "no cast sheet"):
            plan_conversion(self.root, load_production(self.root), "SC-030", "P3")

    def test_a_sheet_without_a_recording_cannot_lend_its_voice(self) -> None:
        (self.root / "cast" / "mara" / "reference" / "voice.wav").unlink()
        with self.assertRaisesRegex(ValidationError, "no voice recording"):
            plan_conversion(self.root, load_production(self.root), "SC-030", "P3")

    def test_two_speakers_each_keep_their_own_voice(self) -> None:
        stack = self.root / "cast" / "speaker" / "character.yaml"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=90:duration=5",
                        str(stack.parent / "voice.wav")], check=True)
        text = stack.read_text(encoding="utf-8")
        text = text.replace("voice:\n", "voice:\n  references: [voice.wav]\n", 1) if "voice:\n" in text else text + "\nvoice:\n  references: [voice.wav]\n"
        stack.write_text(text, encoding="utf-8")
        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene.write_text(scene.read_text(encoding="utf-8").replace(
            "    lines: {who: MARA, text: That's it}\n",
            "    lines: [{who: SPEAKER, text: That's it}, {who: MARA, text: That's the one}]\n"), encoding="utf-8")
        plan = plan_conversion(self.root, load_production(self.root), "SC-030", "P3")
        self.assertEqual([item["who"] for item in plan.speakers], ["SPEAKER", "MARA"])
        self.assertEqual([line["who"] for line in plan.spec()["lines"]], ["SPEAKER", "MARA"])
        job = self.manager.wait(self.manager.submit("convert_voice", self.root, {"scene": "SC-030", "shot": "P3"})["id"], timeout=60)
        self.assertEqual(job["state"], "succeeded", job["error"])

    def test_the_converted_take_joins_the_others_with_its_lineage(self) -> None:
        self.assertIsNotNone(voice_python())
        job = self.manager.wait(self.manager.submit("convert_voice", self.root, {"scene": "SC-030", "shot": "P3"})["id"], timeout=60)
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.manager.adopt(job["id"])
        shot = next(item for item in load_scene(self.root, "SC-030")["shots"] if item["id"] == "P3")
        take = next(item for item in shot["takes"] if item["id"] == "VOICE")
        self.assertTrue(take["media"].endswith("work/_takes/c03-voice.mp4"))
        provenance = take["provenance"]
        self.assertEqual((provenance["kind"], provenance["member"], provenance["from_take"]), ("voice-conversion", "MARA", "CUT"))
        self.assertEqual(provenance["similarity"], {"before": 0.5, "after": 0.8})
        # The picture is the source take's, untouched.
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width",
                                "-of", "json", str(self.root / take["media"])], capture_output=True, text=True)
        source = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width",
                                 "-of", "json", str(self.root / "scenes/030-echo-chamber/work/c03.mp4")], capture_output=True, text=True)
        self.assertEqual(json.loads(probe.stdout), json.loads(source.stdout))

    def test_the_cut_can_hear_a_shot_in_the_cast_voice_without_a_new_take(self) -> None:
        from cine_toaster.commands import dispatch

        director = {"id": "director", "kind": "human"}
        with self.assertRaisesRegex(ValidationError, "no line spoken in the take"):
            dispatch(self.root, "set_voice", {"scene_id": "SC-030", "shot_id": "P1", "actor": director})
        dispatch(self.root, "set_voice", {"scene_id": "SC-030", "shot_id": "P3", "actor": director,
                                          "rationale": "Mara drifts in this take"})
        shot = next(item for item in load_scene(self.root, "SC-030")["shots"] if item["id"] == "P3")
        self.assertTrue(shot["voice_in_cut"]["converted"])

        def assemble(version: str) -> dict:
            job = self.manager.wait(self.manager.submit("assemble", self.root, {"scene": "SC-030", "version": version})["id"],
                                    timeout=120)
            self.assertEqual(job["state"], "succeeded", job["error"])
            return job

        job = assemble("v1")
        summary = job["result"]["summary"]
        self.assertEqual(list(summary["voices"]), ["P3"])
        self.assertEqual(summary["voices"]["P3"]["take"], shot["selected_take"] or "CUT")
        self.assertTrue(next(item for item in summary["segments"] if item["shot"] == "P3")["revoice"])
        self.manager.adopt(job["id"])
        scene = load_scene(self.root, "SC-030")
        self.assertIn("Heard in the cast's own voices: P3", scene["assemblies"][-1]["summary"])
        # No new take: the voice belongs to the cut, not to the shot's alternatives.
        self.assertFalse(any(take["id"] == "VOICE" for take in next(
            item for item in scene["shots"] if item["id"] == "P3")["takes"]))
        calls = Path(os.environ["XDG_STATE_HOME"]) / "voice-calls"
        self.assertEqual(len(calls.read_text().splitlines()), 1)
        assemble("v2")  # the same take, recordings and lines: converted once, kept in the cache
        self.assertEqual(len(calls.read_text().splitlines()), 1)

        dispatch(self.root, "set_voice", {"scene_id": "SC-030", "shot_id": "P3", "actor": director, "converted": False})
        self.assertIsNone(next(item for item in load_scene(self.root, "SC-030")["shots"] if item["id"] == "P3")["voice_in_cut"])
        self.assertEqual(assemble("v3")["result"]["summary"]["voices"], {})


if __name__ == "__main__":
    unittest.main()


class AlignmentTests(unittest.TestCase):
    """Who speaks when, from the declared lines and the spoken words (no diarization model)."""

    def words(self, spoken: str, start: float = 0.5, step: float = 0.4) -> list[dict]:
        return [{"word": word, "start": round(start + index * step, 2), "end": round(start + index * step + 0.3, 2)}
                for index, word in enumerate(spoken.split())]

    def test_three_speakers_get_their_own_stretches(self) -> None:
        from cine_toaster.voice_align import align, segments

        lines = [{"who": "CLAIRE", "text": "Kael."}, {"who": "KAEL", "text": "I know."},
                 {"who": "LIRA", "text": "Then say it, both of you."}, {"who": "KAEL", "text": "Later."}]
        # The recognizer mishears one word and adds a filler: the lines still land.
        words = self.words("kale i know uh then say it both of you later")
        spans = align(lines, words)
        self.assertEqual([span["who"] for span in spans], ["CLAIRE", "KAEL", "LIRA", "KAEL"])
        parts = segments(spans, length=6.0)
        self.assertEqual([part["who"] for part in parts], ["CLAIRE", "KAEL", "LIRA", "KAEL"])
        self.assertEqual(parts[0]["start"], 0.0)
        self.assertEqual(parts[-1]["end"], 6.0)
        # Contiguous: nothing converted twice, nothing left out.
        self.assertTrue(all(a["end"] == b["start"] for a, b in zip(parts, parts[1:])))
        self.assertGreater(parts[1]["start"], spans[0]["end"] - 0.01)  # the cut falls in the pause

    def test_one_speaker_is_one_stretch(self) -> None:
        from cine_toaster.voice_align import align, segments

        lines = [{"who": "MARA", "text": "That's it."}, {"who": "MARA", "text": "That's the one."}]
        parts = segments(align(lines, self.words("that's it that's the one")), length=4.0)
        self.assertEqual(parts, [{"who": "MARA", "start": 0.0, "end": 4.0}])

    def test_a_sidecar_that_leaves_out_a_line_is_not_trusted(self) -> None:
        from unittest import mock

        from cine_toaster import voice_worker

        # As in a real take: the subtitle words carry only the second speaker's line.
        lines = [{"who": "KAEL", "text": "Claire?!"}, {"who": "LIRA", "text": "No. My name is Lira."}]
        with tempfile.TemporaryDirectory() as folder:
            sidecar = Path(folder) / "c02.words.json"
            sidecar.write_text(json.dumps([[7.76, 8.24, " My"], [8.24, 8.46, " name"], [8.46, 8.64, " is"],
                                           [8.64, 8.98, " Lira."]]), encoding="utf-8")
            heard = self.words("claire no my name is lira", start=1.0)
            with mock.patch.object(voice_worker, "_heard", return_value=heard) as listen:
                spans, source = voice_worker._spans({"lines": lines, "words": str(sidecar)}, Path(folder) / "v.wav")
            listen.assert_called_once()
            self.assertEqual([span["who"] for span in spans], ["KAEL", "LIRA"])
            self.assertTrue(source.startswith("heard"))
            # A sidecar with every line in it is used as it is, without listening.
            sidecar.write_text(json.dumps([[0.5, 0.9, "Claire?!"], [1.5, 1.8, "No."], [1.9, 2.1, "My"],
                                           [2.1, 2.3, "name"], [2.3, 2.4, "is"], [2.4, 2.8, "Lira."]]), encoding="utf-8")
            with mock.patch.object(voice_worker, "_heard") as listen:
                spans, source = voice_worker._spans({"lines": lines, "words": str(sidecar)}, Path(folder) / "v.wav")
            listen.assert_not_called()
            self.assertEqual(source, "c02.words.json")
