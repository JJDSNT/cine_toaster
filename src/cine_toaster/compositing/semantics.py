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
    "colour.grade": {"lift": 0.0, "gain": 1.0, "gamma": 1.0, "saturation": 1.0},
    "filter.blur": {"radius": 0.0, "kind": "gaussian"},
    "generate.gradient": {"kind": "linear", "colours": [[0.0, 0.0, 0.0, 1.0], [1.0, 1.0, 1.0, 1.0]], "angle": 0.0},
    "generate.source": {"colorspace": "sRGB Encoded Rec.709 (sRGB)", "alpha": "straight", "start": 0.0},
}

#: The smallest spread a threshold's edge has: a hard edge is still one level wide, never a division by zero.
SOFTNESS_FLOOR = 0.002


def default(op: str, key: str, fallback: Any = None) -> Any:
    return DEFAULTS.get(op, {}).get(key, fallback)


def threshold_spread(softness: Any) -> float:
    """The half-width of a threshold's edge, from the softness an author gives (SPEC-0011's rule)."""

    return max(float(softness or 0.0), SOFTNESS_FLOOR)


def blur_kernel(radius: float) -> tuple[float, int]:
    """A blur's Gaussian from its radius: (sigma, how many pixels each side it reaches)."""

    sigma = max(float(radius) / 2.0, 1e-3)
    return sigma, max(1, int(math.ceil(sigma * 3)))
