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

These are the FFmpeg renderers; a shader that reads a texture gets its
pictures from `shader_render` instead.
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


def _cover(width: int, height: int) -> str:
    """Scaled to cover the frame and centred: black in a matte is a meaning, never a border."""

    return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1"


def join(ffmpeg: str, outgoing: Path, incoming: Path, outgoing_frames: int, frames: int, matte: Path,
         destination: Path, *, fps: float, width: int, height: int, softness: float = 0.0,
         run: Callable[..., Any], notes: list[str], label: str) -> Path:
    """The last ``frames`` of ``outgoing`` become the first ``frames`` of ``incoming`` through ``matte``."""

    seconds = frames / fps
    tail = outgoing_frames - frames
    cover = _cover(width, height)
    if is_moving(matte):
        length = _probe(matte)["duration"] or seconds
        if abs(length - seconds) > 1 / fps:
            notes.append(f"{label}: its matte runs {length:.2f} s and is retimed to the join's {seconds:.2f} s.")
        if _brightness(matte, last=False) > 8:
            notes.append(f"{label}: its matte does not start black, so the next shot shows from the first frame.")
        if _brightness(matte, last=True) < 247:
            notes.append(f"{label}: its matte does not end white; it is completed over the join's last tenth.")
        source = ["-i", str(matte)]
        shape = (f"[2:v]{cover},format=gray,setpts=(PTS-STARTPTS)*{seconds / length:.6f},fps={fps:g},"
                 f"trim=end_frame={frames},setpts=PTS-STARTPTS[shape];"
                 # Whatever the matte does, the join ends on the incoming picture.
                 f"color=black:s={width}x{height}:r={fps:g}:d={seconds:.4f},format=gray,"
                 f"geq=lum='255*clip((N+1-0.9*{frames})/(0.1*{frames}),0,1)'[ramp];"
                 f"[shape][ramp]blend=all_mode=lighten[m]")
    else:
        spread = max(float(softness or 0.0), 0.002)
        source = ["-loop", "1", "-framerate", f"{fps:g}", "-t", f"{seconds:.4f}", "-i", str(matte)]
        # Progress as the shader has it, never exactly 0 or 1: (n + 1) / (frames + 1).
        progress = f"((N+1)/{frames + 1})*(1+2*{spread})-{spread}"
        shape = (f"[2:v]{cover},format=gray,trim=end_frame={frames},"
                 f"geq=lum='255*clip(({progress}-lum(X,Y)/255)/(2*{spread})+0.5,0,1)'[m]")
    graph = (f"[0:v]trim=start_frame={tail}:end_frame={outgoing_frames},setpts=PTS-STARTPTS,{cover},format=yuv420p[a];"
             f"[1:v]trim=end_frame={frames},setpts=PTS-STARTPTS,{cover},format=yuv420p[b];"
             f"{shape};[b][m]alphamerge[shown];[a][shown]overlay=format=auto,format=yuv420p[v]")
    run([ffmpeg, "-y", "-loglevel", "error", "-i", str(outgoing), "-i", str(incoming), *source,
         "-filter_complex", graph, "-map", "[v]", "-frames:v", str(frames),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", f"{fps:g}",
         str(destination)], message=f"{label}: the join through its matte")
    return destination


def lay_overlay(ffmpeg: str, clip: Path, overlay: Path, destination: Path, *, frames: int, fps: float, width: int,
                height: int, blend: str = "normal", run: Callable[..., Any], notes: list[str], label: str) -> Path:
    """``overlay`` composited over the whole of ``clip``, at its own rate from the start."""

    if not has_alpha(overlay):
        notes.append(f"{label}: its overlay {overlay.name} has no transparency; it is not laid (it would hide "
                     "the join).")
        shutil.copyfile(clip, destination)
        return destination
    seconds = frames / fps
    if is_moving(overlay):
        length = _probe(overlay)["duration"]
        if length and length + 1 / fps < seconds:
            notes.append(f"{label}: its overlay runs {length:.2f} s, less than the join's {seconds:.2f} s; it ends early.")
        source = ["-i", str(overlay)]
    else:
        source = ["-loop", "1", "-framerate", f"{fps:g}", "-t", f"{seconds:.4f}", "-i", str(overlay)]
    cover = _cover(width, height)
    if blend in ("screen", "add"):
        mode = "screen" if blend == "screen" else "addition"
        # Flattened on black first: where the overlay is transparent it then changes nothing.
        graph = (f"[1:v]{cover},fps={fps:g},format=rgba[o];color=black:s={width}x{height}:r={fps:g}:d={seconds:.4f}[k];"
                 f"[k][o]overlay=eof_action=pass:format=auto,format=gbrp[flat];"
                 f"[0:v]format=gbrp[base];[base][flat]blend=all_mode={mode}:shortest=1,format=yuv420p[v]")
    else:
        graph = (f"[1:v]{cover},fps={fps:g},format=rgba[o];"
                 f"[0:v][o]overlay=eof_action=pass:format=auto,format=yuv420p[v]")
    run([ffmpeg, "-y", "-loglevel", "error", "-i", str(clip), *source, "-filter_complex", graph, "-map", "[v]",
         "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-r", f"{fps:g}", str(destination)], message=f"{label}: the overlay on its join")
    return destination
