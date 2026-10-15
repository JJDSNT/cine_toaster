"""Time, in one place (CT-0079): frame rates as fractions, cut points on the frame grid, sound in samples.

The assembly measured three faults, all of time (see `ai-context/work/CT-0079-time-base.md`):
a cut point between two frames -- the picture starts on a whole frame, the sound at
the exact second, half a frame apart; an NTSC rate rounded to 29.97 and written as
2997/100; sounds placed in whole milliseconds. Every conversion between seconds,
frames and samples goes through here, so the representation can change in one
module -- FilmCraft's integer ticks are the candidate (the decision is CT-0079's) --
without touching the graph's operators.

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
