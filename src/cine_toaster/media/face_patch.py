from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import require


# An image editor asked to change a face regenerates the whole frame: it pulls
# colour, smooths skin, and sometimes invents objects. This reduces the edit to
# what was actually wanted -- the face -- and leaves every other pixel of the
# original untouched.

CASCADES = ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml")
SEARCH_ANGLES = (0, -20, 20, -40, 40, -60, 60)
MIN_FACE_FRACTION = 0.08
GRAIN_SIGMA = 1.2
GRAIN_SEED = 7


@dataclass(frozen=True, slots=True)
class Face:
    """A detected face: centre, size, and how far it is rotated."""

    x: float
    y: float
    width: float
    height: float
    angle: float


def match_colour(source, reference):
    """Move the edit's colour statistics onto the original's, per channel in Lab."""

    cv2 = require("cv2")
    numpy = require("numpy")
    converted = cv2.cvtColor(source, cv2.COLOR_BGR2LAB).astype(numpy.float32)
    target = cv2.cvtColor(reference, cv2.COLOR_BGR2LAB).astype(numpy.float32)
    for channel in range(3):
        values = converted[..., channel]
        wanted = target[..., channel]
        converted[..., channel] = (values - values.mean()) * (
            wanted.std() / (values.std() + 1e-6)
        ) + wanted.mean()
    return cv2.cvtColor(numpy.clip(converted, 0, 255).astype(numpy.uint8), cv2.COLOR_LAB2BGR)


def restore_grain(edited, original):
    """Give back the fine detail the editor smoothed away.

    Editors flatten skin: pores and freckles disappear, and a face without them
    next to a body with them reads as pasted on.
    """

    cv2 = require("cv2")
    numpy = require("numpy")
    base = original.astype(numpy.float32)
    edit = edited.astype(numpy.float32)
    base_detail = base - cv2.GaussianBlur(base, (0, 0), GRAIN_SIGMA)
    edit_detail = edit - cv2.GaussianBlur(edit, (0, 0), GRAIN_SIGMA)
    missing = max(0.0, float(base_detail.std() - edit_detail.std()))
    noise = numpy.random.default_rng(GRAIN_SEED).normal(0, missing, edit.shape[:2])
    return numpy.clip(edit + noise[..., None].astype(numpy.float32), 0, 255)


def detect_faces(image, limit: int = 1) -> list[Face]:
    """Find faces, including tilted ones.

    A head in a shot is rarely upright -- someone lying down, leaning in -- so
    the search is repeated on a rotated copy and the boxes mapped back.
    """

    cv2 = require("cv2")
    numpy = require("numpy")
    grey = cv2.equalizeHist(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
    height, width = grey.shape
    minimum = int(width * MIN_FACE_FRACTION)

    found: list[tuple[float, float, float, float, float, float]] = []
    for angle in SEARCH_ANGLES:
        rotation = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        rotated = cv2.warpAffine(grey, rotation, (width, height), borderMode=cv2.BORDER_REPLICATE)
        inverse = cv2.invertAffineTransform(rotation)
        for name in CASCADES:
            classifier = cv2.CascadeClassifier(cv2.data.haarcascades + name)
            for flipped in (False, True):
                candidate = cv2.flip(rotated, 1) if flipped else rotated
                for (x, y, w, h) in classifier.detectMultiScale(
                    candidate, 1.05, 6, minSize=(minimum, minimum)
                ):
                    if flipped:
                        x = width - x - w
                    centre = inverse @ numpy.array([x + w / 2, y + h / 2, 1.0])
                    found.append((w * h, centre[0], centre[1], w, h, -angle))

    found.sort(reverse=True)
    chosen: list[Face] = []
    for _area, x, y, w, h, angle in found:
        if all(abs(x - face.x) > w / 2 or abs(y - face.y) > h / 2 for face in chosen):
            chosen.append(Face(float(x), float(y), float(w), float(h), float(angle)))
        if len(chosen) >= limit:
            break
    return chosen


def build_mask(shape, faces: list[Face]):
    """A soft ellipse over each face: takes the chin, spares hair and forehead."""

    cv2 = require("cv2")
    numpy = require("numpy")
    mask = numpy.zeros(shape[:2], numpy.float32)
    for face in faces:
        offset_x = -numpy.sin(numpy.radians(face.angle)) * face.height * 0.06
        offset_y = numpy.cos(numpy.radians(face.angle)) * face.height * 0.06
        cv2.ellipse(
            mask,
            (int(face.x - offset_x), int(face.y + offset_y)),
            (int(face.width * 0.46), int(face.height * 0.58)),
            -face.angle,
            0,
            360,
            1.0,
            -1,
        )
    kernel = int(max(face.width for face in faces) * 0.18) | 1
    return cv2.GaussianBlur(mask, (kernel, kernel), 0)[..., None]


def patch_face(
    original: Path,
    edited: Path,
    destination: Path,
    *,
    faces: int = 1,
    write_mask: bool = False,
) -> list[Face]:
    """Paste only the edited face back onto the original frame."""

    cv2 = require("cv2")
    numpy = require("numpy")
    base = cv2.imread(str(original))
    edit = cv2.imread(str(edited))
    if base is None or edit is None:
        raise FileNotFoundError(f"Could not read {original} or {edited}")

    edit = cv2.resize(edit, (base.shape[1], base.shape[0]), interpolation=cv2.INTER_LANCZOS4)
    edit = restore_grain(match_colour(edit, base), base)
    found = detect_faces(base, faces) or detect_faces(edit.astype(numpy.uint8), faces)
    if not found:
        raise ValueError(f"No face found in {original}; the frame is left unchanged")

    mask = build_mask(base.shape, found)
    result = (edit * mask + base * (1 - mask)).astype(numpy.uint8)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destination), result)
    if write_mask:
        cv2.imwrite(
            str(destination.with_name(destination.stem + "-mask.png")),
            (mask[..., 0] * 255).astype(numpy.uint8),
        )
    return found


__all__ = ["Face", "build_mask", "detect_faces", "match_colour", "patch_face", "restore_grain"]
