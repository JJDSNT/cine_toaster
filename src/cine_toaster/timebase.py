"""Time, in one place (CT-0079): frame rates as fractions, cut points on the frame grid, sound in samples.

The assembly measured three faults, all of time (see `ai-context/work/CT-0079-time-base.md`):
a cut point between two frames -- the picture starts on a whole frame, the sound at
the exact second, half a frame apart; an NTSC rate rounded to 29.97 and written as
2997/100; sounds placed in whole milliseconds. Every conversion between seconds,
frames and samples goes through here, so the representation can change in one
module without touching the graph's operators.

The decision (ADR 0023): exact fractions to compute; FilmCraft's integer ticks
(254,016,000,000 a second) to store and exchange -- converted exactly, or
quantised only by a named policy; a person's YAML keeps seconds, frames or
timecode. A frame index, a sample index, an instant in ticks and a half-open
range are four different things, and each has its own name here.

Rates are exact fractions. A rate given as a decimal (29.97, or a float computed
from a fraction) is read as the nearest fraction with a denominator up to 1001,
which recovers every broadcast rate (30000/1001, 24000/1001, 60000/1001) exactly.
Ranges are half-open: a shot of `n` frames from frame `k` holds frames k to k+n-1,
and the next starts at k+n.
"""

from __future__ import annotations

import math
from fractions import Fraction

#: The cut's sound: one rate for every piece and the mix.
SAMPLE_RATE = 48000
#: Broadcast rates are n/1001; any other is whole or a simple fraction.
LARGEST_DENOMINATOR = 1001
#: The rate, in decimals, that productions write for an NTSC rate.
NTSC = {"23.976": Fraction(24000, 1001), "29.97": Fraction(30000, 1001), "59.94": Fraction(60000, 1001),
        "47.952": Fraction(48000, 1001), "119.88": Fraction(120000, 1001)}


def rate(value: object) -> Fraction:
    """A frame rate as an exact fraction: from "30000/1001", "29.97", 29.97, 29.97002997..., or 24."""

    if isinstance(value, Fraction):
        return value
    text = str(value).strip()
    if text in NTSC:
        return NTSC[text]
    if "/" in text:
        numerator, _, denominator = text.partition("/")
        exact = Fraction(int(numerator), int(denominator or 1))
    else:
        exact = Fraction(text)
    near = exact.limit_denominator(LARGEST_DENOMINATOR)
    # 29.97 written as a decimal is NTSC: what a probe or a person rounds it to.
    for ntsc in NTSC.values():
        if abs(float(near) - float(ntsc)) < 5e-4:
            return ntsc
    return near


def ffmpeg_rate(value: object) -> str:
    """The rate as FFmpeg is told it: a fraction, never a rounded decimal."""

    exact = rate(value)
    return str(exact.numerator) if exact.denominator == 1 else f"{exact.numerator}/{exact.denominator}"


def frame_at(seconds: float | Fraction, fps: object) -> int:
    """The frame of the grid nearest `seconds` (a cut point snaps to it)."""

    return int(math.floor(Fraction(seconds) * rate(fps) + Fraction(1, 2)))


def seconds_of(frame: int, fps: object) -> Fraction:
    """Where frame `frame` starts, exactly."""

    return Fraction(frame) / rate(fps)


def snap(seconds: float, fps: object) -> float:
    """A cut point moved to the nearest frame boundary of the picture it cuts."""

    return float(seconds_of(frame_at(seconds, fps), fps))


def samples_of_frames(frames: int, fps: object, sample_rate: int = SAMPLE_RATE) -> int:
    """The sample where frame `frames` starts. From the frame count, never from summed lengths: a frame at
    30000/1001 is 1601.6 samples, so each position is rounded once, from the film's start, and never drifts."""

    return int(math.floor(Fraction(frames) * sample_rate / rate(fps) + Fraction(1, 2)))


def samples(seconds: float | Fraction, sample_rate: int = SAMPLE_RATE) -> int:
    """The sample nearest `seconds`."""

    return int(math.floor(Fraction(seconds) * sample_rate + Fraction(1, 2)))


def seek(seconds: float | Fraction) -> str:
    """A position for FFmpeg's `-ss`, never past the instant: floored to the microsecond, so a frame starting
    exactly there is the first one read (a rounded-up decimal would skip it)."""

    micro = math.floor(Fraction(seconds) * 1_000_000)
    return f"{max(0, micro) / 1_000_000:.6f}"


# --- Ticks: the stored and exchanged form (ADR 0023) -------------------------------------------------------

#: FilmCraft's and EffectCraft's base: 2^12 x 3^4 x 5^6 x 7^2 ticks a second -- every broadcast frame (x1001)
#: and every common sample rate is a whole number of them. A rate with another prime (11 or 13 fps) is not.
TICKS_PER_SECOND = 254_016_000_000
#: The largest instant or length stored: FilmCraft's bound, a quarter of a signed 64-bit integer (about 105
#: days), so sums and offsets of stored times never overflow where ticks are 64-bit.
TICK_LIMIT = (2**63 - 1) // 4
#: How a value that is not a whole number of ticks may be brought to one -- only when asked, by name.
ROUNDINGS = ("floor", "ceil", "half_up", "half_even")


class NotRepresentable(ValueError):
    """A time that is not a whole number of ticks, converted without a rounding policy; or one beyond
    `TICK_LIMIT`."""


