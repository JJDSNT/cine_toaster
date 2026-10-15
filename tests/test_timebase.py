"""CT-0079: time in one place -- rates as fractions, cut points on the frame grid, sound in samples."""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from cine_toaster import timebase

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
MEASURE = Path(__file__).parents[1] / "scripts" / "research" / "time_drift.py"


def measurement():
    spec = importlib.util.spec_from_file_location("time_drift", MEASURE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RateTests(unittest.TestCase):
    def test_a_rate_is_an_exact_fraction_however_it_is_written(self) -> None:
        ntsc = Fraction(30000, 1001)
        for written in ("30000/1001", "29.97", 29.97, 30000 / 1001, ntsc):
            with self.subTest(written=written):
                self.assertEqual(timebase.rate(written), ntsc)
        self.assertEqual(timebase.rate("24000/1001"), Fraction(24000, 1001))
        self.assertEqual(timebase.rate(23.976), Fraction(24000, 1001))
        self.assertEqual(timebase.rate("24"), 24)
        self.assertEqual(timebase.rate(25.0), 25)

    def test_ffmpeg_is_told_the_fraction(self) -> None:
        self.assertEqual(timebase.ffmpeg_rate(29.97), "30000/1001")
        self.assertEqual(timebase.ffmpeg_rate(24.0), "24")


class GridTests(unittest.TestCase):
    def test_a_cut_point_snaps_to_the_nearest_frame(self) -> None:
        self.assertEqual(timebase.frame_at(0.35, 24), 8)  # 8.4 frames
        self.assertAlmostEqual(timebase.snap(0.35, 24), 8 / 24)
        self.assertEqual(timebase.frame_at(0.35, "30000/1001"), 10)  # 10.49
        self.assertAlmostEqual(timebase.snap(0.35, 20), 0.35)  # on the grid already

    def test_sound_positions_come_from_frames_and_do_not_drift(self) -> None:
        """A frame at 30000/1001 is 1601.6 samples: summed per frame, rounding would drift; from the frame
        count, an hour is still within half a sample of exact."""

        frames = 30000 * 3600 // 1001
        exact = Fraction(frames) * 48000 / Fraction(30000, 1001)
        self.assertLessEqual(abs(timebase.samples_of_frames(frames, "30000/1001") - exact), Fraction(1, 2))
        self.assertEqual(timebase.samples_of_frames(24, 24), 48000)

    def test_a_seek_never_passes_the_instant(self) -> None:
        for seconds in (Fraction(10, 1) / Fraction(30000, 1001), 1 / 3, 0.35):
            with self.subTest(seconds=seconds):
                self.assertLessEqual(Fraction(timebase.seek(seconds)), Fraction(seconds))
                self.assertLess(Fraction(seconds) - Fraction(timebase.seek(seconds)), Fraction(1, 1_000_000))


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class SyncTests(unittest.TestCase):
    """The matrix's regression tests: a cut whose takes flash and click at one instant, the sound on the picture
    within a sample -- for trims off the grid (0.35 s at most rates) and on it (20 fps)."""

    def film(self, rate: str, shots: int = 4) -> dict:
        module = measurement()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name) / "film"
        module.make_film(root, shots, rate)
        return module.measure(root, rate)

    def test_the_sound_lands_on_its_frame_at_every_rate(self) -> None:
        for rate in ("24", "25", "20", "24000/1001", "30000/1001"):
            with self.subTest(rate=rate):
                result = self.film(rate)
                # The rate is written as it is: NTSC stays NTSC.
                self.assertEqual(Fraction(result["rate_written"]), Fraction(rate))
                for stage in ("engine", "delivery"):
                    measured = result[stage]
                    self.assertEqual((measured["flashes"], measured["clicks"]), (4, 4), stage)
                    # Within the grid's own limit: an NTSC frame boundary falls between two samples.
                    self.assertLessEqual(max(abs(measured["min"]), abs(measured["max"])), 0.5, (stage, measured))


if __name__ == "__main__":
    unittest.main()
