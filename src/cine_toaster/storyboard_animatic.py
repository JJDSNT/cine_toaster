"""A sequence's storyboard in time: each shot's latest drawing, held for its breakdown duration.

The director reviews a sequence, and a storyboard is judged in time as much as
in frames (Demo 01, 2026-10-18). This needs no blockout, no model and no paid
work: the drawings in the canonical sequence order, each with a gentle push-in
and a small scene/shot label, cut together with FFmpeg. Every run is a new
numbered file beside the earlier ones -- an animatic is never overwritten.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .errors import PersistenceError, ValidationError
from .project import load_production
from .storyboard import load_storyboard

WIDTH, HEIGHT, FPS = 1280, 720, 24
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
#: A shot with no declared duration is held this long, and says so in the report.
DEFAULT_SECONDS = 3.0


def plan(root: Path, sequence: str) -> list[dict[str, Any]]:
    """Each shot of the sequence, in order, with its latest drawing and its duration."""

    from .production_context import work_structure

    root = Path(root).expanduser().resolve()
    production = load_production(root)
    scope = next((item for item in work_structure(production, sequence=sequence)["sequences"]
                  if item["id"] == sequence), None)
    if scope is None:
        raise ValidationError(f"No canonical sequence {sequence!r}")
    latest: dict[tuple[str, str], dict] = {}
    for board in load_storyboard(root, production=production)["candidates"]:
        key = (board["scene"], board["shot"])
        if key not in latest or (board.get("version") or 0) >= (latest[key].get("version") or 0):
            latest[key] = board
    scenes = {item["id"]: item for item in production["scenes"]}
    shots = []
    for scene_id in scope["scene_ids"]:
        for shot in scenes[scene_id]["shots"]:
            board = latest.get((scene_id, shot["id"]))
            seconds = float(shot.get("duration_seconds") or 0)
            shots.append({"scene": scene_id, "scene_title": scenes[scene_id].get("title", ""), "shot": shot["id"],
                          "seconds": seconds or DEFAULT_SECONDS, "declared": bool(seconds),
                          "board": board["id"] if board else None, "version": board.get("version") if board else None,
                          "image": str(root / board["image"]["path"]) if board else None})
    return shots


def _clip(shot: dict[str, Any], index: int, folder: Path, ffmpeg: str) -> Path:
    out = folder / f"{index:03d}.mp4"
    frames = max(int(round(shot["seconds"] * FPS)), 1)
    label = f"{shot['scene']} {shot['shot']}" + (f"  v{shot['version']}" if shot.get("version") else "")
    fit = (f"scale={WIDTH * 2}:{HEIGHT * 2}:force_original_aspect_ratio=decrease,"
           f"pad={WIDTH * 2}:{HEIGHT * 2}:(ow-iw)/2:(oh-ih)/2:color=0x101010,setsar=1")
    push = (f"zoompan=z='1+0.04*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}")
    text = ""
    if FONT.is_file():
        text = (f",drawtext=fontfile={FONT}:text='{label}':x=24:y=h-44:fontsize=22:"
                "fontcolor=white@0.85:box=1:boxcolor=black@0.45:boxborderw=8")
    if shot["image"]:
        command = [ffmpeg, "-y", "-loglevel", "error", "-loop", "1", "-i", shot["image"],
                   "-vf", fit + "," + push + text, "-frames:v", str(frames), "-pix_fmt", "yuv420p",
                   "-c:v", "libx264", "-preset", "veryfast", "-r", str(FPS), str(out)]
    else:  # a missing drawing is shown as missing, never skipped
        command = [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                   f"color=c=0x202020:s={WIDTH}x{HEIGHT}:r={FPS}", "-frames:v", str(frames),
                   "-vf", text.lstrip(",").replace(label, label + "  -- no drawing yet") if text else "null",
                   "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", str(out)]
    subprocess.run(command, check=True, capture_output=True)
    return out


def render(root: Path, sequence: str) -> dict[str, Any]:
    """Render the sequence's storyboard animatic as a new numbered file under renders/animatics/."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise PersistenceError("FFmpeg is needed for the storyboard animatic (toast doctor)")
    root = Path(root).expanduser().resolve()
    shots = plan(root, sequence)
    folder = root / "renders" / "animatics"
    folder.mkdir(parents=True, exist_ok=True)
    number = 1 + max((int(path.stem.rsplit("-v", 1)[1]) for path in folder.glob(f"{sequence}-storyboard-v*.mp4")
                      if path.stem.rsplit("-v", 1)[1].isdigit()), default=0)
    target = folder / f"{sequence}-storyboard-v{number}.mp4"
    with tempfile.TemporaryDirectory() as work:
        work_dir = Path(work)
        clips = [_clip(shot, index, work_dir, ffmpeg) for index, shot in enumerate(shots)]
        listing = work_dir / "list.txt"
        listing.write_text("".join(f"file '{clip}'\n" for clip in clips), encoding="utf-8")
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", str(target)], check=True, capture_output=True)
    return {"sequence": sequence, "path": str(target.relative_to(root)), "version": number,
            "seconds": round(sum(shot["seconds"] for shot in shots), 2), "shots": len(shots),
            "missing": [f"{shot['scene']} {shot['shot']}" for shot in shots if not shot["image"]],
            "undeclared_durations": [f"{shot['scene']} {shot['shot']}" for shot in shots if not shot["declared"]]}
