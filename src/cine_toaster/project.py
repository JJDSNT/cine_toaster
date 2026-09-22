from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import ResourceNotFoundError, ValidationError
from .geometry import Finding, check_geometry, parse_geometry
from .looks import load_looks, resolve as resolve_look
from .state import SceneState, load_scene_state
from .transitions import list_transitions
from .takes import discover, shot_key, work_directory_for
from .vocabulary import (
    LEGACY_KEYS,
    COMPOSED_ENGINES,
    GENERATED_NOTHING,
    KIND_ENGINES,
    KIND_SOURCES,
    KNOWN_SHOT_FIELDS,
    SOURCES,
    PROJECT_FILE,
    SCENE_DIRECTORIES,
    SCENE_FILES,
    field,
    shot_kind,
    status as normalize_status,
)
from .vocabulary import text as vtext


DONE_STATUSES = {"approved", "complete", "completed", "selected"}
ATTENTION_STATUSES = {"blocked", "needs_review", "in_review", "failed"}


class ProjectFormatError(ValueError):
    """Raised when a Cine Toaster project file is invalid."""


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
    except yaml.YAMLError as error:
        raise ProjectFormatError(f"Invalid YAML in {path}: {error}") from error
    if document is None:
        return {}
    if not isinstance(document, dict):
        raise ProjectFormatError(f"{path} must contain a mapping at the top level")
    return document


def _require(document: dict[str, Any], key: str, path: Path) -> Any:
    value = document.get(key)
    if value in (None, ""):
        raise ProjectFormatError(f"Missing {key!r} in {path}")
    return value


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def scene_files(root: Path, manifest: dict[str, Any] | None = None) -> list[Path]:
    """Every breakdown in the production, one per scene.

    A scene may exist in more than one variant -- the same scene reworked for a
    different engine. The project names the variant in production; the others
    stay on disk as history without competing for the scene id.
    """

    root = root.expanduser().resolve()
    if manifest is None:
        manifest_path = root / PROJECT_FILE
        manifest = _read_yaml(manifest_path) if manifest_path.is_file() else {}

    paths = field(manifest, "paths") or {}
    declared = vtext(paths, "scenes")
    directory = root / declared if declared else None
    if directory is None or not directory.is_dir():
        directory = next(
            (root / name for name in SCENE_DIRECTORIES if (root / name).is_dir()),
            None,
        )
    if directory is None:
        return []

    wanted = vtext(field(manifest, "production") or {}, "variant")
    by_scene: dict[str, tuple[int, Path]] = {}
    candidates: list[Path] = []
    for name in SCENE_FILES:
        candidates.extend(sorted(directory.glob(f"*/**/{name}")))
        candidates.extend(sorted(directory.glob(f"*/{name}")))
    for path in candidates:
        document = _read_yaml(path)
        scene_id = vtext(document, "scene") or _text(document.get("id"))
        if not scene_id:
            continue
        variant = vtext(document, "variant")
        # A file matching the production variant wins; otherwise the plain one.
        rank = 2 if (wanted and variant == wanted) else (0 if variant else 1)
        current = by_scene.get(scene_id)
        if current is None or rank > current[0]:
            by_scene[scene_id] = (rank, path)
    return [path for _rank, path in sorted(by_scene.values(), key=lambda item: str(item[1]))]


