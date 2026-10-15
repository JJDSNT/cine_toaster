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

    return corner_pin(image, transform_corners(translate=translate, scale=scale, rotate=rotate, pivot=pivot,
                                               perspective=perspective, aspect=aspect), aspect)


def rotation(angles: Any) -> np.ndarray:
    """The turn every warp makes from its `rotate`, decided once (CT-0075): three angles in degrees about x, y
    and z, applied x first; one number is a turn in the picture's plane (about z), as an editor means it."""

    values = np.asarray(angles if angles is not None else 0.0, dtype=np.float64).reshape(-1)
    rx, ry, rz = (values.tolist() + [0.0, 0.0])[:3] if values.size >= 2 else [0.0, 0.0, float(values[0]) if values.size else 0.0]
    a, b, c = np.radians([rx, ry, rz])
    turn_x = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    turn_y = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
    turn_z = np.array([[np.cos(c), -np.sin(c), 0], [np.sin(c), np.cos(c), 0], [0, 0, 1]])
    return turn_z @ turn_y @ turn_x


def camera_distance(perspective: float | None) -> float | None:
    """How far the camera stands from the picture (in picture heights) for a vertical field of view in degrees;
    None for no perspective (an orthographic view). One camera for every warp (CT-0075)."""

    return 0.5 / math.tan(math.radians(float(perspective)) / 2) if perspective else None


def transform_corners(*, translate: Any, scale: Any, rotate: Any, pivot: Any, perspective: float,
                      aspect: float) -> list[list[float]]:
    """Where the picture's four corners land (fractions of the frame): the geometry every renderer shares."""

    translate = np.broadcast_to(np.asarray(translate, dtype=np.float64), (2,))
    scale = np.broadcast_to(np.asarray(scale, dtype=np.float64), (2,))
    pivot = np.broadcast_to(np.asarray(pivot, dtype=np.float64), (2,))
    # The picture as a plane in 3D, in units of its height, centred on the pivot.
    corners = []
    for x, y in UNIT:
        px, py = (x - pivot[0]) * aspect * scale[0], (y - pivot[1]) * scale[1]
        corners.append(np.array([px, py, 0.0]))
    turn = rotation(rotate)
    distance = camera_distance(perspective)
    target = []
    for corner in corners:
        x, y, z = turn @ corner
        if distance is not None:  # seen from a camera at `distance`, looking at the pivot
            factor = distance / max(distance + z, 1e-6)
            x, y = x * factor, y * factor
        target.append([(x / aspect) + pivot[0] + translate[0], y + pivot[1] + translate[1]])
    return target


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


# --- a picture on a 3D surface (SPEC-0012 warp.surface) -------------------------------

SHAPES = ("plane", "sphere", "cylinder", "page")


def _surface_points(shape: str, morph: float, u: np.ndarray, v: np.ndarray, aspect: float) -> np.ndarray:
    """Where each (u, v) of the picture sits in 3D, in units of the picture's height, its centre at the origin.

    ``morph`` goes from 0 (the flat picture) to 1 (the full shape): the picture is bent around a radius that
    shrinks as it grows, so it wraps itself onto the shape rather than jumping to it -- a ball forming, a
    tube rolling up, a page turning.
    """

    x, y = (u - 0.5) * aspect, (v - 0.5)
    t = float(np.clip(morph, 0.0, 1.0))
    if shape == "plane" or t <= 1e-4:
        return np.stack([x, y, np.zeros_like(x)], axis=-1)
    if shape == "sphere":
        radius = (aspect / (2 * np.pi)) / t  # at 1 the picture's width goes once round the ball
        lon, lat = x / radius, np.clip(y / radius, -np.pi / 2, np.pi / 2)
        return np.stack([radius * np.sin(lon) * np.cos(lat), radius * np.sin(lat),
                         radius - radius * np.cos(lon) * np.cos(lat)], axis=-1)
    if shape == "cylinder":
        radius = (aspect / (2 * np.pi)) / t
        angle = x / radius
        return np.stack([radius * np.sin(angle), y, radius - radius * np.cos(angle)], axis=-1)
    if shape == "page":  # turned from the right edge: the fold line travels across as the morph grows
        radius = 0.08
        fold = aspect / 2 - t * (aspect + np.pi * radius)
        beyond = np.maximum(x - fold, 0.0)
        angle = np.minimum(beyond / radius, np.pi)
        flat_part = np.maximum(beyond - np.pi * radius, 0.0)  # past half a turn the page lies back, reversed
        px = np.where(x > fold, fold + radius * np.sin(angle) - flat_part, x)
        pz = np.where(x > fold, -(radius - radius * np.cos(angle)), 0.0)  # lifted toward the camera
        pz = np.where(beyond > np.pi * radius, -2 * radius, pz)
        return np.stack([px, y, pz], axis=-1)
    raise ValueError(f"no surface {shape!r}")



def surface(image: np.ndarray, *, shape: str, morph: float, rotate: Any, translate: Any, scale: float,
            perspective: float, light: float, detail: int, supersample: int, aspect: float) -> tuple[np.ndarray, np.ndarray]:
    """The picture mapped onto a 3D surface and seen through a camera: (picture with alpha, depth).

    The surface is a mesh of ``detail`` cells across, turned about its own centre, moved (x and y in
    fractions of the frame, z in picture heights away from the camera), and rasterised with a depth buffer,
    so a ball's far side is hidden and a tube shows its inside where it should. ``light`` darkens faces
    turned away from the camera, as a lamp beside the lens would. Drawn ``supersample`` times larger and
    reduced, so its edge has coverage.
    """

    height, width = image.shape[:2]
    big_w, big_h = width * supersample, height * supersample
    mesh = surface_mesh(shape=shape, morph=morph, rotate=rotate, translate=translate, scale=scale,
                        perspective=perspective, light=light, detail=detail, aspect=aspect)
    gu, gv, z, shade = mesh["u"], mesh["v"], mesh["z"], mesh["shade"]
    sx, sy = mesh["x"] * big_w, mesh["y"] * big_h
    rows, columns = gu.shape[0] - 1, gu.shape[1] - 1
    del mesh
    return _rasterise(image, gu, gv, z, shade, sx, sy, rows, columns, big_w, big_h, width, height, supersample)


