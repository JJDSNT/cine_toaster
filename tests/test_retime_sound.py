"""C7 step 3 (CT-0080): a retimed shot's sound -- its contract, and the policies mute, preserve and stretch."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock

import numpy as np

from cine_toaster import retime_sound as rs
from cine_toaster.errors import ValidationError

RATE = 48000
FPS = Fraction(24)
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def ramp(t: Fraction) -> Fraction:
    """Output seconds -> media seconds from 1 s of the media: 1x for a second, 2x, then 0.5x."""

    if t < 1:
        return 1 + t
    if t < 2:
        return 2 + 2 * (t - 1)
    return 4 + (t - 2) / 2


def timemap(mapping=ramp, seconds: int = 3) -> rs.TimeMap:
    frames = seconds * 24
    return rs.TimeMap(FPS, Fraction(1), tuple(mapping(Fraction(2 * f + 1, 48)) for f in range(frames)), at=mapping)


def write(path: Path, data: np.ndarray) -> Path:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(RATE), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_f32le", str(path)], input=np.ascontiguousarray(data, np.float32).tobytes(), check=True)
    return path


def read(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "2", "-ar", str(RATE), "-f", "f32le",
                          "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


def onsets(stereo: np.ndarray, threshold: float = 0.05) -> list[int]:
    mono = np.abs(stereo.sum(axis=1)) / 2
    loud = np.nonzero(mono > threshold)[0]
    return [int(v) for v in loud[np.insert(np.diff(loud) > 100, 0, True)]] if len(loud) else []


def inverse(mapping, media: float, seconds: int = 3) -> float:
    grid = np.linspace(0, seconds, 300001)
    return float(np.interp(media, [float(mapping(Fraction(t).limit_denominator(10**6))) for t in grid], grid))


class ContractTests(unittest.TestCase):
    def test_a_map_is_unchanged_shifted_or_a_speed(self) -> None:
        self.assertEqual(timemap(lambda t: 1 + t).kind, "unchanged")
        shifted = timemap(lambda t: 1 + t - Fraction(1, 8))  # three frames earlier
        self.assertEqual((shifted.kind, shifted.shift), ("shifted", Fraction(-1, 8)))
        self.assertEqual(timemap().kind, "speed")

    def test_pieces_follow_the_map_between_frames(self) -> None:
        """With the map itself, each piece's edges are where the map is at a frame boundary: 1x, 2x, 0.5x."""

        pieces = timemap().pieces()
        self.assertEqual([(piece.first, piece.end) for piece in pieces], [(0, 24), (24, 48), (48, 72)])
        self.assertEqual([piece.start for piece in pieces], [Fraction(1), Fraction(2), Fraction(4)])
        self.assertEqual([round(piece.speed(FPS), 6) for piece in pieces], [1.0, 2.0, 0.5])

    def test_policies_are_named_and_resample_is_refused_by_name(self) -> None:
        self.assertIsNone(rs.policy_problem("stretch"))
        self.assertIn("not built yet", rs.policy_problem("resample"))
        self.assertIn("one of", rs.policy_problem("faster"))


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        n = 6 * RATE
        self.clicks_at = np.arange(int(1.13 * RATE), int(5.3 * RATE), int(0.17 * RATE))  # media samples, off any grid
        clicks = np.zeros((n, 2), np.float32)
        for at in self.clicks_at:
            clicks[at:at + 96] = 0.8
        self.clicks = write(self.root / "clicks.wav", clicks)
        t = np.arange(n) / RATE
        tone = (0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        self.tone = write(self.root / "tone.wav", np.stack([tone, tone], axis=1))

    def build(self, policy: str, source: Path, mapping=ramp, **more) -> np.ndarray:
        out = self.root / f"{policy}.wav"
        rs.build(policy, timemap(mapping), source, out, **more)
        return read(out)

    def test_stretch_lays_every_attack_on_its_instant(self) -> None:
        out = self.build("stretch", self.clicks)
        self.assertEqual(len(out), 3 * RATE)  # exactly the shot's samples
        expected = [round(inverse(ramp, at / RATE) * RATE) for at in self.clicks_at if 1 <= at / RATE < 5.5]
        expected = [e for e in expected if 0 < e < 3 * RATE - 1300]
        found = onsets(out)
        self.assertEqual(len(found), len(expected))
        self.assertLessEqual(max(abs(f - e) for f, e in zip(found, expected)), 1)  # to the sample
        peaks = [float(np.abs(out[e:e + 96]).max()) for e in expected]
        self.assertGreater(min(peaks), 0.75)  # whole, not halved by the grains

    def test_stretch_keeps_pitch_and_level_through_the_changes(self) -> None:
        out = self.build("stretch", self.tone).sum(axis=1) / 2
        envelope = np.abs(out[2400:-2400]).reshape(-1, 240).max(axis=1)
        self.assertLess(float(np.ptp(20 * np.log10(envelope / 0.25))), 0.5)  # no dip, no bump: within 0.5 dB
        for lo, hi in ((0.1, 0.9), (1.1, 1.9), (2.1, 2.9)):
            part = out[int(lo * RATE):int(hi * RATE)]
            spectrum = np.abs(np.fft.rfft(part * np.hanning(len(part)), 8 * len(part)))
            self.assertAlmostEqual(np.argmax(spectrum) * RATE / (8 * len(part)), 440.0, delta=1.0)

    def test_stretch_of_a_shift_moves_the_sound_without_processing_it(self) -> None:
        late = lambda t: 1 + t - Fraction(1, 8)  # noqa: E731 - three frames earlier of the media
        out = self.build("stretch", self.clicks, late)
        expected = [round((at / RATE - 1 + 1 / 8) * RATE) for at in self.clicks_at]
        expected = [e for e in expected if 0 <= e < 3 * RATE - 100]
        self.assertEqual(onsets(out)[: len(expected)], expected)  # exactly, sample for sample

    def test_preserve_keeps_the_take_s_own_speed_not_its_sync(self) -> None:
        out = self.build("preserve", self.clicks)
        found = onsets(out)
        self.assertEqual(found[:4], [int(at - RATE) for at in self.clicks_at[:4]])  # from the cut point, at speed 1
        self.assertEqual(len(out), 3 * RATE)

    def test_preserve_pads_where_the_take_ends_first(self) -> None:
        short = write(self.root / "short.wav", np.full((int(2.5 * RATE), 2), 0.1, np.float32))
        out = self.build("preserve", short)
        self.assertEqual(len(out), 3 * RATE)
        self.assertLess(float(np.abs(out[int(1.6 * RATE):]).max()), 1e-6)  # silence past the take's end

    def test_mute_is_silence_of_the_shot_s_length(self) -> None:
        out = self.build("mute", self.clicks)
        self.assertEqual((len(out), float(np.abs(out).max())), (3 * RATE, 0.0))

    def test_a_reverse_or_a_freeze_cannot_be_stretched(self) -> None:
        with self.assertRaises(ValidationError):
            self.build("stretch", self.clicks, lambda t: 4 - t)
        with self.assertRaises(ValidationError):
            self.build("stretch", self.clicks, lambda t: Fraction(2))

    def test_a_stretcher_asked_and_missing_is_refused_not_swapped(self) -> None:
        with mock.patch.object(rs, "available", return_value=["anchored"]):
            with self.assertRaises(ValidationError):
                self.build("stretch", self.clicks, stretch_with="rubberband")
        with self.assertRaises(ValidationError):
            self.build("stretch", self.clicks, stretch_with="magic")

    def test_stereo_stays_coherent(self) -> None:
        n = 6 * RATE
        pair = np.zeros((n, 2), np.float32)
        for at in (int(1.5 * RATE), int(2.6 * RATE)):
            pair[at:at + 96, 0] = 0.8
            pair[at + 48:at + 144, 1] = 0.8  # the right one millisecond later
        out = self.build("stretch", write(self.root / "pair.wav", pair))
        for media in (1.5, 2.6):
            e = round(inverse(ramp, media) * RATE)
            left = e - 200 + int(np.argmax(np.abs(out[e - 200:e + 400, 0]) > 0.5))
            right = e - 200 + int(np.argmax(np.abs(out[e - 200:e + 400, 1]) > 0.5))
            self.assertEqual((left - e, right - e), (0, 48))


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class CutTests(unittest.TestCase):
    def cut(self, composite: str, policy: str) -> tuple[list[str], np.ndarray, object]:
        import importlib.util

        from cine_toaster.assembly import plan_scene, render
        from cine_toaster.project import load_production

        spec = importlib.util.spec_from_file_location(
            "time_drift", Path(__file__).parents[1] / "scripts" / "research" / "time_drift.py")
        drift = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(drift)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name) / "film"
        drift.make_film(root, 2, "24")  # each take: a flash and a click at its frame 20
        scene = root / "scenes" / "010" / "scene.yaml"
        scene.write_text(scene.read_text().replace("    label: Shot 1.\n", (
            f"    label: Shot 1.\n    retime_sound: {policy}\n    composite:\n      nodes:\n"
            f"        room: {{op: generate.source, take: CUT}}\n{composite}      output: out\n")))
        plan = plan_scene(root, load_production(root)["scenes"][0])
        render(root, plan, root / "cut.mp4", root / "work",
               lambda command, **_: subprocess.run(command, check=True, capture_output=True))
        return plan.notes, read(root / "work" / "sound.wav"), plan

    def test_a_speed_up_with_stretch_lays_its_click_where_the_picture_shows_it(self) -> None:
        notes, sound, plan = self.cut("        m: {op: curve.keys, keys: [[0, 0], [2, 4]]}\n"
                                      "        out: {op: time.remap, in: room, map: {curve: m}}\n", "stretch")
        self.assertTrue(any("P1: retimed -- its take's sound stretched" in note for note in notes), notes)
        origin = Fraction(8, 24)  # the take's 0.35 s cut point, on its frame grid
        expected = round((Fraction(20, 24) - origin) / 2 * RATE)  # 2x: half as far into the shot
        self.assertEqual(onsets(sound, 0.5 * float(np.abs(sound).max()))[0], expected)

    def test_an_offset_with_stretch_moves_its_click_by_the_offset(self) -> None:
        notes, sound, _ = self.cut("        out: {op: time.offset, in: room, frames: 3}\n", "stretch")
        self.assertTrue(any("moved by" in note for note in notes), notes)
        origin = Fraction(8, 24)
        expected = round((Fraction(20, 24) - origin + Fraction(3, 24)) * RATE)  # shown three frames late
        self.assertEqual(onsets(sound, 0.5 * float(np.abs(sound).max()))[0], expected)


if __name__ == "__main__":
    unittest.main()
