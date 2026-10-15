"""What an op's parameters mean, decided once for every renderer (ADR 0022, CT-0072).

Two renderers may draw an op differently; they may not decide differently what
its parameters default to, or how a value given by the author becomes the
number the drawing uses. Those decisions live here, and the reference, the GL
renderer and the recipes built in code read them from here.
"""

from __future__ import annotations

import math
from typing import Any

#: Parameters an author may leave out, and what they then are.
DEFAULTS: dict[str, dict[str, Any]] = {
    "signal.luma": {"transfer": "sRGB"},
    "matte.from_signal": {"low": 0.0, "high": 1.0, "gamma": 1.0, "invert": False},
    "matte.threshold": {"softness": 0.0},
    "matte.key": {"invert": False, "softness": 0.0},
    "merge.over": {"mix": 1.0},
    "merge.blend": {"mix": 1.0},
    "warp.transform": {"translate": [0.0, 0.0], "scale": [1.0, 1.0], "rotate": 0.0, "pivot": [0.5, 0.5],
                       "perspective": 0.0},
    "warp.displace": {"strength": 0.1, "edge": "transparent"},
    "warp.procedural": {"amount": 1.0, "frequency": 4.0, "centre": [0.5, 0.5], "edge": "transparent"},
    "warp.surface": {"morph": 1.0, "rotate": [0.0, 0.0, 0.0], "translate": [0.0, 0.0, 0.0], "scale": 1.0,
                     "perspective": 35.0, "light": 0.4, "detail": 48, "supersample": 2},
    "colour.despill": {"limit": "max", "amount": 1.0},
    "filter.bevel": {"radius": 6.0, "depth": 1.0, "angle": 135.0, "elevation": 35.0, "highlight": 0.6, "shadow": 0.6},
    "colour.grade": {"lift": 0.0, "gain": 1.0, "gamma": 1.0, "saturation": 1.0},
    "filter.blur": {"radius": 0.0, "kind": "gaussian"},
    "generate.gradient": {"kind": "linear", "colours": [[0.0, 0.0, 0.0, 1.0], [1.0, 1.0, 1.0, 1.0]], "angle": 0.0},
    # A source's colour space and alpha are its file's convention unless said (`reference.read`, CT-0077).
    "generate.source": {"start": 0.0},
    # A pulse per beat: rising over `attack` before it, falling over `decay` after it, each with its ease;
    # pulses that meet keep the higher (`max`) or add up to a full one (`add`) (C3, CT-0074).
    "curve.beats": {"attack": 0.02, "decay": 0.2, "every": 1, "low": 0.0, "high": 1.0,
                    "attack_ease": "linear", "decay_ease": "linear", "overlap": "max"},
}

#: The named eases (SPEC-0012 §6); any other ease is a cubic Bezier given as [x1, y1, x2, y2].
EASE_NAMES = ("linear", "in", "out", "in-out", "hold")

#: The smallest spread a threshold's edge has: a hard edge is still one level wide, never a division by zero.
SOFTNESS_FLOOR = 0.002


#: Lengths given in pixels (a blur's or a border's radius, a text's size) are pixels of a frame this many lines
#: high, scaled to the frame being drawn: a composite looks the same at 180 lines as at 1080 (CT-0075).
REFERENCE_LINES = 720


def pixels(value: Any, height: int) -> float:
    """A length an author gave in pixels at `REFERENCE_LINES`, in pixels of a frame ``height`` lines high."""

    return float(value) * height / REFERENCE_LINES


def default(op: str, key: str, fallback: Any = None) -> Any:
    return DEFAULTS.get(op, {}).get(key, fallback)


def ease_problem(ease: Any) -> str | None:
    """Why ``ease`` is not an ease, or None: a name, or a Bezier's four numbers with its times within 0..1."""

    if isinstance(ease, (list, tuple)):
        if len(ease) != 4 or not all(isinstance(value, (int, float)) for value in ease):
            return f"a Bezier ease is four numbers (x1, y1, x2, y2), not {list(ease)!r}"
        if not (0 <= ease[0] <= 1 and 0 <= ease[2] <= 1):
            return f"a Bezier ease keeps its handles' times within 0 and 1, not {ease[0]} and {ease[2]}"
        return None
    if str(ease) not in EASE_NAMES:
        return f"no ease {ease!r}: {', '.join(EASE_NAMES)}, or a Bezier [x1, y1, x2, y2]"
    return None


def screen_channel(colour: Any) -> int:
    """Which channel a key colour is made of -- 0 red, 1 green, 2 blue: the one a spill raises (CT-0075)."""

    values = [float(c) for c in (list(colour) + [0.0, 0.0, 0.0])[:3]]
    return max(range(3), key=lambda index: values[index])


LETTER_KEYS = ("offset", "rotate", "scale", "opacity")
LETTER_ORDERS = ("forward", "backward", "centre", "random")


