"""Tracks as production records (C7 step 5, CT-0080): measured once on their media, kept, reviewed, reused.

A track belongs to the **media** it was measured on, not to a shot: a window
followed through a take is the same data whichever shot is cut from that take,
however it is trimmed, offset, ramped or reversed (the graph reads it by its
clock at the media instant a source shows -- `compositing/clock.py`). So it is
kept in the production, under `tracks/<id>/`:

    track.yaml               who it is: id, kind, the media (its path and content hash), the stretch measured,
                             the region, the measurement in use, its revision
    measurements/0001.json   each automatic measurement, as the tracker gave it -- never edited
    corrections.json         a person's corrections, apart: each the entry it replaces, by whom, when, why,
                             and whether it is still in force -- reverting keeps it, and never touches the
                             measurement

The track a graph reads is the measurement in use with the corrections in
force laid over it. Every measurement says what made it (tracker, version,
region, the media's hash); a track whose media or measuring has changed since
is **stale**, and is refused with the reason and the command that remeasures
it -- never used as if it still described its media. Corrections made on an
earlier measurement are kept and reported, not applied to a new one.

Mutations are commands, as every other change to a production: an actor, an
optional rationale, an event, a revision.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

from . import timebase
from .errors import ValidationError
from .events import Event, append_event
from .state import Actor, scene_lock

TRACKS_DIRECTORY = "tracks"
KINDS = ("point", "plane")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def directory(root: Path, track_id: str) -> Path:
    if not _ID.match(track_id or ""):
        raise ValidationError(f"A track's id is lowercase letters, digits and dashes, not {track_id!r}")
    return Path(root) / TRACKS_DIRECTORY / track_id


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.part")
    partial.write_text(text, encoding="utf-8")
    partial.replace(path)


def _media_hash(root: Path, media: str) -> str:
    from .compositing.identity import file_hash

    path = Path(root) / media
    if not path.is_file():
        raise ValidationError(f"The track's media {media} is not there")
    return file_hash(path)


def _project_id(root: Path) -> str:
    from .project import load_production

    return str(load_production(root)["id"])


# --- commands ---------------------------------------------------------------------------------------------------

def measure_track(root: Path, *, track_id: str, media: str, kind: str, region: list[float], actor: Actor,
                  start: float | None = None, end: float | None = None, rationale: str | None = None) -> dict[str, Any]:
    """Measure (or measure again) a track on its media, at the media's own size and rate, from `start` to `end`
    (seconds of the media; its whole length by default). A new measurement is added and put in use; earlier
    ones and every correction stay."""

    from .assembly import probe
    from .compositing import reference
    from .compositing.tracking import TRACKER, TRACKER_VERSION, measure

    root = Path(root).expanduser().resolve()
    if kind not in KINDS:
        raise ValidationError(f"A track is a point or a plane, not {kind!r}")
    if not (isinstance(region, (list, tuple)) and len(region) == 4 and all(isinstance(v, (int, float)) for v in region)
            and 0 <= region[0] < region[2] <= 1 and 0 <= region[1] < region[3] <= 1):
        raise ValidationError("A track's region is [x0, y0, x1, y1], fractions of the picture, x0 < x1, y0 < y1")
    path = root / media
    info = probe(path)
    rate = timebase.rate(info["fps"])
    first = timebase.frame_at(start or 0.0, rate)
    last = timebase.frame_at(end, rate) if end is not None else timebase.frame_at(info["duration"], rate)
    if last <= first:
        raise ValidationError("A track measures at least one frame: its end comes after its start")
    count = last - first
    origin = timebase.seconds_of(first, rate)
    clip = reference.read(path, count, (info["width"], info["height"]), float(rate), start=float(origin))
    measured = measure(lambda index: clip[index], kind, list(region), reference.LINEAR, frames=count)
    folder = directory(root, track_id)
    folder.mkdir(parents=True, exist_ok=True)
    with scene_lock(folder):
        record = _read_yaml(folder / "track.yaml") if (folder / "track.yaml").is_file() else {}
        number = int(record.get("measurement", 0)) + 1
        media_hash = _media_hash(root, media)
        measurement = {
            "kind": kind, "clock": {"rate": timebase.ffmpeg_rate(rate), "origin": timebase.to_record(origin)},
            "frames": measured["frames"],
            "measured": {**measured["measured"], "tracker": TRACKER, "version": TRACKER_VERSION,
                         "region": list(region), "media": media, "media_hash": media_hash,
                         "start": float(origin), "frames": count, "at": _now(), "by": actor.public_dict()},
        }
        _write(folder / "measurements" / f"{number:04d}.json", json.dumps(measurement))
        record = {"schema_version": 1, "id": track_id, "kind": kind, "media": media, "media_hash": media_hash,
                  "region": list(region), "start": float(origin), "frames": count, "measurement": number,
                  "revision": int(record.get("revision", 0)) + 1, "updated_at": _now()}
        _write(folder / "track.yaml", yaml.safe_dump(record, sort_keys=False))
        command_id = "cmd_" + uuid.uuid4().hex[:16]
        event = append_event(root, Event.create("track.measured", _project_id(root), track_id=track_id,
                                                measurement=number, revision=record["revision"],
                                                actor=actor.public_dict(), rationale=rationale or "",
                                                command_id=command_id))
    return {"command_id": command_id, "type": "track.measured", "track": track_id, "measurement": number,
            "revision": record["revision"], "event": event.public_dict()}


def correct_track(root: Path, *, track_id: str, index: int, actor: Actor, points: list | None = None,
                  corners: list | None = None, note: str = "", expected_revision: int | None = None) -> dict[str, Any]:
    """A person's correction of one entry of the measurement in use: kept apart, in force until reverted."""

    root = Path(root).expanduser().resolve()
    folder = directory(root, track_id)
    with scene_lock(folder):
        record = _record(folder)
        if expected_revision is not None and expected_revision != record["revision"]:
            raise ValidationError(f"The track {track_id} is at revision {record['revision']}, not {expected_revision}")
        if not 0 <= index < int(record["frames"]):
            raise ValidationError(f"The track {track_id} has entries 0 to {int(record['frames']) - 1}, not {index}")
        value = _entry_value(record["kind"], points, corners)
        corrections = _corrections(folder)
        correction = {"id": "cor_" + uuid.uuid4().hex[:12], "index": int(index), **value,
                      "measurement": record["measurement"], "active": True, "note": note, "at": _now(),
                      "by": actor.public_dict()}
        corrections.append(correction)
        _write(folder / "corrections.json", json.dumps(corrections, indent=1))
        record["revision"] = int(record["revision"]) + 1
        record["updated_at"] = _now()
        _write(folder / "track.yaml", yaml.safe_dump(record, sort_keys=False))
        event = append_event(root, Event.create("track.corrected", _project_id(root), track_id=track_id, index=index,
                                                correction=correction["id"], revision=record["revision"],
                                                actor=actor.public_dict(), rationale=note))
    return {"type": "track.corrected", "track": track_id, "correction": correction["id"],
            "revision": record["revision"], "event": event.public_dict()}


