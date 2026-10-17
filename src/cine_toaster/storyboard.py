"""Draft storyboard images, independent of final stills and human approvals (ADR 0027)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .creation import content_digest, reference_snapshot
from .errors import PersistenceError, ResourceNotFoundError, RevisionConflictError, ValidationError
from .events import Event, append_event
from .project import load_production
from .state import Actor, now, scene_lock

MAX_IMAGE_BYTES = 32 * 1024 * 1024
SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def _inside(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValidationError("Storyboard files must stay inside this production")
    return resolved


def load_storyboard(root: Path, *, production: dict | None = None) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    project_id = (production if production is not None else load_production(root))["id"]
    path = _inside(root, root / "storyboard/state.json")
    if not path.exists():
        return {"schema_version": 1, "project_id": project_id, "revision": 0, "candidates": []}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if (state.get("schema_version") != 1 or state.get("project_id") != project_id
                or type(state.get("revision")) is not int or state["revision"] < 0
                or not isinstance(state.get("candidates"), list)):
            raise ValueError("unsupported schema, project identity or journal shape")
        ids = set()
        for item in state["candidates"]:
            if (not isinstance(item, dict) or any(not isinstance(item.get(key), str) for key in ("id", "scene", "shot", "title", "created_at", "based_on"))
                    or item["id"] in ids or type(item.get("version")) is not int or item["version"] < 1
                    or not isinstance(item.get("image"), dict) or not isinstance(item.get("inputs"), list)
                    or not isinstance(item.get("context"), dict) or not isinstance(item["context"].get("sha256"), str)
                    or any(not isinstance(item["image"].get(key), str) for key in ("path", "sha256"))):
                raise ValueError("invalid storyboard candidate")
            for source in item["inputs"]:
                if not isinstance(source, dict) or any(not isinstance(source.get(key), str) for key in ("id", "sha256")):
                    raise ValueError("invalid storyboard input")
            ids.add(item["id"])
        return state
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise PersistenceError(f"Cannot read storyboard/state.json: {error}") from error


def _context(production: dict, scene_id: str, shot_id: str) -> dict:
    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    shot = next((item for item in scene["shots"] if item["id"] == shot_id), None) if scene else None
    if shot is None:
        raise ResourceNotFoundError(f"No shot {scene_id}/{shot_id}")
    # Exclude runtime takes, selection/gates, render timestamps and other operational state.
    value = {"scene": scene_id, "shot": shot_id, "direction": scene.get("direction", ""),
             "style": scene.get("style", ""), "cast": scene.get("cast", {}),
             "intent": {key: shot.get(key) for key in ("label", "description", "subject", "camera", "camera_text",
                 "framing", "size", "move", "subjects_move", "ends_on", "duration_seconds", "script", "covers", "cut")}}
    return {"sha256": content_digest(value), "record": value}


def register_storyboard_candidate(root: Path, *, scene: str, shot: str, image: Path, title: str,
                                   expected_revision: int, actor: Actor, references: list[str] | None = None,
                                   based_on: str = "", note: str = "", provenance: dict | None = None) -> dict:
    """Import a new retained image version; never select a master or decide a human gate."""
    if any(not isinstance(value, str) or not value.strip() for value in (scene, shot, title)) or len(title) > 240:
        raise ValidationError("A storyboard candidate needs scene, shot and a title of at most 240 characters")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError("expected_revision must be a non-negative integer")
    if not isinstance(based_on, str) or not isinstance(note, str) or len(note) > 4000:
        raise ValidationError("based_on must be a candidate id; note must be at most 4000 characters")
    if provenance is None:
        provenance = {}
    try:
        if not isinstance(provenance, dict) or len(json.dumps(provenance, allow_nan=False).encode()) > 65536:
            raise ValueError("provenance must be a JSON object of at most 64 KiB")
    except (TypeError, ValueError) as error:
        raise ValidationError(str(error)) from error
    source = Path(image).expanduser().resolve()
    if source.suffix.lower() not in SUFFIXES:
        raise ValidationError("Storyboard images must be PNG, JPEG or WebP")
    try:
        with source.open("rb") as handle:
            pixels = handle.read(MAX_IMAGE_BYTES + 1)
    except OSError as error:
        raise ValidationError(f"Cannot read storyboard image: {error}") from error
    valid = (source.suffix.lower() == ".png" and pixels.startswith(b"\x89PNG\r\n\x1a\n")
             or source.suffix.lower() in (".jpg", ".jpeg") and pixels.startswith(b"\xff\xd8\xff")
             or source.suffix.lower() == ".webp" and pixels.startswith(b"RIFF") and pixels[8:12] == b"WEBP")
    if not valid or len(pixels) > MAX_IMAGE_BYTES:
        raise ValidationError("Image signature does not match its extension, or image exceeds 32 MiB")
    root = Path(root).expanduser().resolve()
    with scene_lock(root):
        state = load_storyboard(root)
        if state["revision"] != expected_revision:
            raise RevisionConflictError(expected_revision, state["revision"])
        context = _context(load_production(root), scene, shot)
        existing = [item for item in state["candidates"] if item["scene"] == scene and item["shot"] == shot]
        if based_on and not any(item["id"] == based_on for item in existing):
            raise ValidationError("based_on must name a candidate for the same scene and shot")
        inputs = reference_snapshot(root, [] if references is None else references)
        identity = "board_" + uuid.uuid4().hex[:16]
        relative = f"storyboard/images/{identity}{source.suffix.lower()}"
        target = _inside(root, root / relative)
        journal = _inside(root, root / "storyboard/state.json")
        candidate = {"id": identity, "scene": scene, "shot": shot, "title": title.strip(),
                     "version": len(existing) + 1, "based_on": based_on, "note": note,
                     "image": {"path": relative, "sha256": hashlib.sha256(pixels).hexdigest()},
                     "context": context, "inputs": inputs, "provenance": provenance,
                     "created_at": now(), "actor": actor.public_dict()}
        committed = {**state, "revision": state["revision"] + 1, "candidates": [*state["candidates"], candidate]}
        temporary = None
        wrote_image = False
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                wrote_image = True
                handle.write(pixels); handle.flush(); os.fsync(handle.fileno())
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=journal.parent,
                                             prefix=".saving-", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(committed, handle, ensure_ascii=False, indent=2)
                handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, journal)
        except OSError as error:
            # Only this operation's uncommitted new files; never an earlier candidate/source.
            if temporary:
                temporary.unlink(missing_ok=True)
            if wrote_image:
                target.unlink(missing_ok=True)
            raise PersistenceError(f"Could not save storyboard candidate: {error}") from error
        append_event(root, Event.create("storyboard.candidate_saved", state["project_id"],
            scene_id=scene, shot_id=shot, candidate_id=identity, revision=committed["revision"], actor=actor.public_dict()))
        return {"revision": committed["revision"], "candidate": candidate}


def storyboard_view(root: Path, scene: str = "") -> dict:
    root = Path(root).expanduser().resolve()
    state = load_storyboard(root)
    production = load_production(root)
    if scene and not any(item["id"] == scene for item in production["scenes"]):
        raise ResourceNotFoundError(f"No scene {scene!r}")
    candidates, sources = [], {}
    for item in state["candidates"]:
        if scene and item["scene"] != scene:
            continue
        findings = []
        available = False
        try:
            path = _inside(root, root / item["image"]["path"])
            available = path.is_file()
            if not available or hashlib.sha256(path.read_bytes()).hexdigest() != item["image"]["sha256"]:
                findings.append({"code": "image_changed", "message": "Recorded image is missing or changed"})
        except (OSError, ValidationError):
            available = False
            findings.append({"code": "image_unavailable", "message": "Recorded image is unavailable or outside the production"})
        try:
            if _context(production, item["scene"], item["shot"])["sha256"] != item["context"]["sha256"]:
                findings.append({"code": "story_changed", "message": "Shot or covered screenplay changed since this drawing"})
        except ResourceNotFoundError:
            findings.append({"code": "shot_missing", "message": "The recorded scene/shot no longer exists"})
        for source in item["inputs"]:
            ref_id = source["id"]
            if ref_id not in sources:
                try:
                    sources[ref_id] = reference_snapshot(root, [ref_id])[0]["sha256"]
                except (ValidationError, ResourceNotFoundError):
                    sources[ref_id] = None
            if sources[ref_id] != source["sha256"]:
                findings.append({"code": "input_changed", "message": f"Reference {ref_id} is missing or changed; recorded input retained"})
        candidates.append({**item, "findings": findings, "image_available": available, "review": "not_recorded"})
    coverage = [{"scene": item["id"], "shots": len(item["shots"]),
                 "with_candidates": sum(any(board["scene"] == item["id"] and board["shot"] == shot["id"] for board in state["candidates"])
                                        for shot in item["shots"])} for item in production["scenes"]]
    return {"project_id": state["project_id"], "revision": state["revision"], "scene": scene,
            "candidates": candidates, "coverage": coverage}