def letters_problem(spec: Any) -> str | None:
    """Why a per-letter animator cannot be drawn, or None (C6b, CT-0078). An animator is `{keys: [{t, offset,
    rotate, scale, opacity, ease}], stagger, order, start, seed, wave: {amplitude, frequency, phase}}`: each
    letter plays the keys from its own start, `stagger` seconds after the one before it in `order`."""

    if not isinstance(spec, dict):
        return "is a mapping: {keys, stagger, order, start, wave}"
    unknown = set(spec) - {"keys", "stagger", "order", "start", "seed", "wave"}
    if unknown:
        return f"has no {', '.join(sorted(unknown))}"
    if spec.get("order", "forward") not in LETTER_ORDERS:
        return f"orders letters {spec.get('order')!r}; the orders are {', '.join(LETTER_ORDERS)}"
    for name in ("stagger", "start"):
        if not isinstance(spec.get(name, 0.0), (int, float)):
            return f"gives {name} as a number of seconds"
    keys = spec.get("keys") or []
    if not isinstance(keys, list):
        return "gives its keys as a list"
    for key in keys:
        if not isinstance(key, dict) or "t" not in key:
            return "has a key with no time `t`"
        extra = set(key) - {"t", "ease", *LETTER_KEYS}
        if extra:
            return f"has a key with {', '.join(sorted(extra))}; a key gives {', '.join(LETTER_KEYS)} and an ease"
        if "ease" in key and ease_problem(key["ease"]):
            return ease_problem(key["ease"])
    wave = spec.get("wave")
    if wave is not None and (not isinstance(wave, dict) or set(wave) - {"amplitude", "frequency", "phase"}):
        return "gives its wave as {amplitude, frequency, phase}"
    if not keys and wave is None:
        return "has neither keys nor a wave: nothing would move"
    return None


def light_direction(angle: float, elevation: float) -> tuple[float, float, float]:
    """Where light comes from, for a bevel: `angle` in degrees counter-clockwise from the right as the frame is
    seen (135 is the upper left), `elevation` above the frame; in the picture's own axes (y down)."""

    a, e = math.radians(float(angle)), math.radians(float(elevation))
    return math.cos(e) * math.cos(a), -math.cos(e) * math.sin(a), math.sin(e)


def hue_turn(degrees: float) -> list[list[float]]:
    """The matrix that turns colours about the grey axis by `degrees`: colour cycling (colour.cycle)."""

    angle = math.radians(float(degrees))
    cos, sin = math.cos(angle), math.sin(angle)
    k = 1.0 / math.sqrt(3.0)
    cross = [[0.0, -k, k], [k, 0.0, -k], [-k, k, 0.0]]
    return [[cos * (1.0 if row == col else 0.0) + sin * cross[row][col] + (1 - cos) * k * k for col in range(3)]
            for row in range(3)]


def threshold_spread(softness: Any) -> float:
    """The half-width of a threshold's edge, from the softness an author gives (SPEC-0011's rule)."""

    return max(float(softness or 0.0), SOFTNESS_FLOOR)


def blur_kernel(radius: float) -> tuple[float, int]:
    """A blur's Gaussian from its radius: (sigma, how many pixels each side it reaches)."""

    sigma = max(float(radius) / 2.0, 1e-3)
    return sigma, max(1, int(math.ceil(sigma * 3)))


#: The policy for an instant that is *approximate* -- a map curve with eases, noise or combinations, computed in
#: floating point: within this many frames of a boundary, it is on the boundary (a float32 curve puts 2x
#: speed's instants at 6.9999999 frames where they are 7, and a plain floor stutters). An *exact* instant -- a
#: Fraction, from a map of linear or held keys -- is never moved: a boundary stays a boundary and an instant
#: just before it stays before it (CT-0080, after the user's review).
BOUNDARY_TOLERANCE = 1e-6


def _floor(frames: Any) -> int:
    from fractions import Fraction

    if isinstance(frames, Fraction):
        return math.floor(frames)
    return math.floor(frames + BOUNDARY_TOLERANCE)


#: How a remap obtains the picture at a source instant (C7, CT-0080) -- apart from which instant it is.
REMAP_INTERPOLATIONS = ("nearest", "blend")


def remap_samples(seconds: Any, fps: Any, interpolation: str = "nearest", *, clamp: bool = True) -> list[tuple[int, float]]:
    """The source frames, and their weights, that make the picture at source instant `seconds`.

    The remap decides *which instant*; this decides *how it is pictured* -- so an optical or a model's
    interpolation is one more name here, not another remap. Frames are sampled at their centres:
    - nearest: the frame whose centre is nearest, which is the frame that *contains* the instant (ADR 0023's
      frame of an instant: the last one started) -- `floor(seconds * fps)`;
    - blend: the two frames whose centres stand either side of the instant, weighted by where it falls
      between them (`floor` finds them, the fraction weighs them).
    Frames before the first are the first (unless `clamp` is off: a source with a pre-roll has frames before
    its local zero, at negative indices); past the last, the caller holds the last. An exact instant (a
    Fraction, with the rate as one) is placed exactly; an approximate one by `BOUNDARY_TOLERANCE`.
    """

    from fractions import Fraction

    if isinstance(seconds, Fraction):
        from ..timebase import rate

        fps = rate(fps)
    lowest = 0 if clamp else -(10**12)
    if interpolation == "nearest":
        return [(max(lowest, _floor(seconds * fps)), 1.0)]
    if interpolation != "blend":
        raise ValueError(f"interpolation is one of {', '.join(REMAP_INTERPOLATIONS)}, not {interpolation!r}")
    position = seconds * fps - Fraction(1, 2) if isinstance(seconds, Fraction) else seconds * fps - 0.5
    first = _floor(position)
    weight = max(0.0, float(position - first))
    if first < lowest:
        return [(lowest, 1.0)]
    return [(first, 1.0 - weight)] + ([(first + 1, weight)] if weight > 1e-9 else [])
