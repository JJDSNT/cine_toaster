"""A scene's cut, assembled from the takes chosen for its shots.

Every assembly is a **version**: rendered to its own file, never overwritten,
and registered with the takes it was built from (`record_assembly`), so a
version can be watched, judged, compared and restored.

This first assembly is deliberately plain, and says so:

- each shot contributes its selected take, or the production's current one
  (`c02.mp4`);
- the take is cut to the shot's `trim` (`{in, out}` or `{head, tail}`, in
  seconds) or, without one, to the shot's duration from the start of the take;
- shots are joined with straight cuts. Transitions and split edits (J/L) are
  listed as not rendered yet, not approximated;
- picture is normalised to the first take's size and frame rate, and sound to
  48 kHz stereo. A take without sound gets silence of the same length.

A production's own montage tools can register their renders as versions too;
this module is not the only way a version is made.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ValidationError

FPS = 24


@dataclass(slots=True)
class Segment:
    shot: str
    take: str
    media: str
    start: float
    end: float
    join: str = "hard"


@dataclass(slots=True)
class Plan:
    scene: str
    segments: list[Segment] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def takes(self) -> dict[str, str]:
        return {segment.shot: segment.take for segment in self.segments}

    @property
    def duration(self) -> float:
        return round(sum(segment.end - segment.start for segment in self.segments), 3)


def probe(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise ValidationError("ffprobe is needed to assemble a cut (it ships with FFmpeg)")
    completed = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    data = json.loads(completed.stdout or "{}")
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    rate = video.get("r_frame_rate") or f"{FPS}/1"
    numerator, _, denominator = rate.partition("/")
    return {
        "duration": float((data.get("format") or {}).get("duration") or 0.0),
        "audio": any(s.get("codec_type") == "audio" for s in streams),
        "width": int(video.get("width") or 1280),
        "height": int(video.get("height") or 720),
        "fps": round(float(numerator) / float(denominator or 1), 3) if numerator else FPS,
    }


def _trim(raw: Any, length: float, duration: float) -> tuple[float, float, str]:
    """Where a take is cut, and a note when the declared cut does not fit."""

    trim = raw if isinstance(raw, dict) else {}
    start = float(trim.get("in", trim.get("head", 0.0)) or 0.0)
    if "out" in trim:
        end = float(trim["out"])
    elif "tail" in trim:
        end = length - float(trim["tail"])
    elif duration:
        end = start + duration
    else:
        end = length
    note = ""
    if end > length + 0.01:
        note = f"runs {end - length:.2f} s past the end of its take; cut at the take's end"
        end = length
    if end - start < 1 / FPS:
        raise ValidationError(f"The cut leaves nothing of the take ({start:.2f}–{end:.2f} s of {length:.2f} s)")
    return round(start, 3), round(end, 3), note


def plan_scene(root: Path, scene: dict[str, Any]) -> Plan:
    """Which take of each shot, cut where, joined how."""

    plan = Plan(scene=scene["id"])
    cuts = {cut["to"]: cut for cut in scene.get("cuts") or []}
    for shot in scene["shots"]:
        if shot.get("out_of_cut"):
            continue
        takes = [take for take in shot.get("takes") or [] if take.get("media")]
        chosen = next((take for take in takes if take.get("selected")), None)
        if chosen is None:
            chosen = next((take for take in takes if take["id"] == "CUT"), None)
        if chosen is None:
            if shot.get("source") == "composed":
                plan.notes.append(f"{shot['id']} is composed (a card); its card is not part of a take cut yet.")
            else:
                plan.notes.append(f"{shot['id']} has no take to use; it is left out of this version.")
            continue
        path = root / chosen["media"]
        info = probe(path)
        start, end, note = _trim(shot.get("trim"), info["duration"], float(shot.get("duration_seconds") or 0))
        if note:
            plan.notes.append(f"{shot['id']} {note}.")
        cut = cuts.get(shot["id"]) or {}
        join = cut.get("type") or "hard"
        if plan.segments and join in ("j", "l"):
            plan.notes.append(f"{shot['id']}: the {join.upper()}-cut is rendered as a straight cut in this version.")
        transition = (cut.get("transition") or {}).get("id")
        if plan.segments and transition:
            plan.notes.append(f"{shot['id']}: the transition {transition!r} is not rendered in this version.")
        plan.segments.append(Segment(shot["id"], chosen["id"], chosen["media"], start, end, join))
    if not plan.segments:
        raise ValidationError(f"{scene['id']} has no shot with a take to assemble")
    return plan


def render(root: Path, plan: Plan, output: Path, work: Path, run_process) -> None:
    """Cut each take, normalise it, and join the pieces without re-encoding twice.

    ``run_process(command, expected_seconds=..., message=..., span=...)`` is
    the job's process runner, so progress and cancellation work per piece.
    """

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValidationError("FFmpeg is needed to assemble a cut")
    work.mkdir(parents=True, exist_ok=True)
    first = probe(root / plan.segments[0].media)
    size = f"{first['width'] // 2 * 2}:{first['height'] // 2 * 2}"
    fps = first["fps"] or FPS
    pieces = []
    total = len(plan.segments)
    for index, segment in enumerate(plan.segments):
        source = root / segment.media
        has_audio = probe(source)["audio"]
        length = segment.end - segment.start
        piece = work / f"piece-{index:03d}.mp4"
        command = [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{segment.start:.3f}", "-t", f"{length:.3f}", "-i", str(source)]
        if not has_audio:
            command += ["-f", "lavfi", "-t", f"{length:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        command += [
            "-vf", f"scale={size}:force_original_aspect_ratio=decrease,pad={size}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p",
            "-map", "0:v:0", "-map", "0:a:0" if has_audio else "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", str(piece),
        ]
        run_process(command, expected_seconds=length, message=f"Cutting {segment.shot}",
                    span=(0.9 * index / total, 0.9 * (index + 1) / total))
        pieces.append(piece)
    listing = work / "pieces.txt"
    listing.write_text("".join(f"file '{piece.name}'\n" for piece in pieces), encoding="utf-8")
    run_process([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                 "-c", "copy", "-movflags", "+faststart", str(output)],
                message="Joining the shots", span=(0.9, 1.0))
