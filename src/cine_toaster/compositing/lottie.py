"""Lottie animations read as a source: the adapter to ThorVG (C6b stage D, CT-0078).

A Lottie file (Bodymovin's JSON, or a dotLottie archive) is ready motion
graphics -- lettering, icons, lower thirds -- with its own transparency. Here it
is one more kind of file a source reads: drawn frame by frame by ThorVG into the
same clip a picture or a video becomes, so a layer, an element or a title's fill
takes it as it takes any file, with nothing else to learn.

ThorVG (MIT) is reached through `thorvg-python` (LGPL 2.1, loaded as a library,
not changed), the `motion` extra. Chosen over rlottie in the spike recorded in
`CT-0078`: faster on the heavy samples and it draws text layers, which rlottie
leaves out. The rest of Cine Toaster sees `is_lottie`, `available` and `read`.
"""

from __future__ import annotations

import json
import tempfile
import threading
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from ..errors import ValidationError

#: What to install when ThorVG is missing; the doctor says the same.
REMEDY = "pip install thorvg-python   (or: pip install -e '.[motion]')"

_engine: Any = None
_lock = threading.Lock()


def available() -> bool:
    try:
        import thorvg_python  # noqa: F401
    except ImportError:
        return False
    return True


def is_lottie(path: Path) -> bool:
    """A dotLottie archive, or a JSON file that is a Lottie animation: its frame rate, its out point and its
    layers at the top (they may follow its assets, so the file is read whole, once)."""

    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".lottie":
        return True
    if suffix != ".json" or not path.is_file():
        return False
    return _is_animation(str(path), path.stat().st_mtime_ns)


@lru_cache(maxsize=64)
def _is_animation(path: str, _changed: int) -> bool:
    try:
        top = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(top, dict) and all(key in top for key in ("fr", "op", "layers"))


def _animation_file(path: Path, work: Path) -> Path:
    """The animation's JSON: the file itself, or the first animation inside a dotLottie archive."""

    if path.suffix.lower() != ".lottie":
        return path
    with zipfile.ZipFile(path) as archive:
        names = sorted(name for name in archive.namelist() if name.startswith("animations/") and name.endswith(".json"))
        if not names:
            raise ValidationError(f"{path.name} holds no animation")
        target = work / "animation.json"
        target.write_bytes(archive.read(names[0]))
    return target


def _thorvg():
    global _engine
    import thorvg_python as tvg

    if _engine is None:
        _engine = tvg.Engine(threads=4)
    return tvg, _engine


def read(path: Path, frames: int, size: tuple[int, int], fps: float, *, start: float = 0.0,
         stretch_to: float | None = None, hold: bool = True) -> np.ndarray:
    """`frames` frames of the animation from `start` seconds, fitted to `size` as any picture is (`conform_box`),
    as straight-alpha display-encoded 16-bit RGBA in a memory-mapped array (the clip a PNG becomes).

    The animation plays at its own frame rate, whatever the film's; after its end it holds its last frame, or
    is gone (`hold`). `stretch_to` fits its whole run to that many seconds."""

    from .reference import conform_box

    if not available():
        raise ValidationError(f"Drawing the Lottie animation {Path(path).name} needs ThorVG: {REMEDY}")
    path = Path(path)
    with tempfile.TemporaryDirectory(prefix="lottie-") as folder:
        source = _animation_file(path, Path(folder))
        try:
            meta = json.loads(source.read_text(encoding="utf-8"))
            rate, first, last = float(meta["fr"]), float(meta.get("ip", 0)), float(meta["op"])
            source_size = (int(meta["w"]), int(meta["h"]))
        except (ValueError, KeyError, TypeError) as error:
            raise ValidationError(f"{path.name} is not a Lottie animation: {error}") from error
        width, height = size
        fitted_width, fitted_height, x, y = conform_box(*source_size, width, height)
        length = max(1.0, last - first)  # in the animation's frames
        speed = length / rate / stretch_to if stretch_to else 1.0
        handle = tempfile.NamedTemporaryFile(prefix="clip-", suffix=".raw", delete=False)
        stored = np.lib.format.open_memmap(handle.name, mode="w+", dtype="<u2", shape=(frames, height, width, 4))
        Path(handle.name).unlink()  # the mapping keeps it
        handle.close()
        with _lock:  # one ThorVG engine, drawn from one thread at a time
            tvg, engine = _thorvg()
            canvas = tvg.SwCanvas(engine)
            canvas.set_target(fitted_width, fitted_height, cs=tvg.Colorspace.ABGR8888S)  # straight alpha
            animation = tvg.LottieAnimation(engine)
            picture = animation.get_picture()
            if picture.load(str(source)) != tvg.Result.SUCCESS:
                canvas.destroy()
                raise ValidationError(f"ThorVG cannot read {path.name}")
            picture.set_size(fitted_width, fitted_height)
            canvas.add(picture)
            try:
                for index in range(frames):
                    at = (start + index / fps) * speed * rate  # in the animation's frames, from its first
                    if at > length - 1 and not hold:
                        continue  # gone: the frame stays transparent
                    animation.set_frame(float(min(max(at, 0.0), length - 1)))
                    canvas.update()
                    canvas.draw(True)
                    canvas.sync()
                    drawn = np.frombuffer(bytes(canvas.buffer_arr), np.uint8).reshape(fitted_height, fitted_width, 4)
                    stored[index, y:y + fitted_height, x:x + fitted_width] = drawn.astype(np.uint16) * 257
            finally:
                canvas.destroy()
    return stored
