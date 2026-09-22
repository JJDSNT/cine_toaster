from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import require


# A video model asked to defocus reinvents the face and the set: the subject is
# no longer the same person once the frame goes soft. So the clip is generated
# sharp and the focus is applied afterwards, in the edit, where nothing can be
# reinvented.
#
# Every curve here is an argument. A drifting focus is a directorial choice, and
# its timing belongs to the scene that needs it, not to this module.


@dataclass(frozen=True, slots=True)
class Curve:
    """A value over time, as (second, value) points, linearly interpolated."""

    points: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("A curve needs at least two points")
        seconds = [second for second, _value in self.points]
        if seconds != sorted(seconds):
            raise ValueError("Curve points must be in time order")

    def at(self, second: float) -> float:
        points = self.points
        if second <= points[0][0]:
            return points[0][1]
        if second >= points[-1][0]:
            return points[-1][1]
        for (first_second, first_value), (next_second, next_value) in zip(points, points[1:]):
            if second <= next_second:
                span = next_second - first_second
                if span <= 0:
                    return next_value
                blend = (second - first_second) / span
                return first_value + (next_value - first_value) * blend
        return points[-1][1]


def cover_crop(image, width: int, height: int):
    """Scale to cover the frame, then take the centre."""

    cv2 = require("cv2")
    source_height, source_width = image.shape[:2]
    scale = max(width / source_width, height / source_height)
    resized = cv2.resize(
        image,
        (round(source_width * scale), round(source_height * scale)),
        interpolation=cv2.INTER_LANCZOS4,
    )
    top = (resized.shape[0] - height) // 2
    left = (resized.shape[1] - width) // 2
    return resized[top : top + height, left : left + width]


def apply_focus(
    clip: Path,
    destination: Path,
    *,
    blur: Curve,
    flash: Curve | None = None,
    overlay: Path | None = None,
    overlay_alpha: Curve | None = None,
    blur_floor: float = 0.3,
) -> int:
    """Re-focus a finished clip over time, optionally fading another image over it.

    `blur` is the Gaussian sigma per second. `flash` adds brightness. `overlay`
    with `overlay_alpha` lets one face give way to another inside the soft
    frame -- something a model will not do reliably, and an edit will do exactly.

    Returns the number of frames written. Audio is taken from the source clip
    untouched.
    """

    cv2 = require("cv2")
    numpy = require("numpy")
    if overlay is not None and overlay_alpha is None:
        raise ValueError("An overlay needs an overlay_alpha curve")

    capture = cv2.VideoCapture(str(clip))
    if not capture.isOpened():
        raise FileNotFoundError(f"Could not open {clip}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 24
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    over = None
    if overlay is not None:
        loaded = cv2.imread(str(overlay))
        if loaded is None:
            raise FileNotFoundError(f"Could not read {overlay}")
        over = cover_crop(loaded, width, height).astype(numpy.float32)

    with tempfile.TemporaryDirectory() as workspace:
        silent = Path(workspace) / "silent.mp4"
        writer = cv2.VideoWriter(
            str(silent), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )
        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            second = index / fps
            working = frame.astype(numpy.float32)
            if over is not None and overlay_alpha is not None:
                alpha = overlay_alpha.at(second)
                working = working * (1 - alpha) + over * alpha
            sigma = blur.at(second)
            if sigma > blur_floor:
                working = cv2.GaussianBlur(working, (0, 0), sigma)
            if flash is not None:
                working = working + 255 * flash.at(second)
            writer.write(numpy.clip(working, 0, 255).astype(numpy.uint8))
            index += 1
        writer.release()
        capture.release()

        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-i", str(silent), "-i", str(clip),
                "-map", "0:v", "-map", "1:a?",
                "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-shortest",
                str(destination),
            ],
            check=True,
        )
    return index


__all__ = ["Curve", "apply_focus", "cover_crop"]