def revert_corrections(root: Path, *, track_id: str, actor: Actor, correction: str | None = None,
                       index: int | None = None, note: str = "") -> dict[str, Any]:
    """Take corrections out of force -- one by its id, those of one entry, or all -- keeping them in the record."""

    root = Path(root).expanduser().resolve()
    folder = directory(root, track_id)
    with scene_lock(folder):
        record = _record(folder)
        corrections = _corrections(folder)
        chosen = [item for item in corrections if item["active"]
                  and (correction is None or item["id"] == correction) and (index is None or item["index"] == index)]
        if not chosen:
            raise ValidationError(f"The track {track_id} has no correction in force to revert there")
        for item in chosen:
            item["active"] = False
            item["reverted"] = {"at": _now(), "by": actor.public_dict(), "note": note}
        _write(folder / "corrections.json", json.dumps(corrections, indent=1))
        record["revision"] = int(record["revision"]) + 1
        record["updated_at"] = _now()
        _write(folder / "track.yaml", yaml.safe_dump(record, sort_keys=False))
        event = append_event(root, Event.create("track.reverted", _project_id(root), track_id=track_id,
                                                corrections=[item["id"] for item in chosen],
                                                revision=record["revision"], actor=actor.public_dict(), rationale=note))
    return {"type": "track.reverted", "track": track_id, "reverted": [item["id"] for item in chosen],
            "revision": record["revision"], "event": event.public_dict()}


