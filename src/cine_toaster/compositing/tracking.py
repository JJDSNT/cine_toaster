"""Measuring a track (SPEC-0012 §3, track.measure) with OpenCV: data apart from the algorithm that made it.

The result is the track format of SPEC-0012 §1 -- {kind, frames: [{points} or
{corners}]} in fractions of the picture -- whatever measured it, so a track
from Blender or drawn by a person is used the same way. Each entry also says
how much it can be trusted (C7 step 5, CT-0080):

- `confidence`, 0 to 1: of the features followed into this frame, the share
  that pass a forward-backward check (followed to it and back, they land
  within `FB_LIMIT` pixels of where they were) -- and, for a plane, that agree
  with its homography (RANSAC inliers) -- lowered when fewer than `SOLID`
  remain. Per step, not since the start: features leaving the frame in a
  pan thin the track without making it doubtful; an occlusion makes it so;
- `reseeded`: true where the features had thinned out below `RESEED_BELOW` of
  what they started with, and fresh ones were found in the region where the
  track then stood -- the track carries on from there without a jump;
- `reacquired`: true where the track had been lost (the view covered, the
  texture gone) and was found again by its last confident appearance, looked
  for around where it was (`REACQUIRE_REACH` regions away) -- its confidence
  then is how well that appearance matched. Lost entries keep the last place,
  at no confidence, so the stretch is plain to see and to correct.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..errors import ValidationError

#: Bumped whenever the measuring changes what it would measure: tracks measured by another version are stale.
TRACKER = "opencv-lk"
TRACKER_VERSION = 2
#: A feature followed forward then back must land this close (pixels at the measured size) to be kept.
FB_LIMIT = 1.0
#: Below this share of its starting features (or fewer than `FEWEST`), a track finds fresh ones.
RESEED_BELOW = 0.4
FEWEST = 8
#: Fewer good features than this, and an entry's confidence is lowered in proportion.
SOLID = 16
#: How far around its last place a lost track is looked for, in regions (its width and height).
REACQUIRE_REACH = 1.5
#: A match at least this good (normalised correlation) re-acquires a lost track.
REACQUIRE_MATCH = 0.6


def measure(pictures: Any, kind: str, region: Any, working: str, frames: int | None = None) -> dict[str, Any]:
    """Points (their centre) or a plane (four corners) followed through the frames, each with a confidence.

    ``pictures`` is an array (frames, H, W, 4) or a function giving frame ``i``; with a function, only two
    frames are ever held, so a long clip is tracked in the memory of two.
    """

    try:
        import cv2
    except ImportError as error:
        raise ValidationError("Tracking needs OpenCV (opencv-python)") from error
    if kind not in ("point", "plane"):
        raise ValidationError(f"The reference tracks points and planes, not {kind!r} (a camera solve is C8's)")
    from .reference import ENCODED, convert

    frame_of = pictures if callable(pictures) else (lambda index: pictures[index])
    count = frames if callable(pictures) else len(pictures)

    def grey(index: int) -> np.ndarray:
        picture = np.asarray(frame_of(index), dtype=np.float32)
        alpha = picture[..., 3:4]
        rgb = np.divide(picture[..., :3], alpha, out=np.zeros_like(picture[..., :3]), where=alpha > 1e-6)
        encoded = convert(rgb, working, ENCODED)
        return (np.clip(encoded @ np.array([0.2126, 0.7152, 0.0722], np.float32), 0, 1) * 255).astype(np.uint8)

    previous = grey(0)
    height, width = previous.shape
    x0, y0, x1, y1 = (np.asarray(region, dtype=np.float64) if region is not None else np.array([0, 0, 1, 1.0]))
    box = np.float64([[x0 * width, y0 * height], [x1 * width, y0 * height], [x1 * width, y1 * height],
                      [x0 * width, y1 * height]])

    def seed(picture: np.ndarray, corners: np.ndarray) -> np.ndarray | None:
        mask = np.zeros(picture.shape, np.uint8)
        cv2.fillConvexPoly(mask, np.round(corners).astype(np.int32), 255)
        found = cv2.goodFeaturesToTrack(picture, maxCorners=200, qualityLevel=0.01, minDistance=3, mask=mask)
        return found.reshape(-1, 2).astype(np.float32) if found is not None else None

    points = seed(previous, box)
    if points is None or len(points) < (4 if kind == "plane" else 1):
        raise ValidationError("Nothing in the region to track: it needs texture")
    started = len(points)
    # A point is the centre of its region, moved as its features move; a plane is its region's corners, carried
    # by the homography from the features where they were anchored (the first frame, or the last reseed).
    centre = box.mean(axis=0)
    corners = box.copy()
    anchors, anchor_corners = points.copy(), box.copy()
    out: list[dict[str, Any]] = []

    def entry(confidence: float, reseeded: bool) -> dict[str, Any]:
        made: dict[str, Any] = {"confidence": round(float(np.clip(confidence, 0.0, 1.0)), 4)}
        if kind == "point":
            made["points"] = [[float(centre[0] / width), float(centre[1] / height)]]
        else:
            made["corners"] = [[float(x / width), float(y / height)] for x, y in corners]
        if reseeded:
            made["reseeded"] = True
        return made

    def appearance(picture: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """The region's picture where the track now stands, and its top-left corner."""

        where = corners if kind == "plane" else box - box.mean(axis=0) + centre
        x_lo, y_lo = np.floor(where.min(axis=0)).astype(int)
        x_hi, y_hi = np.ceil(where.max(axis=0)).astype(int)
        x_lo, y_lo, x_hi, y_hi = max(0, x_lo), max(0, y_lo), min(width, x_hi), min(height, y_hi)
        return picture[y_lo:y_hi, x_lo:x_hi].copy(), np.array([x_lo, y_lo], np.float64)

    last_seen = appearance(previous)
    lost = False
    out.append(entry(1.0, False))
    for index in range(1, count):
        current = grey(index)
        if len(points) == 0:
            # Nothing left to follow (the view covered, the texture gone): held where it was, worth nothing --
            # until its last confident appearance is found again around there.
            template, top_left = last_seen
            found = None
            if template.size and template.std() > 2.0 and current.std() > 2.0:
                reach = (np.array(template.shape[::-1]) * REACQUIRE_REACH).astype(int)
                x_lo, y_lo = np.maximum(top_left.astype(int) - reach, 0)
                x_hi = min(width, int(top_left[0]) + template.shape[1] + reach[0])
                y_hi = min(height, int(top_left[1]) + template.shape[0] + reach[1])
                area = current[y_lo:y_hi, x_lo:x_hi]
                if area.shape[0] >= template.shape[0] and area.shape[1] >= template.shape[1]:
                    scores = cv2.matchTemplate(area, template, cv2.TM_CCOEFF_NORMED)
                    _, best, _, at = cv2.minMaxLoc(scores)
                    if best >= REACQUIRE_MATCH:
                        found = (np.array([x_lo + at[0], y_lo + at[1]], np.float64) - top_left, best)
            if found is None:
                out.append(entry(0.0, False))
                previous = current
                continue
            shift, best = found
            centre, corners = centre + shift, corners + shift
            region_now = corners if kind == "plane" else box - box.mean(axis=0) + centre
            fresh = seed(current, region_now)
            if fresh is not None and len(fresh) >= (4 if kind == "plane" else 1):
                points, anchors, anchor_corners, started = fresh, fresh.copy(), corners.copy(), len(fresh)
            made = entry(best, True)
            made["reacquired"] = True
            out.append(made)
            previous, lost = current, False
            last_seen = appearance(current)
            continue
        moved, status, _ = cv2.calcOpticalFlowPyrLK(previous, current, points.reshape(-1, 1, 2), None)
        back, back_status, _ = cv2.calcOpticalFlowPyrLK(current, previous, moved, None)
        moved = moved.reshape(-1, 2)
        error = np.linalg.norm(back.reshape(-1, 2) - points, axis=1)
        good = (status.reshape(-1) == 1) & (back_status.reshape(-1) == 1) & (error < FB_LIMIT)
        confidence = float(good.sum()) / max(1, len(points)) * min(1.0, float(good.sum()) / SOLID)
        if kind == "point":
            if good.any():
                centre = centre + (moved[good] - points[good]).mean(axis=0)
        else:
            matrix, inliers = (cv2.findHomography(anchors[good], moved[good], cv2.RANSAC, 3.0)
                               if good.sum() >= 4 else (None, None))
            if matrix is None:
                confidence = 0.0  # lost here: the last corners are held, and said to be worth nothing
            else:
                corners = cv2.perspectiveTransform(anchor_corners.reshape(-1, 1, 2), matrix).reshape(-1, 2)
                confidence *= float(inliers.mean()) if inliers is not None and len(inliers) else 0.0
        points, anchors, previous = moved[good], anchors[good], current
        reseeded = False
        if len(points) < max(FEWEST, RESEED_BELOW * started):
            # Thinned out: fresh features where the track now stands, anchored to this frame.
            region_now = corners if kind == "plane" else box - box.mean(axis=0) + centre
            fresh = seed(current, region_now)
            if fresh is not None and len(fresh) >= (4 if kind == "plane" else 1):
                points, anchors, anchor_corners = fresh, fresh.copy(), corners.copy()
                started, reseeded = len(fresh), True
        out.append(entry(confidence, reseeded))
        if confidence >= 0.5:
            last_seen = appearance(current)  # what to look for if it is lost
    return {"kind": kind, "frames": out, "measured": {"tracker": TRACKER, "version": TRACKER_VERSION,
                                                      "size": [width, height]}}


def weak_spans(track: dict[str, Any], below: float = 0.5) -> list[tuple[int, int]]:
    """The stretches of entries (first, last, inclusive) whose confidence is under `below`: where a person
    should look, or correct."""

    spans: list[tuple[int, int]] = []
    start = None
    for index, frame in enumerate(track.get("frames") or []):
        weak = float(frame.get("confidence", 1.0)) < below
        if weak and start is None:
            start = index
        if not weak and start is not None:
            spans.append((start, index - 1))
            start = None
    if start is not None:
        spans.append((start, len(track["frames"]) - 1))
    return spans
