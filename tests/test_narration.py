"""Lines a production speaks itself: where the audio goes, in whose voice, and when it is stale (CT-0065)."""

from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

from cine_toaster.narration import speak_lines
from cine_toaster.project import load_production

SCENE = textwrap.dedent("""\
    scene: S1
    shots:
      - n: 1
        source: composed
        engine: solid
        duration: 4
        lines:
          - {who: NARRATOR, text: "{first}", voice: piper/en_US-lessac-medium, mix: {file: sound/a.wav, at: 0}}
          - {who: SCEPTIC, text: "Like what?", voice: piper/en_US-ryan-medium, mix: {file: sound/b.wav, at: 2}}
""")


class Fake:
    """A narrator that writes the voice and the words instead of sound."""

    def __init__(self, voice: str, calls: list) -> None:
        self.voice, self.calls = voice, calls

    def speak(self, *, text: str, output: Path):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{self.voice}: {text}")
        self.calls.append((self.voice, text))
        return SimpleNamespace(duration_seconds=1.0)


class NarrationTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
        (self.root / "scenes" / "010").mkdir(parents=True)
        self.write("Everything you see.")
        self.calls: list = []

    def write(self, first: str) -> None:
        (self.root / "scenes" / "010" / "scene.yaml").write_text(SCENE.replace("{first}", first))

    def speak(self, **options):
        return speak_lines(self.root, load_production(self.root), lambda voice: Fake(voice, self.calls),
                           default_voice="en_US-lessac-medium", **options)

    def codes(self) -> list[tuple[str, str]]:
        return [(f["code"], f["severity"]) for f in load_production(self.root)["scenes"][0]["findings"]
                if f["code"].startswith("line_audio")]

    def test_audio_is_written_beside_the_scene_each_line_in_its_own_voice(self) -> None:
        self.assertEqual(self.codes(), [("line_audio_missing", "advice")] * 2)
        results = self.speak()
        self.assertEqual([item.file for item in results], ["scenes/010/sound/a.wav", "scenes/010/sound/b.wav"])
        self.assertEqual([voice for voice, _ in self.calls], ["en_US-lessac-medium", "en_US-ryan-medium"])
        self.assertFalse((self.root / "sound").exists())
        self.assertEqual(self.codes(), [])

    def test_a_line_whose_words_changed_is_stale_and_spoken_again(self) -> None:
        self.speak()
        self.write("Everything you are about to see.")
        self.assertEqual(self.codes(), [("line_audio_stale", "warning")])
        results = self.speak()
        self.assertEqual([item.status for item in results], ["respoke", "keep"])
        self.assertIn("about to see", (self.root / "scenes/010/sound/a.wav").read_text())
        self.assertEqual(self.codes(), [])

    def test_audio_not_spoken_here_is_kept_and_a_file_at_the_root_is_not_heard(self) -> None:
        recorded = self.root / "scenes/010/sound/a.wav"
        recorded.parent.mkdir(parents=True)
        recorded.write_text("a person")
        (self.root / "sound").mkdir()
        (self.root / "sound/b.wav").write_text("made by an older toast voice")
        self.assertIn("production root", next(f["message"] for f in load_production(self.root)["scenes"][0]["findings"]
                                              if f["code"] == "line_audio_missing"))
        results = self.speak()
        self.assertEqual([item.status for item in results], ["keep", "spoke"])
        self.assertEqual(recorded.read_text(), "a person")
        record = json.loads((self.root / "scenes/010/sound/b.wav.provenance.json").read_text())
        self.assertEqual((record["model"], record["text"]), ("en_US-ryan-medium", "Like what?"))

    def test_a_line_in_a_voice_that_is_not_offline_is_refused(self) -> None:
        scene = self.root / "scenes/010/scene.yaml"
        scene.write_text(scene.read_text().replace("piper/en_US-ryan-medium", "Deep_Man"))
        self.assertEqual([item.status for item in self.speak()], ["spoke", "refuse"])


if __name__ == "__main__":
    unittest.main()


class VoiceDownloadTests(unittest.TestCase):
    """A voice is fetched with a stall limit and retries (CT-0096: Piper's own download hung ten minutes on a
    stalled connection and failed the build). No network: the opener is given."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.voices = Path(directory.name) / "voices"

    @staticmethod
    def opener(script: list):
        import io
        import socket

        calls = []

        def open_url(url, timeout=None):
            calls.append((url, timeout))
            step = script.pop(0)
            if step == "stall":
                raise socket.timeout("timed out")
            return io.BytesIO(step)

        open_url.calls = calls
        return open_url

    def test_a_stalled_connection_is_tried_again_and_the_voice_kept_whole(self) -> None:
        from cine_toaster.providers import piper

        opener = self.opener(["stall", b"model bytes", b"{}"])
        model = piper.ensure_voice(self.voices, "en_US-lessac-medium", opener=opener)
        self.assertEqual(model.read_bytes(), b"model bytes")
        self.assertEqual((self.voices / "en_US-lessac-medium.onnx.json").read_bytes(), b"{}")
        self.assertEqual([timeout for _, timeout in opener.calls], [piper.STALL_SECONDS] * 3)
        self.assertIn("/en/en_US/lessac/medium/en_US-lessac-medium.onnx", opener.calls[0][0])
        self.assertFalse(list(self.voices.glob("*.part")))
        # Kept, it is not fetched again.
        self.assertEqual(piper.ensure_voice(self.voices, "en_US-lessac-medium", opener=self.opener([])), model)

    def test_a_connection_that_never_answers_fails_after_its_tries_leaving_nothing_half_written(self) -> None:
        from cine_toaster.providers import ProviderError, piper

        with self.assertRaisesRegex(ProviderError, "failed 3 times"):
            piper.ensure_voice(self.voices, "en_US-lessac-medium", opener=self.opener(["stall"] * 3))
        self.assertEqual(list(self.voices.iterdir()), [])
