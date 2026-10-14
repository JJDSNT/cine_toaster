"""Warps for the reference (SPEC-0012 §3, warp): every one is "where in the source does this pixel come from".

Coordinates are fractions of the picture, (0, 0) the top left. Sampling is
bilinear; outside the source is transparent (zero, premultiplied).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def sample(image: np.ndarray, sx: np.ndarray, sy: np.ndarray, edge: str = "transparent") -> np.ndarray:
    """``image`` at source pixel positions ``sx``, ``sy`` (pixel units, centres at .5 - .5 = integers).

    ``edge`` says what lies outside the source: nothing (`transparent`, SPEC-0012's default), its border
    pixels repeated (`extend`), or its reflection (`mirror`) -- what a full-frame warp usually wants.
    """

    height, width = image.shape[:2]
    if edge == "extend":
        sx, sy = np.clip(sx, 0, width - 1), np.clip(sy, 0, height - 1)
    elif edge == "mirror":
        sx = (width - 1) - np.abs(np.mod(sx, 2 * (width - 1)) - (width - 1))
        sy = (height - 1) - np.abs(np.mod(sy, 2 * (height - 1)) - (height - 1))
    planes = image if image.ndim == 3 else image[..., None]
    padded = np.pad(planes, ((1, 1), (1, 1), (0, 0)))
    x0, y0 = np.floor(sx).astype(int), np.floor(sy).astype(int)
    fx, fy = (sx - x0)[..., None], (sy - y0)[..., None]

    def at(px: np.ndarray, py: np.ndarray) -> np.ndarray:
        inside = (px >= -1) & (px <= width) & (py >= -1) & (py <= height)
        return padded[np.clip(py + 1, 0, height + 1), np.clip(px + 1, 0, width + 1)] * inside[..., None]

    out = (at(x0, y0) * (1 - fx) * (1 - fy) + at(x0 + 1, y0) * fx * (1 - fy)
           + at(x0, y0 + 1) * (1 - fx) * fy + at(x0 + 1, y0 + 1) * fx * fy).astype(np.float32)
    return out if image.ndim == 3 else out[..., 0]


def grid(shape: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Each output pixel's centre as fractions of the picture."""

    height, width = shape[:2]
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    return (xs + 0.5) / width, (ys + 0.5) / height


def from_fractions(image: np.ndarray, u: np.ndarray, v: np.ndarray, edge: str = "transparent") -> np.ndarray:
    height, width = image.shape[:2]
    return sample(image, u * width - 0.5, v * height - 0.5, edge)


def homography(source: list[list[float]], target: list[list[float]]) -> np.ndarray:
    """The 3x3 matrix taking four source points to four target points."""

    rows, rhs = [], []
    for (x, y), (u, v) in zip(source, target):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        rhs += [u, v]
    solution = np.linalg.solve(np.asarray(rows, dtype=np.float64), np.asarray(rhs, dtype=np.float64))
    return np.append(solution, 1.0).reshape(3, 3)


UNIT = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]


def corner_pin(image: np.ndarray, corners: list[list[float]], aspect: float) -> np.ndarray:
    """The picture's four corners placed at ``corners`` (fractions, clockwise from the top left)."""

    inverse = np.linalg.inv(homography(UNIT, corners))
    u, v = grid(image.shape)
    w = inverse[2, 0] * u + inverse[2, 1] * v + inverse[2, 2]
    su = (inverse[0, 0] * u + inverse[0, 1] * v + inverse[0, 2]) / w
    sv = (inverse[1, 0] * u + inverse[1, 1] * v + inverse[1, 2]) / w
    behind = w <= 0
    out = from_fractions(image, su, sv)
    out[behind] = 0
    return out


def transform(image: np.ndarray, *, translate: Any, scale: Any, rotate: Any, pivot: Any, perspective: float,
              aspect: float) -> np.ndarray:
    """Move, scale and rotate in three axes about a pivot; with a field of view, in perspective."""

    translate = np.broadcast_to(np.asarray(translate, dtype=np.float64), (2,))
    scale = np.broadcast_to(np.asarray(scale, dtype=np.float64), (2,))
    angles = np.asarray(rotate, dtype=np.float64).reshape(-1)
    rx, ry, rz = (angles if angles.size == 3 else np.array([0.0, 0.0, angles[-1] if angles.size else 0.0]))
    pivot = np.broadcast_to(np.asarray(pivot, dtype=np.float64), (2,))
    # The picture as a plane in 3D, in units of its height, centred on the pivot.
    corners = []
    for x, y in UNIT:
        px, py = (x - pivot[0]) * aspect * scale[0], (y - pivot[1]) * scale[1]
        corners.append(np.array([px, py, 0.0]))
    a, b, c = (math.radians(value) for value in (rx, ry, rz))
    turn_x = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    turn_y = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    turn_z = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    turn = turn_z @ turn_y @ turn_x
    distance = 0.5 / math.tan(math.radians(perspective) / 2) if perspective else None
    target = []
    for corner in corners:
        x, y, z = turn @ corner
        if distance is not None:  # seen from a camera at `distance`, looking at the pivot
            factor = distance / max(distance + z, 1e-6)
            x, y = x * factor, y * factor
        target.append([(x / aspect) + pivot[0] + translate[0], y + pivot[1] + translate[1]])
    return corner_pin(image, target, aspect)


def displace(image: np.ndarray, field: np.ndarray, strength: float, direction: Any,
             edge: str = "transparent") -> np.ndarray:
    """Each pixel taken from a neighbour along a field: one channel along ``direction``, two as vectors (pixels)."""

    height, width = image.shape[:2]
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    if field.ndim == 3 and field.shape[-1] >= 2:
        dx, dy = field[..., 0] * strength, field[..., 1] * strength
    else:
        values = (field if field.ndim == 2 else field[..., 0]) - 0.5
        direction = np.broadcast_to(np.asarray(direction if direction is not None else [1.0, 0.0], dtype=np.float32),
                                    (2,))
        dx, dy = values * direction[0] * strength * width, values * direction[1] * strength * height
    return sample(image, xs - dx, ys - dy, edge)


def procedural(image: np.ndarray, kind: str, amount: float, frequency: float, centre: Any,
               aspect: float, edge: str = "transparent") -> np.ndarray:
    u, v = grid(image.shape)
    cx, cy = np.broadcast_to(np.asarray(centre if centre is not None else [0.5, 0.5], dtype=np.float32), (2,))
    du, dv = (u - cx) * aspect, v - cy
    radius = np.hypot(du, dv)
    if kind == "ripple":
        push = amount * 0.02 * np.sin(radius * frequency * 2 * math.pi)
        scale = np.where(radius > 1e-6, (radius + push) / np.maximum(radius, 1e-6), 1.0)
        du, dv = du * scale, dv * scale
    elif kind == "swirl":
        angle = amount * np.clip(1 - radius / 0.5, 0, None) ** 2
        cos, sin = np.cos(angle), np.sin(angle)
        du, dv = du * cos - dv * sin, du * sin + dv * cos
    elif kind == "lens":
        factor = 1 + amount * radius * radius
        du, dv = du * factor, dv * factor
    else:
        raise ValueError(f"no procedural warp {kind!r}")
    return from_fractions(image, du / aspect + cx, dv + cy, edge)