def _load_shots(
    document: dict[str, Any],
    path: Path,
    root: Path,
    declared_fields: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    raw_shots = field(document, "shots") or []
    if not isinstance(raw_shots, list):
        raise ProjectFormatError(f"shots must be a list in {path}")

    declared_fields = declared_fields or {}
    work = work_directory_for(path)
    shots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_shots:
        if not isinstance(raw, dict):
            raise ProjectFormatError(f"Each shot must be a mapping in {path}")
        number = raw.get("n")
        if number in (None, ""):
            raise ProjectFormatError(f"A shot is missing its number in {path}")
        shot_id = f"P{shot_key(number)}"
        if shot_id in seen:
            raise ProjectFormatError(f"Duplicate shot {number!r} in {path}")
        seen.add(shot_id)

        kind = shot_kind(field(raw, "kind"))
        source = vtext(raw, "source") or KIND_SOURCES.get(kind, "generated")
        engine = vtext(raw, "engine") or KIND_ENGINES.get(kind, "")
        composed = source == "composed" or engine in COMPOSED_ENGINES
        takes = (
            []
            if kind in GENERATED_NOTHING or composed
            else [take.public_dict() for take in discover(work, number, relative_to=root)]
        )
        extra, unknown = _extra_shot_fields(raw, declared_fields)
        shots.append(
            {
                "id": shot_id,
                "number": _text(number),
                "label": vtext(raw, "label")[:160] or shot_id,
                "kind": kind,
                "source": source,
                "engine": engine,
                "camera": _text(raw.get("camera_id") or raw.get("_camera")),
                "subject": vtext(raw, "subject"),
                "looks_at": vtext(raw, "looks_at"),
                "description": vtext(raw, "action"),
                "duration_seconds": float(field(raw, "duration") or 0),
                "look": vtext(raw, "look"),
                "from": _lineage(raw),
                "variant": vtext(raw, "variant"),
                "text": field(raw, "text"),
                "ops": field(raw, "ops") or [],
                "sound": field(raw, "sound"),
                "notes": _notes(raw),
                "lines": _lines(raw),
                "transition": _transition(raw),
                "authored_status": "",
                "authored_selected_take": "",
                "out_of_cut": bool(field(raw, "out_of_cut")),
                "extra_fields": extra,
                "unknown_fields": unknown,
                "takes": takes,
                "take_count": len(takes),
            }
        )
    return shots


def _lineage(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """What these frames come from, however the breakdown spelled it.

    Seven legacy keys said this -- `usa`, `usa_de`, `usa_arquivo`,
    `usa_ultimo_de`, `reusa`, `deriva`, `ref`. They are one concept.
    """

    entries: list[dict[str, Any]] = []
    for name in ("from", *LEGACY_KEYS["from"]):
        value = raw.get(name)
        if value in (None, "", [], {}):
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            if isinstance(item, dict):
                entries.append({"ref": _text(item.get("ref") or item.get("id")), **item})
            else:
                entries.append({"ref": _text(item), "relation": name if name != "from" else ""})
    return entries


def _notes(raw: dict[str, Any]) -> list[str]:
    notes = []
    for name in ("notes", *LEGACY_KEYS["notes"]):
        value = raw.get(name)
        if value in (None, ""):
            continue
        notes.extend(value if isinstance(value, list) else [_text(value)])
    return notes


def _lines(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Spoken lines. The field OpenMontage has nowhere to put (CT-0014)."""

    lines: list[dict[str, Any]] = []
    for item in field(raw, "lines") or []:
        if not isinstance(item, dict):
            continue
        lines.append(
            {
                "who": vtext(item, "who"),
                "text": vtext(item, "text") or _text(item.get("pt")),
                "en": _text(item.get("en")),
                "delivery": vtext(item, "delivery"),
                "voice": vtext(item, "voice"),
                "mix": field(item, "mix") or {},
            }
        )
    return lines


def _transition(raw: dict[str, Any]) -> dict[str, Any] | None:
    """A reference into the transition catalog, with why it was chosen."""

    value = field(raw, "transition")
    if not value:
        return None
    if not isinstance(value, dict):
        return {"id": _text(value), "duration_ms": None, "reason": ""}
    return {
        "id": _text(value.get("id")),
        "duration_ms": value.get("duration_ms"),
        "reason": vtext(value, "reason"),
    }


def _extra_shot_fields(
    raw: dict[str, Any],
    declared: dict[str, str],
) -> tuple[dict[str, Any], list[str]]:
    """Split what the core does not type into declared extras and passthrough.

    Nothing is dropped (SPEC-0004). A key the production declared is carried
    under its own label; anything else is carried verbatim and reported, so a
    field the schema does not understand is visible rather than silent.
    """

    extra: dict[str, Any] = {}
    unknown: list[str] = []
    for key, value in raw.items():
        name = str(key)
        if name in KNOWN_SHOT_FIELDS:
            continue
        if name in declared:
            extra[name] = {"label": declared[name], "value": value}
        else:
            extra[name] = {"label": name, "value": value}
            unknown.append(name)
    return extra, sorted(unknown)


def _camera_assignments(geography: dict[str, Any]) -> dict[str, str]:
    """Which camera covers which shot, read from the geography plan."""

    assignments: dict[str, str] = {}
    for camera in (geography or {}).get("cameras") or []:
        if not isinstance(camera, dict):
            continue
        camera_id = _text(camera.get("id"))
        if not camera_id:
            continue
        for number in str(field(camera, "shots", "")).split():
            if number.strip("()"):
                assignments[f"P{shot_key(number.strip('()'))}"] = camera_id
    return assignments


def _apply_state(shots: list[dict[str, Any]], state: SceneState) -> None:
    """Overlay committed decisions on what the breakdown and the disk describe."""

    for shot in shots:
        selection = state.selections.get(shot["id"])
        if selection is not None:
            shot["selected_take"] = selection.take_id
            shot["selection"] = selection.public_dict()
            shot["status"] = "selected"
        else:
            shot["selected_take"] = ""
            shot["selection"] = None
            if shot["out_of_cut"]:
                shot["status"] = "not_started"
            elif shot["take_count"] > 1:
                shot["status"] = "needs_review"
            elif shot["take_count"] == 1:
                shot["status"] = "ready"
            else:
                shot["status"] = "not_started"
        for take in shot["takes"]:
            take["selected"] = bool(shot["selected_take"]) and take["id"] == shot["selected_take"]


def _load_scene(
    path: Path,
    root: Path,
    declared_fields: dict[str, str] | None = None,
    project_look: str = "",
) -> dict[str, Any]:
    document = _read_yaml(path)
    scene_id = vtext(document, "scene") or _text(document.get("id"))
    if not scene_id:
        raise ProjectFormatError(f"Missing 'scene' in {path}")

    geography = field(document, "geography") or {}
    shots = _load_shots(document, path, root, declared_fields)
    assignments = _camera_assignments(geography)
    for shot in shots:
        if not shot["camera"]:
            shot["camera"] = assignments.get(shot["id"], "")

    directory = path.parent
    state = load_scene_state(directory, scene_id)
    _apply_state(shots, state)

    try:
        geometry = parse_geometry(_geometry_document(geography))
    except ValidationError as error:
        raise ProjectFormatError(f"{error.message} (in {path})") from error
    findings = [
        finding.public_dict() for finding in check_geometry(geometry, shots, scene_id=scene_id)
    ]
    findings.extend(finding.public_dict() for finding in _check_shot_fields(shots, scene_id))
    findings.extend(
        finding.public_dict() for finding in _check_transitions(shots, scene_id, root)
    )

    decisions = [
        {
            "question": vtext(item, "question"),
            "status": normalize_status(item.get("status")) or "proposed",
            "answer": vtext(item, "proposal") or vtext(item, "answer"),
        }
        for item in (field(document, "decisions") or [])
        if isinstance(item, dict)
    ]

    scene_look = vtext(document, "look")
    for shot in shots:
        value, level = resolve_look(
            shot=shot["look"], scene=scene_look, project=project_look
        )
        shot["look"] = value
        shot["look_from"] = level

    pending_shots = [shot["id"] for shot in shots if shot["status"] == "needs_review"]
    decided = sum(1 for shot in shots if shot["selected_take"])
    total_decidable = sum(1 for shot in shots if shot["take_count"])

    return {
        "id": scene_id,
        "order": int(field(document, "order") or 0),
        "title": vtext(document, "title") or scene_id,
        "sequence": vtext(document, "sequence"),
        "sequence_id": "",
        "variant": vtext(document, "variant"),
        "look": scene_look,
        "status": "in_review" if pending_shots else ("selected" if decided else "not_started"),
        "current_step": vtext(document, "step") or "review",
        "iteration": len(state.assemblies) or 1,
        "duration_seconds": sum(shot["duration_seconds"] for shot in shots),
        "summary": vtext(document, "summary"),
        "direction": vtext(document, "direction"),
        "updated_at": state.updated_at,
        "path": directory.relative_to(root).as_posix(),
        "file": path.relative_to(root).as_posix(),
        "progress": round(decided / total_decidable * 100) if total_decidable else 0,
        "revision": state.revision,
        "workflow": field(document, "steps") or [],
        "shots": shots,
        "decisions": decisions,
        "iterations": [],
        "blockers": field(document, "blockers") or [],
        "geometry": geometry.public_dict(),
        "findings": findings,
        "decision_log": list(reversed(state.decisions)),
        "pending_shots": pending_shots,
        "assemblies": [assembly.public_dict() for assembly in reversed(state.assemblies)],
        "approved_assembly": (
            state.approved_assembly().public_dict() if state.approved_assembly() else None
        ),
    }


def _check_transitions(
    shots: list[dict[str, Any]],
    scene_id: str,
    root: Path,
) -> list[Finding]:
    """A transition must name something the catalog actually has.

    An id nothing resolves would render as a plain cut, and the choice would be
    lost without anyone being told.
    """

    referenced = {
        shot["transition"]["id"]: shot["id"]
        for shot in shots
        if shot.get("transition") and shot["transition"].get("id")
    }
    if not referenced:
        return []
    try:
        available = {item["id"] for item in list_transitions(root)}
    except Exception:
        return []
    findings: list[Finding] = []
    for transition_id, shot_id in sorted(referenced.items()):
        if transition_id in available:
            continue
        findings.append(
            Finding(
                code="transition_unknown",
                severity="error",
                message=(
                    f"Shot {shot_id} asks for transition {transition_id!r}, which is in no "
                    f"catalog. It would render as a cut."
                ),
                scene_id=scene_id,
                shots=(shot_id,),
            )
        )
    return findings


def _check_shot_fields(shots: list[dict[str, Any]], scene_id: str) -> list[Finding]:
    """Report shot keys nothing understands.

    A field the schema does not know must be visible, not silent (SPEC-0004).
    It is advisory: the breakdown is still correct and still loads, and the
    author chooses between declaring the key and letting a family absorb it.
    """

    by_field: dict[str, list[str]] = {}
    for shot in shots:
        for name in shot.get("unknown_fields") or []:
            by_field.setdefault(name, []).append(shot["id"])
    findings: list[Finding] = []
    for name, shot_ids in sorted(by_field.items()):
        findings.append(
            Finding(
                code="shot_field_undeclared",
                severity="advice",
                message=(
                    f"{name!r} is used by {len(shot_ids)} shot(s) and nothing reads it. "
                    f"Declare it under 'shot_fields' in project.yaml, or move it into a "
                    f"field the schema knows."
                ),
                scene_id=scene_id,
                shots=tuple(shot_ids),
            )
        )
    return findings


def _geometry_document(geography: dict[str, Any]) -> dict[str, Any] | None:
    """Translate the breakdown's plan into the Core's geometry vocabulary.

    The file speaks the production's language; the domain model speaks one of
    its own. This is the only place the two meet.
    """

    if not geography:
        return None

    room = field(geography, "room")
    subjects: list[dict[str, Any]] = []
    for person in field(geography, "subjects") or []:
        if not isinstance(person, dict) or "x" not in person:
            continue
        name = vtext(person, "label")
        subjects.append(
            {
                "id": person.get("id") or _identifier(name),
                "label": name,
                "position": [float(person["x"]), float(person["y"])],
                "eye_height": field(person, "eye_height"),
            }
        )

    by_position = {
        (round(item["position"][0], 2), round(item["position"][1], 2)): item["id"]
        for item in subjects
    }
    cameras: list[dict[str, Any]] = []
    seen: set[str] = set()
    for camera in field(geography, "cameras") or []:
        if not isinstance(camera, dict) or "x" not in camera:
            continue
        camera_id = _text(camera.get("id"))
        if not camera_id or camera_id in seen:
            continue
        seen.add(camera_id)
        aim = field(camera, "target")
        target: Any = aim
        if isinstance(aim, (list, tuple)) and len(aim) == 2:
            key = (round(float(aim[0]), 2), round(float(aim[1]), 2))
            target = by_position.get(key, [float(aim[0]), float(aim[1])])
        cameras.append(
            {
                "id": camera_id,
                "label": vtext(camera, "label") or camera_id,
                "position": [float(camera["x"]), float(camera["y"])],
                "height": field(camera, "height"),
                "target": target,
                "lens_mm": field(camera, "lens_mm", 50),
            }
        )

    document: dict[str, Any] = {"units": "m", "subjects": subjects, "cameras": cameras}
    if isinstance(room, (list, tuple)) and len(room) >= 2:
        document["room"] = {
            "width": float(room[0]),
            "depth": float(room[1]),
            "height": float(room[2]) if len(room) > 2 else 2.7,
        }
    axis = field(geography, "axis")
    if isinstance(axis, (list, tuple)) and len(axis) == 2:
        document["axis"] = {
            "between": [
                by_position.get(tuple(value), _identifier(_text(value)))
                if not isinstance(value, str)
                else _identifier(value)
                for value in axis
            ]
        }
    return document


def _identifier(name: str) -> str:
    import re
    import unicodedata

    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").upper() or "SUBJECT"


def scene_directory(root: Path, scene_id: str) -> Path:
    """Where one scene's breakdown and runtime state live."""

    root = root.expanduser().resolve()
    for path in scene_files(root):
        if vtext(_read_yaml(path), "scene") == scene_id:
            return path.parent
    raise ResourceNotFoundError(f"Scene {scene_id!r} is not part of this production")


def _load_sequences(
    manifest: dict[str, Any],
    scenes: list[dict[str, Any]],
    path: Path,
) -> list[dict[str, Any]]:
    """Group scenes into the unit a director actually reviews."""

    raw_sequences = field(manifest, "sequences") or []
    if not isinstance(raw_sequences, list):
        raise ProjectFormatError(f"sequences must be a list in {path}")

    by_id = {scene["id"]: scene for scene in scenes}
    claimed: set[str] = set()
    sequences: list[dict[str, Any]] = []
    for raw in raw_sequences:
        if not isinstance(raw, dict):
            raise ProjectFormatError(f"Each sequence must be a mapping in {path}")
        sequence_id = _text(_require(raw, "id", path))
        members: list[dict[str, Any]] = []
        missing: list[str] = []
        for scene_id in field(raw, "scenes") or []:
            scene = by_id.get(_text(scene_id))
            if scene is None:
                missing.append(_text(scene_id))
                continue
            members.append(scene)
            claimed.add(scene["id"])
        if missing:
            raise ProjectFormatError(
                f"sequence {sequence_id!r} lists unknown scenes {', '.join(missing)} in {path}"
            )

        decided = sum(
            1
            for scene in members
            for shot in scene["shots"]
            if shot["take_count"] and shot["selected_take"]
        )
        undecided = sum(len(scene["pending_shots"]) for scene in members)
        sequences.append(
            {
                "id": sequence_id,
                "label": vtext(raw, "label") or sequence_id,
                "act": vtext(raw, "act"),
                "status": normalize_status(raw.get("status")) or "in_progress",
                "render": vtext(raw, "render"),
                "summary": vtext(raw, "summary"),
                "scene_ids": [scene["id"] for scene in members],
                "scene_count": len(members),
                "duration_seconds": sum(scene["duration_seconds"] for scene in members),
                "decided_shots": decided,
                "pending_shots": undecided,
                "open_findings": sum(len(scene["findings"]) for scene in members),
                "progress": round(decided / (decided + undecided) * 100)
                if decided + undecided
                else 0,
            }
        )

    loose = [scene["id"] for scene in scenes if scene["id"] not in claimed]
    if sequences and loose:
        sequences.append(
            {
                "id": "unassigned",
                "label": "Not in a sequence yet",
                "act": "",
                "status": "in_progress",
                "render": "",
                "summary": "",
                "scene_ids": loose,
                "scene_count": len(loose),
                "duration_seconds": sum(by_id[item]["duration_seconds"] for item in loose),
                "decided_shots": 0,
                "pending_shots": sum(len(by_id[item]["pending_shots"]) for item in loose),
                "open_findings": sum(len(by_id[item]["findings"]) for item in loose),
                "progress": 0,
            }
        )
    return sequences


def _declared_shot_fields(manifest: dict[str, Any]) -> dict[str, str]:
    """Shot keys this production declares, with the label it wants shown.

    A production accretes fields the application has no opinion about. Naming
    them here is how a film keeps its own vocabulary without the general schema
    growing a field for it (SPEC-0004).
    """

    declared: dict[str, str] = {}
    raw = manifest.get("shot_fields") or {}
    if isinstance(raw, dict):
        for name, value in raw.items():
            if isinstance(value, dict):
                declared[str(name)] = _text(value.get("label")) or str(name)
            else:
                declared[str(name)] = _text(value) or str(name)
    elif isinstance(raw, list):
        for name in raw:
            declared[str(name)] = str(name)
    return declared


def load_production(root: Path) -> dict[str, Any]:
    """Load the operational model of one production, straight from its files."""

    root = root.expanduser().resolve()
    manifest_path = root / PROJECT_FILE
    if not manifest_path.is_file():
        raise FileNotFoundError(f"No Cine Toaster project file: {manifest_path}")

    manifest = _read_yaml(manifest_path)
    project_id = _text(_require(manifest, "id", manifest_path))
    title = vtext(manifest, "title")
    if not title:
        raise ProjectFormatError(f"Missing 'title' in {manifest_path}")

    declared_fields = _declared_shot_fields(manifest)
    project_look = vtext(manifest, "look")
    scenes = [
        _load_scene(path, root, declared_fields, project_look)
        for path in scene_files(root, manifest)
    ]
    scenes.sort(key=lambda scene: (scene["order"], scene["id"]))
    scene_ids = [scene["id"] for scene in scenes]
    if len(scene_ids) != len(set(scene_ids)):
        raise ProjectFormatError("Scene ids must be unique")

    sequences = _load_sequences(manifest, scenes, manifest_path)
    for sequence in sequences:
        for scene_id in sequence["scene_ids"]:
            next(scene for scene in scenes if scene["id"] == scene_id)["sequence_id"] = sequence[
                "id"
            ]

    attention: list[dict[str, Any]] = []
    for scene in scenes:
        for finding in scene["findings"]:
            if finding["severity"] == "error":
                attention.append(
                    {
                        "kind": "continuity",
                        "scene_id": scene["id"],
                        "scene_title": scene["title"],
                        "message": finding["message"],
                    }
                )
        for blocker in scene["blockers"]:
            attention.append(
                {
                    "kind": "blocker",
                    "scene_id": scene["id"],
                    "scene_title": scene["title"],
                    "message": _text(blocker),
                }
            )

    production = field(manifest, "production") or {}
    active_scene_id = vtext(production, "active_scene")
    active_scene = next((scene for scene in scenes if scene["id"] == active_scene_id), None)

    return {
        "schema_version": int(manifest.get("schema_version") or 1),
        "id": project_id,
        "title": title,
        "format": vtext(manifest, "format") or "Film",
        "logline": _text(manifest.get("logline")),
        "look": project_look,
        "looks": {name: look.public_dict() for name, look in load_looks(root).items()},
        "production": production,
        "phases": field(manifest, "phases") or [],
        "sequences": sequences,
        "scenes": scenes,
        "active_scene": active_scene,
        "attention": attention,
        "metrics": {
            "total_scenes": len(scenes),
            "approved_scenes": sum(scene["status"] in DONE_STATUSES for scene in scenes),
            "in_progress_scenes": sum(scene["status"] == "in_review" for scene in scenes),
            "attention_items": len(attention),
            "pending_shots": sum(len(scene["pending_shots"]) for scene in scenes),
            "open_findings": sum(len(scene["findings"]) for scene in scenes),
            "total_sequences": len([item for item in sequences if item["id"] != "unassigned"]),
            "overall_progress": round(
                sum(scene["progress"] for scene in scenes) / len(scenes)
            )
            if scenes
            else 0,
        },
    }


def load_scene(root: Path, scene_id: str) -> dict[str, Any] | None:
    production = load_production(root)
    return next((scene for scene in production["scenes"] if scene["id"] == scene_id), None)
