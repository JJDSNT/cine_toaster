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
    "colour.grade": {"lift": 0.0, "gain": 1.0, "gamma": 1.0, "saturation": 1.0},
    "filter.blur": {"radius": 0.0, "kind": "gaussian"},
    "generate.gradient": {"kind": "linear", "colours": [[0.0, 0.0, 0.0, 1.0], [1.0, 1.0, 1.0, 1.0]], "angle": 0.0},
    "generate.source": {"colorspace": "sRGB Encoded Rec.709 (sRGB)", "alpha": "straight", "start": 0.0},
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


def threshold_spread(softness: Any) -> float:
    """The half-width of a threshold's edge, from the softness an author gives (SPEC-0011's rule)."""

    return max(float(softness or 0.0), SOFTNESS_FLOOR)


def blur_kernel(radius: float) -> tuple[float, int]:
    """A blur's Gaussian from its radius: (sigma, how many pixels each side it reaches)."""

    sigma = max(float(radius) / 2.0, 1e-3)
    return sigma, max(1, int(math.ceil(sigma * 3)))
