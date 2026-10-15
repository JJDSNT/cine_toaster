"""Cutting to music: beats kept beside a track, shot lengths given in beats (CT-0067)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from cine_toaster.beats import detect
from cine_toaster.project import load_production
from cine_toaster.voice import voice_python

sys.path.insert(0, str(Path(__file__).parent))
from heavy import heavy  # noqa: E402

HAS_LIBROSA = bool(voice_python()) and shutil.which("ffmpeg") is not None and subprocess.run(
    [str(voice_python()), "-c", "import librosa"], capture_output=True).returncode == 0 if voice_python() else False

# A track whose beats are every half second from 0.5 s: 120 BPM.
BEATS = [round(0.5 + 0.5 * index, 3) for index in range(40)]
SCENE = textwrap.dedent("""\
    scene: S1
    music: track
    shots:
      - {n: 1, beats: 4}
      - {n: 2, beats: 2}
      - {n: 3, beats: 4, transition: {id: cross-dissolve, beats: 1, reason: a test}}
      - {n: 4, beats: 4, transition: {id: cross-dissolve, duration_ms: 400, reason: a test}}
""")


class LayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
        (self.root / "scenes" / "010").mkdir(parents=True)
        sound = self.root / "sounds" / "track"
        sound.mkdir(parents=True)
        (sound / "sound.toml").write_text('id = "track"\ncategory = "music"\n[source]\nfile = "track.wav"\n')
        (sound / "track.wav").write_bytes(b"a recording")
        self.beats(BEATS)
        self.scene(SCENE)

    def beats(self, times: list[float], **extra) -> None:
        (self.root / "sounds" / "track" / "beats.json").write_text(json.dumps({"tempo": 120, "beats": times, **extra}))

    def scene(self, text: str) -> None:
        (self.root / "scenes" / "010" / "scene.yaml").write_text(text)

    def loaded(self) -> dict:
        return load_production(self.root)["scenes"][0]

    def codes(self) -> list[tuple[str, str]]:
        return [(f["code"], f["severity"]) for f in self.loaded()["findings"]
                if f["code"].startswith(("beats", "join_off"))]

    def test_every_join_falls_on_its_beat(self) -> None:
        scene = self.loaded()
        lengths = [shot["duration_seconds"] for shot in scene["shots"]]
        transitions = [(shot["transition"] or {}).get("duration_ms") for shot in scene["shots"]]
        self.assertEqual(transitions, [None, None, 500, 400])  # one beat is half a second here
        # Joins at beats 4, 6 and 10: 2.5 s, 3.5 s, 5.5 s; the scene ends on beat 14, 7.5 s.
        self.assertEqual(lengths, [2.5, 1.25, 2.45, 2.2])
        clock, joins = 0.0, []
        for index, shot in enumerate(scene["shots"]):
            overlap = (transitions[index] or 0) / 1000
            clock -= overlap
            joins.append(round(clock + overlap / 2, 3))  # where the cut is felt
            clock += lengths[index]
        self.assertEqual(joins[1:], [2.5, 3.5, 5.5])
        self.assertAlmostEqual(clock, 7.5)
        self.assertEqual(self.codes(), [])

    def test_a_scene_that_cannot_be_counted_says_why(self) -> None:
        self.scene(SCENE.replace("{n: 2, beats: 2}", "{n: 2, duration: 1}"))
        self.assertEqual(self.codes(), [("beats_mixed", "error")])
        self.scene(SCENE.replace("music: track\n", ""))
        self.assertEqual(self.codes(), [("beats_without_music", "error")])
        self.scene(SCENE.replace("music: track", "music: {id: track, at: 1}"))
        self.assertEqual(self.codes(), [("beats_music_not_at_start", "error")])
        self.scene(SCENE.replace("{n: 4, beats: 4,", "{n: 4, beats: 40,"))
        self.assertEqual(self.codes(), [("beats_past_end", "error")])
        self.scene(SCENE)
        self.beats(BEATS, sha256="not this recording")
        self.assertEqual(self.codes(), [("beats_missing", "warning")])

    def test_a_transition_too_long_for_its_shots_is_said_to_leave_the_beat(self) -> None:
        self.scene(SCENE.replace("beats: 1, reason", "beats: 3, reason"))
        self.assertEqual(self.codes(), [("join_off_beat", "warning")])


@heavy("detects beats with librosa in the voice environment")
@unittest.skipUnless(HAS_LIBROSA, "the voice environment with librosa is missing")
class DetectionTests(unittest.TestCase):
    def test_a_click_track_at_120_bpm_is_heard_as_120(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            audio = directory / "clicks.wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            "aevalsrc='0.8*sin(2*PI*1000*t)*exp(-60*mod(t,0.5))':s=44100:d=12", str(audio)], check=True)
            heard = detect({"id": "clicks", "file": str(audio), "directory": str(directory)})
            # librosa reads its tempo off a grid (117.5 here); the beats themselves are what the cut uses.
            self.assertAlmostEqual(heard["tempo"], 120, delta=5)
            gaps = [b - a for a, b in zip(heard["beats"], heard["beats"][1:])]
            self.assertAlmostEqual(sum(gaps) / len(gaps), 0.5, delta=0.02)
            self.assertTrue((directory / "beats.json").is_file())
            self.assertEqual(len(heard["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
