"""A graph drawn over a piece of a take, written as a clip with the take's sound (C6, CT-0077).

Effects and titles are both a graph with one port, `picture`, the shot as it is
cut. This draws such a graph over a clip from `start` (or over a still picture
when there is no clip, for previews and cards), by GL when it holds every op and
by the reference otherwise, and keeps the clip's sound: one way of laying a
treatment over a shot, for every catalog that has one.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

import numpy as np


def has_sound(path: Path) -> bool:
    completed = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return bool(completed.stdout.strip())


def over_picture(graph: dict[str, Any], duration: float, output: Path, *, background: Path | None = None,
                 still: np.ndarray | None = None, start: float = 0.0, width: int = 1280, height: int = 720,
                 fps: int = 24, root: Path | None = None, run: Callable[[list[str]], Any] | None = None) -> Path:
    """`graph` (port `picture`) drawn over `background` from `start`, or over `still`; `output` written."""

    from . import reference
    from .gl import renderer_for

    run = run or (lambda command: subprocess.run(command, check=True, capture_output=True))
    width, height = width // 2 * 2, height // 2 * 2
    frames = max(1, round(duration * fps))
    if background is not None:
        picture: Any = reference.read(Path(background), frames, (width, height), fps, start=start)
    else:
        picture = still if still is not None else np.zeros((height, width, 4), np.float32) + [0, 0, 0, 1]
    fast = renderer_for(graph)
    pictures, _identity, _cached = reference.render(graph, {"picture": picture}, frames=frames, size=(width, height),
                                                    fps=fps, root=root, renderer=fast)
    output.parent.mkdir(parents=True, exist_ok=True)
    silent = output.with_suffix(".picture.mp4")
    reference.write(pictures, silent, fps)
    if background is not None and has_sound(Path(background)):
        run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
             "-i", str(background), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-shortest",
             str(output)])
        silent.unlink(missing_ok=True)
    else:
        silent.replace(output)
    return output
