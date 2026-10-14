"""Measuring a track (SPEC-0012 §3, track.measure) with OpenCV: data apart from the algorithm that made it.

The result is the track format of SPEC-0012 §1 -- {kind, frames: [{points}] or
[{corners}]} in fractions of the picture -- whatever measured it, so a track
from Blender or drawn by a person is used the same way.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..errors import ValidationError


def measure(pictures: np.ndarray, kind: str, region: Any, working: str) -> dict[str, Any]:
    """Points (their centre) or a plane (four corners) followed through ``pictures`` (frames, H, W, 4)."""

    try:
        import cv2
    except ImportError as error:
        raise ValidationError("Tracking needs OpenCV (opencv-python)") from error
    if kind not in ("point", "plane"):
        raise ValidationError(f"The reference tracks points and planes, not {kind!r} (a camera solve is C7)")
    from .reference import ENCODED, convert

    frames, height, width = pictures.shape[:3]
    grey = []
    for picture in pictures:
        alpha = picture[..., 3:4]
        rgb = np.divide(picture[..., :3], alpha, out=np.zeros_like(picture[..., :3]), where=alpha > 1e-6)
        encoded = convert(rgb, working, ENCODED)
        grey.append((np.clip(encoded @ np.array([0.2126, 0.7152, 0.0722], np.float32), 0, 1) * 255).astype(np.uint8))
    x0, y0, x1, y1 = (np.asarray(region, dtype=np.float32) if region is not None else np.array([0, 0, 1, 1]))
    mask = np.zeros((height, width), np.uint8)
    mask[int(y0 * height):int(y1 * height), int(x0 * width):int(x1 * width)] = 255
    start = cv2.goodFeaturesToTrack(grey[0], maxCorners=200, qualityLevel=0.01, minDistance=3, mask=mask)
    if start is None or len(start) < (4 if kind == "plane" else 1):
        raise ValidationError("Nothing in the region to track: it needs texture")
    corners0 = np.float32([[x0 * width, y0 * height], [x1 * width, y0 * height], [x1 * width, y1 * height],
                           [x0 * width, y1 * height]]).reshape(-1, 1, 2)
    points, alive = start, np.ones(len(start), bool)
    first = start.reshape(-1, 2)
    out = []
    for index in range(frames):
        if index:
            moved, status, _ = cv2.calcOpticalFlowPyrLK(grey[index - 1], grey[index], points, None)
            alive &= status.reshape(-1).astype(bool)
            points = moved
        now = points.reshape(-1, 2)[alive]
        if kind == "point":
            out.append({"points": [[float(now[:, 0].mean() / width), float(now[:, 1].mean() / height)]]})
        else:
            matrix, _ = cv2.findHomography(first[alive], now, cv2.RANSAC, 3.0)
            if matrix is None:
                raise ValidationError(f"The plane was lost at frame {index}")
            corners = cv2.perspectiveTransform(corners0, matrix).reshape(-1, 2)
            out.append({"corners": [[float(x / width), float(y / height)] for x, y in corners]})
    return {"kind": kind, "frames": out}