def _bounded(ticks: int) -> int:
    if abs(ticks) > TICK_LIMIT:
        raise NotRepresentable(f"{ticks} ticks is beyond the stored limit (+/-{TICK_LIMIT}, about "
                               f"{TICK_LIMIT // TICKS_PER_SECOND // 86400} days)")
    return ticks


def _seconds(value: float | Fraction | int | str) -> Fraction:
    return value if isinstance(value, Fraction) else Fraction(str(value)) if isinstance(value, str) else Fraction(value)


def representable(seconds: float | Fraction | int | str) -> bool:
    return (_seconds(seconds) * TICKS_PER_SECOND).denominator == 1


def to_ticks(seconds: float | Fraction | int | str, *, rounding: str | None = None) -> int:
    """Seconds (best given as a Fraction) as ticks. Exact by default: a value that is not a whole number of
    ticks is refused (`NotRepresentable`), never rounded silently. With `rounding` -- floor, ceil, half_up,
    half_even -- it is quantised by that policy, as the caller chose."""

    scaled = _seconds(seconds) * TICKS_PER_SECOND
    if scaled.denominator == 1:
        return _bounded(int(scaled))
    if rounding is None:
        raise NotRepresentable(f"{_seconds(seconds)} s is not a whole number of ticks "
                               f"({TICKS_PER_SECOND} a second); give a rounding policy, or keep the fraction")
    if rounding == "floor":
        return _bounded(math.floor(scaled))
    if rounding == "ceil":
        return _bounded(math.ceil(scaled))
    if rounding == "half_up":
        return _bounded(math.floor(scaled + Fraction(1, 2)))
    if rounding == "half_even":
        return _bounded(round(scaled))  # Fraction rounds halves to even
    raise ValueError(f"rounding is one of {', '.join(ROUNDINGS)}, not {rounding!r}")


def from_ticks(ticks: int) -> Fraction:
    """Ticks as exact seconds."""

    return Fraction(int(ticks), TICKS_PER_SECOND)


def tick_of_frame(frame: int, fps: object) -> int:
    """Where frame index `frame` starts, in ticks -- exact, or refused at a rate the base does not hold."""

    return to_ticks(seconds_of(frame, fps))


def frame_of_tick(ticks: int, fps: object) -> int:
    """The index of the frame showing at `ticks`: the last one started (a frame holds until the next)."""

    return math.floor(from_ticks(ticks) * rate(fps))


def tick_of_sample(sample: int, sample_rate: int = SAMPLE_RATE) -> int:
    return to_ticks(Fraction(sample, sample_rate))


def sample_of_tick(ticks: int, sample_rate: int = SAMPLE_RATE) -> int:
    """The index of the sample sounding at `ticks`."""

    return math.floor(from_ticks(ticks) * sample_rate)


def to_record(seconds: float | Fraction | int | str, *, rounding: str = "half_even") -> dict[str, object]:
    """A time as a record stores it: `{"ticks": n}` when exact; otherwise the ticks quantised by `rounding` and
    the exact fraction kept beside them (`"exact": "1/11"`), so a source at an uncommon rate loses nothing."""

    value = _seconds(seconds)
    if representable(value):
        return {"ticks": to_ticks(value)}
    return {"ticks": to_ticks(value, rounding=rounding), "exact": f"{value.numerator}/{value.denominator}"}


def from_record(record: dict[str, object]) -> Fraction:
    """A stored time, exact: its fraction when it kept one, else its ticks."""

    if record.get("exact"):
        return Fraction(str(record["exact"]))
    return from_ticks(int(record["ticks"]))  # type: ignore[arg-type]


class TimeRange:
    """A half-open stretch of time in ticks: a start and a duration. It holds `start` and not `start +
    duration`, so two ranges that meet do not overlap and a cut has no frame in two shots."""

    __slots__ = ("start", "duration")

    def __init__(self, start: int, duration: int) -> None:
        if duration < 0:
            raise ValueError("a range's duration is not negative")
        self.start, self.duration = _bounded(int(start)), _bounded(int(duration))
        _bounded(self.start + self.duration)

    @classmethod
    def between(cls, start: int, end: int) -> "TimeRange":
        return cls(start, end - start)

    @classmethod
    def of_frames(cls, first: int, count: int, fps: object) -> "TimeRange":
        """`count` frames from frame index `first`."""

        return cls.between(tick_of_frame(first, fps), tick_of_frame(first + count, fps))

    @property
    def end(self) -> int:
        return self.start + self.duration

    def contains(self, ticks: int) -> bool:
        return self.start <= ticks < self.end

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start < other.end and other.start < self.end

    def intersect(self, other: "TimeRange") -> "TimeRange | None":
        start, end = max(self.start, other.start), min(self.end, other.end)
        return TimeRange.between(start, end) if end > start else None

    def frames(self, fps: object) -> range:
        """The frame indices that start inside the range."""

        exact = rate(fps)
        first = math.ceil(from_ticks(self.start) * exact)
        last = math.ceil(from_ticks(self.end) * exact)
        return range(first, last)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TimeRange) and (self.start, self.duration) == (other.start, other.duration)

    def __hash__(self) -> int:
        return hash((self.start, self.duration))

    def __repr__(self) -> str:
        return f"TimeRange(start={self.start}, duration={self.duration})"
