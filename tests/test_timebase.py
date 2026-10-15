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


class TickTests(unittest.TestCase):
    """ADR 0023: ticks to store and exchange -- exact by default, quantised only by a named policy."""

    def test_every_rate_we_meet_is_whole_ticks_a_frame_and_a_sample(self) -> None:
        for fps in ("8", "10", "12", "15", "16", "20", "24", "25", "30", "48", "50", "60", "120",
                    "24000/1001", "30000/1001", "60000/1001"):
            with self.subTest(fps=fps):
                self.assertTrue(timebase.representable(timebase.seconds_of(1, fps)))
        for sample_rate in (8000, 11025, 16000, 22050, 32000, 44100, 48000, 88200, 96000, 192000):
            with self.subTest(sample_rate=sample_rate):
                self.assertEqual(timebase.TICKS_PER_SECOND % sample_rate, 0)
        self.assertEqual(timebase.tick_of_frame(1, "30000/1001"), 8_475_667_200)
        self.assertEqual(timebase.tick_of_sample(1, 48000), 5_292_000)

    def test_an_exact_conversion_refuses_what_ticks_cannot_hold(self) -> None:
        with self.assertRaises(timebase.NotRepresentable):
            timebase.to_ticks(Fraction(1, 11))
        with self.assertRaises(timebase.NotRepresentable):
            timebase.tick_of_frame(1, 11)  # an 11 fps frame
        with self.assertRaises(ValueError):
            timebase.to_ticks(Fraction(1, 11), rounding="nearest")  # no such policy

    def test_quantising_follows_the_policy_asked(self) -> None:
        third = Fraction(1, 3 * timebase.TICKS_PER_SECOND)  # a third of a tick
        half = Fraction(1, 2 * timebase.TICKS_PER_SECOND)
        self.assertEqual(timebase.to_ticks(third, rounding="floor"), 0)
        self.assertEqual(timebase.to_ticks(third, rounding="ceil"), 1)
        self.assertEqual(timebase.to_ticks(half, rounding="half_up"), 1)
        self.assertEqual(timebase.to_ticks(half, rounding="half_even"), 0)
        self.assertEqual(timebase.to_ticks(3 * half, rounding="half_even"), 2)

    def test_a_quantised_round_trip_differs_but_the_record_keeps_the_original(self) -> None:
        eleventh = Fraction(1, 11)
        ticks = timebase.to_ticks(eleventh, rounding="half_even")
        self.assertNotEqual(timebase.from_ticks(ticks), eleventh)  # the ticks alone lose it
        self.assertLess(abs(timebase.from_ticks(ticks) - eleventh), Fraction(1, timebase.TICKS_PER_SECOND))
        record = timebase.to_record(eleventh)
        self.assertEqual(record["ticks"], ticks)
        self.assertEqual(timebase.from_record(record), eleventh)  # the record does not

    def test_stored_ticks_stay_within_64_bits_with_room_for_sums(self) -> None:
        limit = timebase.TICK_LIMIT
        self.assertLess(4 * limit, 2**63)  # four stored values add without overflowing int64
        self.assertGreater(timebase.from_ticks(limit), 100 * 86400)  # more than 100 days: any film
        self.assertEqual(timebase.to_ticks(timebase.from_ticks(limit)), limit)
        with self.assertRaises(timebase.NotRepresentable):
            timebase.to_ticks(timebase.from_ticks(limit + 1))
        with self.assertRaises(timebase.NotRepresentable):
            timebase.to_ticks(-timebase.from_ticks(limit) - 1, rounding="floor")
        with self.assertRaises(timebase.NotRepresentable):
            timebase.TimeRange(limit, 1)  # its end would pass the limit

    def test_round_trips_are_exact(self) -> None:
        for seconds in (Fraction(0), Fraction(1001, 30000), Fraction(7, 48000), Fraction(3600), Fraction(-5, 24)):
            with self.subTest(seconds=seconds):
                self.assertEqual(timebase.from_ticks(timebase.to_ticks(seconds)), seconds)
                self.assertEqual(timebase.from_record(timebase.to_record(seconds)), seconds)
        self.assertEqual(timebase.to_ticks("0.1"), timebase.TICKS_PER_SECOND // 10)  # a decimal, read as written

    def test_a_source_at_an_uncommon_rate_keeps_its_fraction(self) -> None:
        """An 11 fps source is not refused: its instants are stored with their exact fraction beside the
        quantised ticks, and read back exactly."""

        frame = timebase.seconds_of(5, 11)
        record = timebase.to_record(frame)
        self.assertEqual(record["exact"], "5/11")
        self.assertEqual(timebase.from_record(record), frame)
        self.assertLess(abs(timebase.from_ticks(record["ticks"]) - frame), Fraction(1, timebase.TICKS_PER_SECOND))
        self.assertEqual(timebase.to_record(Fraction(1, 24)), {"ticks": timebase.TICKS_PER_SECOND // 24})

    def test_frames_samples_and_instants_are_kept_apart(self) -> None:
        tick = timebase.tick_of_frame(10, "30000/1001")
        self.assertEqual(timebase.frame_of_tick(tick, "30000/1001"), 10)
        self.assertEqual(timebase.frame_of_tick(tick - 1, "30000/1001"), 9)  # a frame holds until the next
        self.assertEqual(timebase.sample_of_tick(tick), 16016)  # frame 10 is sample 16,016 exactly
        self.assertEqual(timebase.sample_of_tick(timebase.tick_of_frame(1, "30000/1001")), 1601)  # 1601.6, floored


class RangeTests(unittest.TestCase):
    def test_ranges_are_half_open(self) -> None:
        first = timebase.TimeRange.of_frames(0, 24, 24)
        second = timebase.TimeRange.of_frames(24, 24, 24)
        self.assertEqual(first.end, second.start)
        self.assertFalse(first.overlaps(second))  # they meet, they do not overlap
        self.assertTrue(first.contains(first.start))
        self.assertFalse(first.contains(first.end))
        self.assertEqual(list(first.frames(24)), list(range(24)))
        self.assertIsNone(first.intersect(second))
        self.assertEqual(first.intersect(timebase.TimeRange.of_frames(12, 24, 24)),
                         timebase.TimeRange.of_frames(12, 12, 24))
        with self.assertRaises(ValueError):
            timebase.TimeRange(0, -1)


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
