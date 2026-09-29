"""A take's speech, converted to the cast member's own voice (CT-0040).

A video model gives a character a slightly different voice in every
generation. SINGULAR measured Kael against his reference recording at 0.45 to
0.78 across clips, and the LTX identity LoRA did not narrow that. Converting
the take's speech to the voice on the cast sheet does: on 12 of Kael's takes,
similarity rose from 0.67 to 0.82 on average, with the same words
recognised, and the timing within 10 ms, so the mouths still match
(2026-09-29).

The conversion keeps the room. The take's sound is separated into voice and
everything else, only the voice is converted, and the two are mixed back at
the voice's original level. The result is a new take of the shot, beside the
others, with its lineage. Nothing is replaced.

The engines (Demucs to separate, Chatterbox to convert, Resemblyzer to
measure; all MIT or Apache) pin their own numpy and torch, so they run in a
separate interpreter, `.venv-voice` (`make install-voice`) or
`CINE_TOASTER_VOICE_PYTHON`. The worker runs as a process: a job can report
it and cancel it like any encoder.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cast import _digest, cast_key
from .errors import ValidationError

WORKER = Path(__file__).with_name("voice_worker.py")
REPOSITORY_VOICE_PYTHON = Path(__file__).resolve().parents[2] / ".venv-voice" / "bin" / "python"
ENGINE = "chatterbox-vc"
SEPARATION = "htdemucs"


def voice_python() -> Path | None:
    """The interpreter that holds the voice engines, when there is one."""

    configured = os.environ.get("CINE_TOASTER_VOICE_PYTHON", "").strip()
    candidate = Path(configured).expanduser() if configured else REPOSITORY_VOICE_PYTHON
    return candidate if candidate.is_file() and os.access(candidate, os.X_OK) else None


def voice_unavailable_reason() -> str:
    """Why conversion cannot run here, or an empty string when it can."""

    python = voice_python()
    if python is None:
        return "no voice environment (make install-voice, or set CINE_TOASTER_VOICE_PYTHON)"
    probe = subprocess.run([str(python), "-c", "import chatterbox, demucs"], capture_output=True, text=True, timeout=120)
    if probe.returncode:
        return f"{python} lacks chatterbox or demucs (make install-voice)"
    return ""


@dataclass(slots=True)
class VoicePlan:
    scene: str
    shot: str
    take: str
    media: Path
    speaker: str
    member: str
    reference: Path

    def public_dict(self, root: Path) -> dict[str, Any]:
        return {"scene": self.scene, "shot": self.shot, "take": self.take,
                "media": self.media.relative_to(root).as_posix(), "speaker": self.speaker, "member": self.member,
                "reference": self.reference.relative_to(root).as_posix(), "reference_digest": _digest(self.reference)}


def plan_conversion(root: Path, production: dict[str, Any], scene_id: str, shot_id: str, take_id: str = "") -> VoicePlan:
    """Which take, whose voice, and the recording it is converted to."""

    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        raise ValidationError(f"No scene {scene_id!r}")
    shot = next((item for item in scene["shots"] if item["id"] == shot_id), None)
    if shot is None:
        raise ValidationError(f"{scene_id} has no shot {shot_id!r}")
    takes = [take for take in shot.get("takes") or [] if str(take.get("media", "")).endswith((".mp4", ".mov", ".webm"))]
    take = (next((item for item in takes if item["id"] == take_id), None) if take_id
            else next((item for item in takes if item.get("selected")), None) or next(iter(takes), None))
    if take is None:
        raise ValidationError(f"{shot_id} has no video take {take_id!r}" if take_id else f"{shot_id} has no video take")
    speakers = sorted({line.get("who", "") for line in shot.get("lines") or [] if line.get("in_take", True)})
    if not speakers:
        raise ValidationError(f"{shot_id} declares no line spoken in the take; there is no voice to convert")
    if len(speakers) > 1:
        raise ValidationError(f"{shot_id} has {len(speakers)} speakers ({', '.join(speakers)}); "
                              f"converting one voice would change the others too")
    cast = production.get("cast") or {}
    member = next((m for m in cast.values()
                   if cast_key(speakers[0]) in {cast_key(n) for n in [m["id"], m["label"], *m.get("names", [])]}), None)
    if member is None:
        raise ValidationError(f"{speakers[0]} has no cast sheet (cast/<id>/character.yaml) to take a voice from")
    recordings = ((member.get("voice") or {}).get("references") or [])
    reference = next((root / item for item in recordings if (root / item).is_file()), None)
    if reference is None:
        raise ValidationError(f"{member['label']}'s cast sheet has no voice recording "
                              f"(voice: references: [...]); a few clean seconds of the voice are needed")
    return VoicePlan(scene_id, shot_id, take["id"], root / take["media"], speakers[0], member["id"], reference)


def mux_command(take: Path, audio: Path, output: Path) -> list[str]:
    """The take's picture, untouched, with the new sound."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValidationError("FFmpeg is needed to put the converted voice under the picture")
    return [ffmpeg, "-y", "-loglevel", "error", "-i", str(take), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(output)]