# --- reading ----------------------------------------------------------------------------------------------------

def _record(folder: Path) -> dict[str, Any]:
    if not (folder / "track.yaml").is_file():
        raise ValidationError(f"There is no track {folder.name} (measure it first)")
    return _read_yaml(folder / "track.yaml")


def _corrections(folder: Path) -> list[dict[str, Any]]:
    path = folder / "corrections.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def _entry_value(kind: str, points: Any, corners: Any) -> dict[str, Any]:
    def pairs(value: Any, count: int | None) -> bool:
        return (isinstance(value, list) and (count is None or len(value) == count) and value and
                all(isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(v, (int, float)) for v in p)
                    for p in value))

    if kind == "plane":
        if not pairs(corners, 4):
            raise ValidationError("A plane's correction is its four corners, [[x, y], ...], fractions of the picture")
        return {"corners": [[float(x), float(y)] for x, y in corners]}
    if not pairs(points, None):
        raise ValidationError("A point's correction is its points, [[x, y]], fractions of the picture")
    return {"points": [[float(x), float(y)] for x, y in points]}


def status(root: Path, track_id: str) -> dict[str, Any]:
    """What a track is, and whether it may be used: `stale` lists every reason it no longer describes its media
    (empty when it does); `weak` the stretches of low confidence; `corrections` in force and set aside."""

    from .compositing.tracking import TRACKER, TRACKER_VERSION, weak_spans

    root = Path(root).expanduser().resolve()
    folder = directory(root, track_id)
    record = _record(folder)
    measurement = json.loads((folder / "measurements" / f"{int(record['measurement']):04d}.json").read_text())
    made = measurement["measured"]
    stale = []
    path = root / record["media"]
    if not path.is_file():
        stale.append(f"its media {record['media']} is not there")
    elif _media_hash(root, record["media"]) != made["media_hash"]:
        stale.append(f"its media {record['media']} has changed since it was measured")
    if (made.get("tracker"), made.get("version")) != (TRACKER, TRACKER_VERSION):
        stale.append(f"it was measured by {made.get('tracker')} {made.get('version')}, and tracking is now "
                     f"{TRACKER} {TRACKER_VERSION}")
    for key in ("kind", "region", "start", "frames"):
        asked = record.get(key)
        given = measurement.get(key) if key == "kind" else made.get(key)
        if asked != given:
            stale.append(f"its {key} is now {asked!r}; it was measured with {given!r}")
    corrections = _corrections(folder)
    in_force = [item for item in corrections if item["active"] and item["measurement"] == record["measurement"]]
    behind = [item for item in corrections if item["active"] and item["measurement"] != record["measurement"]]
    return {"id": track_id, "kind": record["kind"], "media": record["media"], "revision": record["revision"],
            "measurement": record["measurement"], "stale": stale, "weak": weak_spans(measurement),
            "corrections": len(in_force), "corrections_on_earlier_measurements": len(behind),
            "remeasure": f"toast track measure {root} {track_id} --media {record['media']} --kind {record['kind']}"}


def load_track(root: Path, track_id: str) -> dict[str, Any]:
    """The track a graph reads: the measurement in use with the corrections in force laid over it (each
    corrected entry marked, at full confidence). Refused when stale."""

    root = Path(root).expanduser().resolve()
    folder = directory(root, track_id)
    state = status(root, track_id)
    if state["stale"]:
        raise ValidationError(f"The track {track_id} is stale: {'; '.join(state['stale'])} -- measure it again "
                              f"({state['remeasure']})")
    record = _record(folder)
    measurement = json.loads((folder / "measurements" / f"{int(record['measurement']):04d}.json").read_text())
    frames = [dict(entry) for entry in measurement["frames"]]
    for item in _corrections(folder):
        if item["active"] and item["measurement"] == record["measurement"]:
            key = "corners" if "corners" in item else "points"
            frames[item["index"]] = {key: item[key], "confidence": 1.0, "corrected": item["id"]}
    return {"id": track_id, "kind": measurement["kind"], "clock": measurement["clock"], "frames": frames,
            "media": record["media"], "measured": measurement["measured"], "revision": record["revision"]}


def media_origin(track: dict[str, Any]) -> Fraction:
    return timebase.from_record(track["clock"]["origin"])
