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
        self.assertTrue(plan.reference.name == "voice.wav")
        self.assertEqual(len(plan.public_dict(self.root)["reference_digest"]), 16)

    def test_what_cannot_be_converted_is_said(self) -> None:
        production = load_production(self.root)
        with self.assertRaisesRegex(ValidationError, "no line spoken in the take"):
            plan_conversion(self.root, production, "SC-030", "P1")
        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene.write_text(scene.read_text(encoding="utf-8").replace(
            "    lines: {who: MARA, text: That's it}\n",
            "    lines: [{who: MARA, text: That's it}, {who: SPEAKER, text: That's it}]\n"), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "2 speakers"):
            plan_conversion(self.root, load_production(self.root), "SC-030", "P3")
        scene.write_text(scene.read_text(encoding="utf-8").replace(", {who: SPEAKER, text: That's it}", "").replace(
            "who: MARA", "who: NOBODY"), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "no cast sheet"):
            plan_conversion(self.root, load_production(self.root), "SC-030", "P3")

    def test_a_sheet_without_a_recording_cannot_lend_its_voice(self) -> None:
        (self.root / "cast" / "mara" / "reference" / "voice.wav").unlink()
        with self.assertRaisesRegex(ValidationError, "no voice recording"):
            plan_conversion(self.root, load_production(self.root), "SC-030", "P3")

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


if __name__ == "__main__":
    unittest.main()
