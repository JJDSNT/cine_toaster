"""Cutting to music: a track's beats kept as a record, and shot lengths given in beats (CT-0067).

`toast sound beats <project> <sound>` detects a track's tempo and beats and
writes them beside it, `sounds/<id>/beats.json`, with the checksum of the
file they were heard in. A scene whose `music` has beats may then give each
shot's length in beats instead of seconds:

    music: circuit-synthwave
    shots:
      - n: 1
        beats: 8                              # from the scene's start to beat 8
      - n: 2
        beats: 8
        transition: {id: cube, beats: 2, reason: ...}

Each join falls on a beat: a straight cut exactly, a transition with its
middle there. The lengths in seconds are worked out from the beats, so a
change of one shot does not move the joins after it. The music is read from
the scene's start: it must begin with the first shot, at 0.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .errors import ValidationError

BEATS_FILE = "beats.json"


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(item: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """A catalog sound's beats and why they cannot be used, or (None, '') when it has none."""

    path = Path(item["directory"]) / BEATS_FILE
    if not path.is_file():
        return None, ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, f"its {BEATS_FILE} cannot be read"
    audio = Path(item.get("file") or "")
    if data.get("sha256") and audio.is_file() and data["sha256"] != _checksum(audio):
        return None, "its beats were heard in another recording than the one there now"
    return data, ""


def detect(item: dict[str, Any], run=None) -> dict[str, Any]:
    """Hear a catalog sound's beats in the voice environment and keep them beside it."""

    from .voice import voice_python

    audio = Path(item.get("file") or "")
    if not audio.is_file():
        raise ValidationError(f"The sound {item['id']!r} has no recording to hear: beats need a file, not a generator")
    python = voice_python()
    if python is None:
        raise ValidationError("Beats are heard by librosa in the voice environment, which is not installed "
                              "(make install-voice)")
    run = run or (lambda command: subprocess.run(command, check=True, capture_output=True, text=True, timeout=900))
    with tempfile.TemporaryDirectory(prefix="beats-") as scratch:
        spec, out = Path(scratch) / "spec.json", Path(scratch) / "beats.json"
        spec.write_text(json.dumps({"audio": str(audio), "out": str(out)}), encoding="utf-8")
        try:
            run([str(python), str(Path(__file__).with_name("beats_worker.py")), str(spec)])
        except subprocess.CalledProcessError as error:
            raise ValidationError(f"Hearing the beats of {item['id']!r} failed: {(error.stderr or '')[-300:]}") from error
        data = json.loads(out.read_text(encoding="utf-8"))
    data = {**data, "sound": item["id"], "file": audio.name, "sha256": _checksum(audio)}
    (Path(item["directory"]) / BEATS_FILE).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return data


def lay_out(shots: list[dict[str, Any]], music: list[dict[str, Any]], catalog: dict[str, dict[str, Any]],
            scene_id: str) -> list[dict[str, Any]]:
    """Give shots that count beats their lengths in seconds, and transitions in beats theirs: problems found."""

    counted = [shot for shot in shots if shot.get("beats") is not None]
    if not counted:
        return []
    problems: list[dict[str, Any]] = []

    def problem(code: str, severity: str, message: str, ids: tuple[str, ...] = ()) -> None:
        problems.append({"code": code, "severity": severity, "scene_id": scene_id, "shots": ids, "message": message})

    if len(counted) != len(shots):
        loose = tuple(shot["id"] for shot in shots if shot.get("beats") is None)
        problem("beats_mixed", "error", f"Some shots count beats and {', '.join(loose)} do not; a scene cut to the "
                                        "music counts every shot in beats.", loose)
        return problems
    if not music:
        problem("beats_without_music", "error", "Its shots count beats, but the scene has no music to count them in.")
        return problems
    track = music[0]
    if (track.get("from") and track["from"] != shots[0]["id"]) or float(track.get("at") or 0):
        problem("beats_music_not_at_start", "error",
                f"Its shots count beats of {track['id']}, which does not start with the scene; beats are read from "
                "the scene's start.")
        return problems
    beats, why = read(catalog.get(track["id"]) or {"directory": "", "file": ""})
    if beats is None:
        problem("beats_missing", "warning",
                f"Its shots count beats of {track['id']}, which has {why or 'no beats yet'}; their lengths are the "
                f"seconds they also give, if any. toast sound beats {track['id']} hears them.")
        return problems
    times = beats.get("beats") or []
    interval = (times[-1] - times[0]) / (len(times) - 1) if len(times) > 1 else 0.5
    counts, boundary = [], 0.0
    for shot in shots:
        try:
            boundary += float(shot["beats"])
        except (TypeError, ValueError):
            boundary = -1
        if boundary <= 0 or boundary != int(boundary):
            problem("beats_invalid", "error", f"{shot['id']} counts {shot['beats']!r} beats; a whole number, more "
                                              "than nothing, is needed.", (shot["id"],))
            return problems
        counts.append(int(boundary))
    if counts[-1] >= len(times):
        problem("beats_past_end", "error", f"The shots count {counts[-1]} beats; {track['id']} has {len(times)}.",
                (shots[-1]["id"],))
        return problems
    lengths = []
    for shot in shots:
        transition = shot.get("transition") or {}
        if transition.get("beats") is not None:
            transition["duration_ms"] = round(float(transition["beats"]) * interval * 1000)
        lengths.append(float(transition.get("duration_ms") or 0) / 1000 if shot is not shots[0] and transition.get("id")
                       else 0.0)
    for index, shot in enumerate(shots):
        start = 0.0 if index == 0 else times[counts[index - 1]] - lengths[index] / 2
        end = times[counts[index]] + (lengths[index + 1] / 2 if index + 1 < len(shots) else 0.0)
        shot["duration_seconds"] = round(end - start, 3)
    for index in range(1, len(shots)):
        if lengths[index] > min(shots[index - 1]["duration_seconds"], shots[index]["duration_seconds"]) / 2:
            problem("join_off_beat", "warning",
                    f"The transition into {shots[index]['id']} is longer than half a shot it joins; the cut shortens "
                    "it, and every join after it leaves the beat.", (shots[index - 1]["id"], shots[index]["id"]))
    return problems
