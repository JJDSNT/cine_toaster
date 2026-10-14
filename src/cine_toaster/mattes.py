"""A join shaped by a picture, and a picture riding it (SPEC-0011).

The matte decides, pixel by pixel, how much of the incoming picture is seen:
black is the outgoing picture, white the incoming.

- A **still** matte is an order: a pixel changes when the join's progress
  passes its brightness, spread over ``softness`` so the edge is not a line
  (the gl-transitions `luma` rule).
- A **moving** matte is the change itself: played across the join, its frame
  at each moment is the mix. It should start black and end white; one that
  does not reach white is completed over the join's last tenth, and said.

Both pictures keep playing through the join. An **overlay** -- a picture with
alpha -- is composited over the joined picture afterwards, at its own rate.

The joins are drawn as graphs of SPEC-0012 (ADR 0022) by the same renderers
as every recipe -- GL when it can, else the NumPy reference; this module holds
the checks a version reports and the graphs. (Until CT-0071 it drew them with
FFmpeg filters of its own: a third implementation of luma.)
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from .errors import ValidationError

MOVING_SUFFIXES = (".mp4", ".mov", ".webm", ".mkv", ".avi", ".gif")
#: Pixel formats that carry transparency.
_ALPHA = ("rgba", "bgra", "argb", "abgr", "yuva", "gbrap", "ya8", "ya16", "rgba64", "bgra64")


def is_moving(path: Path) -> bool:
    return Path(path).suffix.lower() in MOVING_SUFFIXES


def _probe(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise ValidationError("ffprobe is needed for a matte or an overlay")
    completed = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=pix_fmt:format=duration", "-of", "json", str(path)],
                               capture_output=True, text=True, timeout=60)
    data = json.loads(completed.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]
    return {"pix_fmt": str(stream.get("pix_fmt") or ""),
            "duration": float((data.get("format") or {}).get("duration") or 0.0)}


def has_alpha(path: Path) -> bool:
    return _probe(path)["pix_fmt"].startswith(_ALPHA)


def _brightness(path: Path, last: bool) -> float:
    """The mean brightness, 0 to 255, of a clip's first or last frame."""

    ffmpeg = shutil.which("ffmpeg")
    command = [ffmpeg, "-loglevel", "error", *(["-sseof", "-0.5"] if last else []), "-i", str(path),
               "-vf", "scale=1:1:flags=area,format=gray", "-f", "rawvideo", "-"]
    data = subprocess.run(command, capture_output=True, timeout=120).stdout
    return float(data[-1]) if data else 0.0


def matte_notes(matte: Path, seconds: float, fps: float, label: str) -> list[str]:
    """What a version says about a moving matte: retimed to its join, not starting black, not ending white."""

    notes = []
    if not is_moving(matte):
        return notes
    length = _probe(matte)["duration"] or seconds
    if abs(length - seconds) > 1 / fps:
        notes.append(f"{label}: its matte runs {length:.2f} s and is retimed to the join's {seconds:.2f} s.")
    if _brightness(matte, last=False) > 8:
        notes.append(f"{label}: its matte does not start black, so the next shot shows from the first frame.")
    if _brightness(matte, last=True) < 247:
        notes.append(f"{label}: its matte does not end white; it is completed over the join's last tenth.")
    return notes


def recipe(moving: bool, softness: float = 0.0) -> dict[str, Any]:
    """A join through a matte as a SPEC-0012 graph (ADR 0022): the matte's luma, made a matte, revealing `to`.

    A still matte is an order (a threshold driven by the progress, spread over ``softness``); a moving one is
    the shape itself, completed to white over the join's last tenth so the join always ends on `to`. One
    implementation of luma for every renderer: this replaced an FFmpeg-only drawing (CT-0071).
    """

    nodes: dict[str, Any] = {
        "order": {"op": "signal.luma", "picture": "matte_clip"},
        "shape": {"op": "matte.from_signal", "signal": "order"},
    }
    if moving:
        nodes.update({
            "white": {"op": "generate.solid", "colour": [1.0, 1.0, 1.0, 1.0]},
            "late": {"op": "curve.map", "in": "progress", "how": "remap", "low": 0.9, "high": 1.0,
                     "out_low": 0.0, "out_high": 1.0},
            "ending": {"op": "matte.threshold", "matte": "white", "progress": "late", "softness": 0.0},
            "reveal": {"op": "matte.combine", "a": "shape", "b": "ending", "how": "union"},
        })
    else:
        nodes["reveal"] = {"op": "matte.threshold", "matte": "shape", "progress": "progress",
                           "softness": max(float(softness or 0.0), 0.002)}
    nodes["out"] = {"op": "merge.over", "front": "to", "back": "from", "matte": "reveal"}
    return {"ports": {"from": "picture", "to": "picture", "progress": "curve", "matte_clip": "picture"},
            "nodes": nodes, "output": "out"}


def overlay_recipe(blend: str = "normal") -> dict[str, Any]:
    """An overlay with alpha laid over a joined picture, as a graph: over, or a screen or add blend."""

    if blend in ("screen", "add"):
        laid = {"op": "merge.blend", "a": "joined", "b": "overlay", "mode": blend}
    else:
        laid = {"op": "merge.over", "front": "overlay", "back": "joined"}
    return {"ports": {"joined": "picture", "overlay": "picture"}, "nodes": {"out": laid}, "output": "out"}


def overlay_notes(overlay: Path, seconds: float, fps: float, label: str) -> tuple[list[str], bool]:
    """(notes, usable): an overlay without transparency is not laid; one shorter than its join ends early."""

    if not has_alpha(overlay):
        return [f"{label}: its overlay {overlay.name} has no transparency; it is not laid (it would hide the join)."], False
    notes = []
    if is_moving(overlay):
        length = _probe(overlay)["duration"]
        if length and length + 1 / fps < seconds:
            notes.append(f"{label}: its overlay runs {length:.2f} s, less than the join's {seconds:.2f} s; it ends early.")
    return notes, True