def surface_mesh(*, shape: str, morph: float, rotate: Any, translate: Any, scale: float, perspective: float,
                 light: float, detail: int, aspect: float) -> dict[str, np.ndarray]:
    """The surface's mesh as every renderer draws it: per vertex its place on the screen (x, y as fractions of
    the frame), its distance from the camera (z), its place in the picture (u, v) and its light."""

    columns = max(8, int(detail))
    rows = max(4, int(round(columns / aspect)))
    gu, gv = np.meshgrid(np.linspace(0, 1, columns + 1), np.linspace(0, 1, rows + 1))
    points = _surface_points(shape, morph, gu, gv, aspect)
    centre = points.reshape(-1, 3).mean(axis=0) if shape in ("sphere", "cylinder") else np.zeros(3)
    points = (points - centre) * float(scale)
    points = points @ rotation(rotate).T
    move = (list(np.asarray(translate, dtype=np.float64).reshape(-1)) + [0.0, 0.0, 0.0])[:3]
    distance = camera_distance(perspective) or 1e6  # no perspective: a camera far enough to be orthographic
    z = points[..., 2] + move[2] + (centre[2] * float(scale) if shape in ("sphere", "cylinder") else 0.0)
    factor = distance / np.maximum(distance + z, 1e-6)
    sx = (points[..., 0] * factor) / aspect + 0.5 + move[0]
    sy = (points[..., 1] * factor) + 0.5 + move[1]

    # A normal per vertex, from the mesh's neighbours, for the light.
    du = np.gradient(points, axis=1)
    dv = np.gradient(points, axis=0)
    normal = np.cross(du, dv)
    normal /= np.maximum(np.linalg.norm(normal, axis=-1, keepdims=True), 1e-9)
    shade = 1.0 - float(light) * (1.0 - np.abs(normal[..., 2]))
    return {"x": sx, "y": sy, "z": z, "u": gu, "v": gv, "shade": shade}


def _rasterise(image: np.ndarray, gu: np.ndarray, gv: np.ndarray, z: np.ndarray, shade: np.ndarray, sx: np.ndarray,
               sy: np.ndarray, rows: int, columns: int, big_w: int, big_h: int, width: int, height: int,
               supersample: int) -> tuple[np.ndarray, np.ndarray]:
    depth_buffer = np.full((big_h, big_w), np.inf, dtype=np.float64)
    u_buffer = np.zeros((big_h, big_w), dtype=np.float32)
    v_buffer = np.zeros((big_h, big_w), dtype=np.float32)
    s_buffer = np.ones((big_h, big_w), dtype=np.float32)
    covered = np.zeros((big_h, big_w), dtype=bool)

    def triangle(a: tuple[int, int], b: tuple[int, int], c: tuple[int, int]) -> None:
        xs = np.array([sx[a], sx[b], sx[c]])
        ys = np.array([sy[a], sy[b], sy[c]])
        x0, x1 = max(int(np.floor(xs.min())), 0), min(int(np.ceil(xs.max())), big_w - 1)
        y0, y1 = max(int(np.floor(ys.min())), 0), min(int(np.ceil(ys.max())), big_h - 1)
        if x0 > x1 or y0 > y1:
            return
        area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
        if abs(area) < 1e-9:
            return
        py, px = np.mgrid[y0:y1 + 1, x0:x1 + 1].astype(np.float64)
        px += 0.5
        py += 0.5
        w0 = ((xs[1] - px) * (ys[2] - py) - (xs[2] - px) * (ys[1] - py)) / area
        w1 = ((xs[2] - px) * (ys[0] - py) - (xs[0] - px) * (ys[2] - py)) / area
        w2 = 1.0 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            return
        zs = np.array([z[a], z[b], z[c]])
        here = w0 * zs[0] + w1 * zs[1] + w2 * zs[2]
        region = (slice(y0, y1 + 1), slice(x0, x1 + 1))
        nearer = inside & (here < depth_buffer[region])
        if not nearer.any():
            return
        depth_buffer[region][nearer] = here[nearer]
        for buffer, values in ((u_buffer, (gu[a], gu[b], gu[c])), (v_buffer, (gv[a], gv[b], gv[c])),
                               (s_buffer, (shade[a], shade[b], shade[c]))):
            buffer[region][nearer] = (w0 * values[0] + w1 * values[1] + w2 * values[2])[nearer]
        covered[region][nearer] = True

    for row in range(rows):
        for column in range(columns):
            a, b = (row, column), (row, column + 1)
            c, d = (row + 1, column), (row + 1, column + 1)
            triangle(a, b, d)
            triangle(a, d, c)

    # The picture read where each covered pixel of the surface falls on it; then reduced to the frame.
    big_picture = from_fractions(image, u_buffer, v_buffer, "extend") * covered[..., None]
    big_picture[..., :3] *= s_buffer[..., None]
    reduced = big_picture.reshape(height, supersample, width, supersample, -1).mean(axis=(1, 3))
    depth = depth_buffer.reshape(height, supersample, width, supersample).min(axis=(1, 3))  # inf where empty
    return reduced.astype(np.float32), depth.astype(np.float32)
