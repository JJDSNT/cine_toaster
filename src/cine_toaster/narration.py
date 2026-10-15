"""The lines a production speaks itself, with an offline voice (CT-0018, CT-0065).

A line that names a file (`mix: {file: sound/vo-open.wav, at: 0.5}`) is laid
in the cut from that file, read beside the scene's breakdown, where a
version's snapshot of the scene finds it. `toast voice` makes the file:

- each line in its own voice (`voice: piper/<id>`), else the one asked for,
  else the default: two speakers must not sound like one;
- what was said is recorded beside the audio (`<file>.provenance.json`), so a
  line whose words or voice changed is spoken again rather than left saying
  what the breakdown no longer says;
- audio with no such record is kept: it may be a person's recording.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .takes import PROVENANCE_SUFFIX

OFFLINE_PREFIX = "piper/"


@dataclass(frozen=True, slots=True)
class Spoken:
    """What became of one line."""

    scene: str
    shot: str
    who: str
    file: str  # relative to the production
    status: str  # spoke | respoke | keep | refuse
    reason: str = ""
    voice: str = ""
    seconds: float = 0.0

    @property
    def made(self) -> bool:
        return self.status in ("spoke", "respoke")


def line_text(line: dict[str, Any]) -> str:
    return str(line.get("en") or line.get("text") or "")


def line_file(line: dict[str, Any]) -> str:
    mix = line.get("mix") if isinstance(line.get("mix"), dict) else {}
    return str(mix.get("file") or mix.get("arquivo") or "")


def spoken_record(audio: Path) -> dict[str, Any]:
    """What `toast voice` recorded when it made this audio, or {}."""

    try:
        data = json.loads(audio.with_name(audio.name + PROVENANCE_SUFFIX).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def stale(audio: Path, line: dict[str, Any]) -> str:
    """Why audio made here no longer matches its line, or ''."""

    record = spoken_record(audio)
    if "text" not in record:
        return ""
    if str(record["text"]) != line_text(line):
        return "the words changed"
    wanted = str(line.get("voice") or "")
    if wanted.startswith(OFFLINE_PREFIX) and record.get("model") and record["model"] != wanted[len(OFFLINE_PREFIX):]:
        return "the voice changed"
    return ""


def speak_lines(
    root: Path,
    production: dict[str, Any],
    speaker: Callable[[str], Any],
    *,
    scene_id: str | None = None,
    default_voice: str,
    force: bool = False,
) -> list[Spoken]:
    """Speak every line that names a file. ``speaker(voice)`` gives the narrator for a voice."""

    root = Path(root)
    results: list[Spoken] = []
    for scene in production["scenes"]:
        if scene_id and scene["id"] != scene_id:
            continue
        directory = root / Path(scene["file"]).parent
        for shot in scene["shots"]:
            for line in shot.get("lines") or []:
                name = line_file(line)
                if not name:
                    continue
                destination = directory / name
                relative = destination.relative_to(root).as_posix()
                who = str(line.get("who") or "")

                def result(status: str, reason: str = "", voice: str = "", seconds: float = 0.0) -> None:
                    results.append(Spoken(scene["id"], shot["id"], who, relative, status, reason, voice, seconds))

                wanted = str(line.get("voice") or "")
                if wanted and not wanted.startswith(OFFLINE_PREFIX):
                    result("refuse", f"its voice is {wanted}, not an offline voice ({OFFLINE_PREFIX}<id>)")
                    continue
                voice = wanted[len(OFFLINE_PREFIX):] if wanted else default_voice
                if destination.suffix.lower() != ".wav":
                    result("refuse", "offline narration writes WAV; declare a .wav file")
                    continue
                status, reason = "spoke", ""
                if destination.is_file() and not force:
                    reason = stale(destination, line)
                    if not reason:
                        made_here = "text" in spoken_record(destination)
                        result("keep", "exists; --force to remake" if made_here
                               else "exists, not recorded as spoken here; --force to remake")
                        continue
                    status = "respoke"
                elif (root / name).is_file() and not destination.is_file():
                    reason = f"{name} at the production root is not read by the cut and is left there"
                made = speaker(voice).speak(text=line_text(line), output=destination)
                destination.with_name(destination.name + PROVENANCE_SUFFIX).write_text(
                    json.dumps({"provider": "piper", "model": voice, "text": line_text(line), "who": who},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                result(status, reason, voice, float(getattr(made, "duration_seconds", 0.0) or 0.0))
    return results
