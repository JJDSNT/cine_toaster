"""Locations and the backlot: a set declared once, pinned from a shared library (SPEC-0010).

A location holds a set's plan -- room, marks, tested camera positions -- and
what it looks like. A scene that says `location: <id>` takes its plan from it
and adds what is its own (who is in the room, which shots each camera covers).
A backlot is a folder of locations shared across productions; a production
pins a copy, and updating it is an explicit act.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .errors import ValidationError

DIRECTORY = "locations"
FILE = "location.yaml"
PIN = "pinned.json"


def _key(value: Any) -> str:
    return str(value or "").strip().upper()


def _read(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValidationError(f"{path} is not a mapping")
    return raw


def _location(path: Path, root: Path | None) -> dict[str, Any]:
    raw = _read(path)
    base = path.parent
    references = []
    for item in raw.get("references") or []:
        if not isinstance(item, dict) or not item.get("path"):
            continue
        target = (base / str(item["path"])).resolve()
        shown = target.relative_to(root.resolve()).as_posix() if root and target.is_relative_to(root.resolve()) else str(item["path"])
        references.append({"path": shown, "kind": str(item.get("kind") or "plate"), "camera": str(item.get("camera") or ""),
                           "exists": target.is_file()})
    pin = base / PIN
    return {
        "id": _key(raw.get("id") or base.name),
        "label": str(raw.get("label") or raw.get("id") or base.name),
        "description": str(raw.get("description") or ""),
        "room": raw.get("room"),
        "marks": [dict(item) for item in raw.get("marks") or [] if isinstance(item, dict)],
        "cameras": [dict(item) for item in raw.get("cameras") or [] if isinstance(item, dict)],
        "references": references,
        "look": str(raw.get("look") or ""),
        "directory": base.relative_to(root).as_posix() if root and base.is_relative_to(root) else str(base),
        "pinned": json.loads(pin.read_text(encoding="utf-8")) if pin.is_file() else None,
    }


def load_locations(root: Path) -> dict[str, dict[str, Any]]:
    """The production's locations, by id."""

    folder = root / DIRECTORY
    if not folder.is_dir():
        return {}
    found = {}
    for path in sorted(folder.glob(f"*/{FILE}")):
        location = _location(path, root)
        found[location["id"]] = location
    return found


def _same(a: dict[str, Any], b: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return all(a.get(key) == b.get(key) for key in keys if key in a and key in b)


def resolve(geography: dict[str, Any], location: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The scene's plan inside its location: (geography, differences worth reporting)."""

    notes: list[str] = []
    merged = dict(geography)
    if not merged.get("room") and location.get("room"):
        merged["room"] = location["room"]

    marks = {_key(mark.get("id")): dict(mark) for mark in location["marks"]}
    for mark in geography.get("marks") or []:
        key = _key(mark.get("id"))
        if key in marks and not _same(mark, marks[key], ("x", "y")):
            notes.append(f"mark {key} is at ({mark.get('x')}, {mark.get('y')}) here, "
                         f"({marks[key].get('x')}, {marks[key].get('y')}) in the location")
        marks[key] = {**marks.get(key, {}), **mark}
    if marks:
        merged["marks"] = list(marks.values())

    cameras = {_key(camera.get("id")): dict(camera) for camera in location["cameras"]}
    order = list(cameras)
    for camera in geography.get("cameras") or []:
        key = _key(camera.get("id"))
        if key in cameras and "x" in camera and not _same(camera, cameras[key], ("x", "y", "height", "lens_mm")):
            notes.append(f"camera {key} stands elsewhere here than in the location")
        if key not in cameras:
            order.append(key)
        # Without a position, the entry only says which shots the location's camera covers.
        cameras[key] = {**cameras.get(key, {}), **camera}
    if cameras:
        merged["cameras"] = [cameras[key] for key in order]
    return merged, notes


# --- the backlot ------------------------------------------------------------------


def backlot_roots() -> list[Path]:
    return [Path(raw).expanduser() for raw in os.environ.get("CINE_TOASTER_BACKLOT", "").split(os.pathsep) if raw]


def digest(folder: Path) -> str:
    """The content of a location folder, without its pin record."""

    hashed = hashlib.sha256()
    for path in sorted(item for item in folder.rglob("*") if item.is_file() and item.name != PIN):
        hashed.update(path.relative_to(folder).as_posix().encode())
        hashed.update(path.read_bytes())
    return hashed.hexdigest()[:16]


def backlot() -> dict[str, dict[str, Any]]:
    """Every location the backlot offers, by id (a later path wins)."""

    found = {}
    for folder in backlot_roots():
        for path in sorted(folder.glob(f"*/{FILE}")):
            location = _location(path, None)
            location["source"] = str(path.parent)
            location["digest"] = digest(path.parent)
            found[location["id"]] = location
    return found


def pin(root: Path, location_id: str, *, update: bool = False) -> dict[str, Any]:
    """Copy a backlot location into the production, recording where it came from."""

    offered = backlot().get(_key(location_id))
    if offered is None:
        raise ValidationError(f"The backlot has no location {location_id!r}",
                              available=sorted(backlot()) or ["(set CINE_TOASTER_BACKLOT)"])
    source = Path(offered["source"])
    target = root / DIRECTORY / source.name
    if target.exists() and not update:
        raise ValidationError(f"{target.relative_to(root)} is already pinned; pin --update replaces it with the backlot's")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(PIN))
    record = {"source": str(source), "digest": offered["digest"], "pinned_at": datetime.now(UTC).isoformat()}
    (target / PIN).write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {"id": offered["id"], "directory": target.relative_to(root).as_posix(), **record}


def status(root: Path) -> list[dict[str, Any]]:
    """For each pinned location: has the backlot moved on, has the copy been edited here?"""

    offered = backlot()
    report = []
    for location_id, location in load_locations(root).items():
        pinned = location["pinned"]
        if not pinned:
            continue
        folder = root / location["directory"]
        upstream = offered.get(location_id)
        report.append({
            "id": location_id,
            "pinned_at": pinned.get("pinned_at", ""),
            "edited_here": digest(folder) != pinned.get("digest"),
            "backlot_moved_on": bool(upstream and upstream["digest"] != pinned.get("digest")),
            "in_backlot": upstream is not None,
        })
    return report
