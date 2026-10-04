from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .errors import ResourceNotFoundError, ValidationError
from .geometry import Finding, check_geometry, parse_geometry
from .movement import check_movement, shot_motions
from . import screenplay as script_model
from .blocks import scene_blocks
from .cast import appearances as cast_appearances, check_cast, load_cast
from .cuts import scene_cuts
from .looks import load_looks, resolve as resolve_look
from .state import SceneState, load_scene_state
from .transitions import list_transitions
from .takes import discover, shot_key, work_directory_for
from .vocabulary import (
    LEGACY_KEYS,
    CORE_SHOT_FIELDS,
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
        # A scene's archive and its versions' snapshots are history, never a scene competing for its id (ADR 0021).
        if {"archive", "versions"} & set(path.relative_to(directory).parts[:-1]):
            continue
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
    aliases: dict[str, tuple[str, dict[str, str]]] | None = None,
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
        # A production's own name for a core field, declared in its manifest,
        # stands in only where the canonical name is absent.
        for alias, (canonical, keys) in (aliases or {}).items():
            if alias in raw and field(raw, canonical) is None:
                value = raw[alias]
                if keys and isinstance(value, dict):
                    value = {keys.get(str(key), key): item for key, item in value.items()}
                raw = {**raw, canonical: value}
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
                # How long the shot plays in the cut; without one, the length of its
                # generation is the best estimate there is.
                "duration_seconds": float(field(raw, "duration") or field(raw, "generated_seconds") or 0),
                # How long a generation is asked to be (CT-0037): not the edit length.
                "generated_seconds": float(field(raw, "generated_seconds") or 0),
                # The loudness a shot's sound should sit at, when it is not speech (LUFS).
                "level_db": float(field(raw, "level_db")) if field(raw, "level_db") is not None else None,
                # What the shot's starting picture shows, in the words a model is given.
                "picture": vtext(raw, "picture"),
                # A shot's `camera` may be a camera id or, in a breakdown written for
                # a model, how the camera behaves ("static close-up, locked off").
                "camera_text": raw.get("camera") if isinstance(raw.get("camera"), str) else "",
                "look": vtext(raw, "look"),
                "from": _lineage(raw),
                "variant": vtext(raw, "variant"),
                "text": field(raw, "text"),
                "ops": field(raw, "ops") or [],
                "sound": field(raw, "sound"),
                "notes": _notes(raw),
                "lines": _lines(raw),
                "transition": _transition(raw),
                "subjects_move": _entries(field(raw, "subjects_move")),
                "subjects_at": _entries(field(raw, "subjects_at")),
                "move": field(raw, "move") if isinstance(field(raw, "move"), dict) else None,
                "size": vtext(raw, "size"),
                "framing": vtext(raw, "framing"),
                # A title from the catalog (CT-0031): on a card, or over the picture.
                "title": field(raw, "title") if isinstance(field(raw, "title"), (str, dict)) else None,
                # Effects from the VFX catalog, applied in order before the title (CT-0031).
                "effects": field(raw, "effects") if isinstance(field(raw, "effects"), (list, dict, str)) else None,
                # How the people in it feel, from the emotion catalog (CT-0048).
                "emotion": field(raw, "emotion") if isinstance(field(raw, "emotion"), (list, dict, str)) else None,
                # Sounds from the catalog, placed on the shot as cut (CT-0048).
                "sounds": field(raw, "sounds") if isinstance(field(raw, "sounds"), (list, dict, str)) else None,
                "ends_on": vtext(raw, "ends_on"),
                "motion": None,
                "covers": field(raw, "covers"),
                "cut": field(raw, "cut") if isinstance(field(raw, "cut"), dict) else None,
                # CT-0037: shots made together in one generation share a block.
                "block": _text(field(raw, "block")),
                "trim": field(raw, "trim") if isinstance(field(raw, "trim"), dict) else None,
                # The take's sound silenced in stretches, and faded from a point (CT-0054, SINGULAR's
                # `silenciar` and `som_baixa_de`).
                "mute": [list(map(float, item)) for item in field(raw, "mute") or [] if isinstance(item, list) and len(item) == 2],
                "sound_fades_at": float(field(raw, "sound_fades_at")) if field(raw, "sound_fades_at") not in (None, "") else None,
                # Where a format's frame sits in the take (CT-0049): {x, y}, 0 to 1, centred by default.
                "reframe": field(raw, "reframe") if isinstance(field(raw, "reframe"), dict) else None,
                "derive": _derive(field(raw, "derive")),
                "guide_at_cut": field(raw, "guide_at_cut") if isinstance(field(raw, "guide_at_cut"), bool) else None,
                "guide_strength": field(raw, "guide_strength"),
                "script": None,
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


def _entries(value: Any) -> list[dict[str, Any]]:
    """A list of mappings, or nothing; SPEC-0005 movement entries."""

    if isinstance(value, dict):
        value = [value]
    return [dict(item) for item in value or [] if isinstance(item, dict)]


def _lineage(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """What these frames come from, however the breakdown spelled it.

    Seven legacy keys said this -- `usa`, `usa_de`, `usa_arquivo`,
    `usa_ultimo_de`, `reusa`, `deriva`, `ref`. They are one concept.
    """

    entries: list[dict[str, Any]] = []
    for name in ("from", "derive", *LEGACY_KEYS["from"]):
        value = raw.get(name)
        if value in (None, "", [], {}):
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            if isinstance(item, dict):
                # A derivation names its source as `from` (legacy `deriva`: `de`).
                ref = item.get("ref") or item.get("id") or item.get("from") or item.get("de")
                entries.append({"ref": _text(ref), **item})
            else:
                entries.append({"ref": _text(item), "relation": name if name != "from" else ""})
    return entries


def _derive(value: Any) -> dict[str, Any] | None:
    """A picture made by editing another: `{from, with, request}`.

    `from` is the shot, master or file whose picture is edited (its geometry
    and framing are kept); `with` names the cast whose references lend
    identity; `request` says what the surfaces become.
    """

    if not isinstance(value, dict):
        return None
    cast = value.get("with") or []
    return {
        "from": _text(value.get("from")),
        "with": [_text(item) for item in (cast if isinstance(cast, list) else [cast])],
        "request": " ".join(_text(value.get("request")).split()),
    }


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
    value = field(raw, "lines") or []
    for item in [value] if isinstance(value, dict) else value:
        if not isinstance(item, dict):
            continue
        mix = field(item, "mix")
        lines.append(
            {
                "who": vtext(item, "who"),
                "text": vtext(item, "text") or _text(item.get("pt")),
                "en": _text(item.get("en")),
                "delivery": vtext(item, "delivery"),
                "voice": vtext(item, "voice"),
                "mix": mix if isinstance(mix, dict) else {},
                # A line marked for the mix only (`mix: true`) is added in the
                # montage: nobody says it in the take itself.
                "in_take": mix is not True,
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


def _phase(root: Path, path: Path, state: SceneState) -> dict[str, Any]:
    from .workflows import phase

    return phase(root, {"file": path.relative_to(root).as_posix()}, state.gates)


def _production_locations(root: Path, scenes: list[dict[str, Any]]) -> dict[str, Any]:
    from .locations import load_locations

    found = load_locations(root)
    for location_id, location in found.items():
        location["appearances"] = [scene["id"] for scene in scenes if scene.get("location") == location_id]
    return found


def _expand_camera_moves(shots: list[dict[str, Any]], scene_id: str, root: Path) -> list[Finding]:
    """`move: {id: push-in}` takes its kind, direction and rig from the camera-move catalog (CT-0027)."""

    if not any(isinstance(shot.get("move"), dict) and shot["move"].get("id") for shot in shots):
        return []
    from .camera_moves import expand, list_moves

    catalog = {move["id"]: move for move in list_moves(root)}
    findings = []
    for shot in shots:
        if not isinstance(shot.get("move"), dict):
            continue
        shot["move"], problem = expand(shot["move"], catalog)
        if problem:
            findings.append(Finding(code="move_unknown", severity="error", scene_id=scene_id, shots=(shot["id"],),
                                    message=f"{shot['id']} {problem}. It would be lost, not guessed."))
    return findings


def _expand_effects(shots: list[dict[str, Any]], scene_id: str, root: Path) -> list[Finding]:
    """`effects: [{id: film-grain}, ...]` take their defaults from the VFX catalog and elements (CT-0031)."""

    if not any(shot.get("effects") for shot in shots):
        return []
    from .vfx import expand, list_effects, list_elements

    catalog = {item["id"]: item for item in list_effects(root)}
    elements = {item["id"]: item for item in list_elements(root)}
    findings = []
    for shot in shots:
        if not shot.get("effects"):
            continue
        shot["effects"], problems = expand(shot["effects"], catalog, elements)
        for problem in problems:
            findings.append(Finding(code="effect_problem", severity="error", scene_id=scene_id, shots=(shot["id"],),
                                    message=f"{shot['id']} {problem}. It would be lost, not guessed."))
    return findings


def _surround(value: Any) -> str:
    """`surround: "5.1"` (a number in YAML too); off, false, none or stereo mean none."""

    text = str(value if value is not None else "").strip().lower()
    return "" if text in ("", "false", "no", "none", "off", "stereo", "0") else text


def _scene_style(document: dict[str, Any], scene_id: str, root: Path,
                 project_style: Any) -> tuple[dict[str, Any] | None, list[Finding]]:
    """The styles in force, one per axis -- technique, direction, format -- each the scene's or else the
    production's (CT-0049), combined."""

    scene_style = document.get("style")
    if not scene_style and not project_style:
        return None, []
    from .styles import list_styles, resolve, summary

    parts, problems = resolve({entry["id"]: entry for entry in list_styles(root)},
                              scene=scene_style, project=project_style)
    findings = [Finding(code="style_unknown", severity="error", scene_id=scene_id, shots=(), message=f"{problem}.")
                for problem in problems]
    return summary(parts), findings


def _expand_emotions(shots: list[dict[str, Any]], document: dict[str, Any], scene_id: str, root: Path,
                     people: set[str], default_intensity: str = "clear") -> list[Finding]:
    """`emotion: {id, who, intensity, arc}` takes its words from the emotion catalog (CT-0048)."""

    if not any(shot.get("emotion") for shot in shots):
        return []
    from .emotions import expand, list_emotions

    catalog = {item["id"]: item for item in list_emotions(root)}
    findings = []
    for shot in shots:
        if not shot.get("emotion"):
            continue
        known = people | {str(line.get("who") or "").upper() for line in shot.get("lines") or []}
        shot["emotion"], problems = expand(shot["emotion"], catalog, people={name for name in known if name},
                                           default_intensity=default_intensity)
        findings.extend(Finding(code="emotion_problem", severity="error", scene_id=scene_id, shots=(shot["id"],),
                                message=f"{shot['id']} {problem}. It would be lost, not guessed.")
                        for problem in problems)
    return findings


def _expand_sounds(shots: list[dict[str, Any]], document: dict[str, Any], scene_id: str,
                   root: Path) -> tuple[dict[str, list[dict[str, Any]]], list[Finding]]:
    """Shot `sounds` and scene `ambience` and `music` take their defaults from the sound catalog (CT-0048)."""

    beds: dict[str, list[dict[str, Any]]] = {"ambience": [], "music": []}
    if not any(shot.get("sounds") for shot in shots) and not any(document.get(kind) for kind in beds):
        return beds, []
    from .sounds import expand, list_sounds

    catalog = {item["id"]: item for item in list_sounds(root)}
    ids = tuple(shot["id"] for shot in shots)
    findings = []
    for shot in shots:
        if not shot.get("sounds"):
            continue
        shot["sounds"], problems = expand(shot["sounds"], catalog)
        findings.extend(Finding(code="sound_problem", severity="error", scene_id=scene_id, shots=(shot["id"],),
                                message=f"{shot['id']} {problem}. It would be lost, not guessed.")
                        for problem in problems)
    for kind in beds:
        beds[kind], problems = expand(document.get(kind), catalog, placed_on="scene", shots=ids)
        findings.extend(Finding(code="sound_problem", severity="error", scene_id=scene_id, shots=(),
                                message=f"The scene's {kind} {problem}. It would be lost, not guessed.")
                        for problem in problems)
    used = {sound["id"] for shot in shots for sound in shot.get("sounds") or []}
    used |= {sound["id"] for kind in beds for sound in beds[kind]}
    for sound_id in sorted(used):
        if catalog[sound_id].get("status") == "provisional":
            findings.append(Finding(
                code="sound_provisional", severity="advice", scene_id=scene_id, shots=(),
                message=f"The sound {sound_id!r} comes from {catalog[sound_id]['provenance'] or 'a provisional source'}; "
                        "replace it with the official file before the film is released."))
    return beds, findings


def _expand_titles(shots: list[dict[str, Any]], scene_id: str, root: Path) -> list[Finding]:
    """`title: {id: card, text: ...}` takes its engine, effect and defaults from the title catalog (CT-0031)."""

    if not any(shot.get("title") for shot in shots):
        return []
    from .titles import engine_missing, expand, list_titles

    catalog = {item["id"]: item for item in list_titles(root)}
    findings = []
    for shot in shots:
        if not shot.get("title"):
            continue
        shot["title"], problem = expand(shot["title"], catalog)
        if problem:
            findings.append(Finding(code="title_unknown", severity="error", scene_id=scene_id, shots=(shot["id"],),
                                    message=f"{shot['id']} {problem}. It would be lost, not guessed."))
        elif shot["title"] and engine_missing(shot["title"]["engine"]):
            findings.append(Finding(code="title_engine_missing", severity="warning", scene_id=scene_id,
                                    shots=(shot["id"],),
                                    message=f"{shot['id']}'s title {shot['title']['id']!r} is drawn by "
                                            f"{shot['title']['engine']}: {engine_missing(shot['title']['engine'])}."))
    return findings


def _apply_cut_decisions(shots: list[dict[str, Any]], state: SceneState) -> None:
    """A cut decided in the runtime stands over the breakdown's (plan step 13).

    The breakdown is not rewritten (ADR 0006): what it says stays visible as
    `authored_cut`/`authored_transition`, and clearing the decision returns to it.
    """

    for shot in shots:
        shot["voice_in_cut"] = state.voices.get(shot["id"])
        decision = state.cuts.get(shot["id"])
        shot["cut_decision"] = decision
        if not decision:
            continue
        shot["authored_cut"], shot["authored_transition"] = shot.get("cut"), shot.get("transition")
        shot["cut"] = {key: decision[key] for key in ("type", "chain", "reason", "split") if decision.get(key)}
        shot["transition"] = decision.get("transition") or None


def _apply_reference_decisions(shots: list[dict[str, Any]], state: SceneState) -> None:
    """What a shot is made from, decided in the runtime, stands over the breakdown's (CT-0046).

    The breakdown's lineage stays visible as `authored_from` (and a derived
    picture's cast as `authored_with`); clearing the decision returns to it.
    """

    for shot in shots:
        decision = state.references.get(shot["id"])
        shot["reference_decision"] = decision
        if not decision:
            continue
        authored = shot.get("from") or []
        shot["authored_from"] = authored
        # How it is made from it (the same picture, its last frame...) stays the breakdown's.
        relation = str((authored[0] if authored else {}).get("relation") or "")
        shot["from"] = [{"ref": decision["from"], "relation": relation, "decided": True}] if decision.get("from") else []
        derive = shot.get("derive")
        if derive:
            shot["authored_with"] = list(derive.get("with") or [])
            shot["derive"] = {**derive, "from": decision.get("from") or derive.get("from") or "",
                              "with": decision["with"] if decision.get("with") is not None else derive.get("with") or []}


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
    screenplay: script_model.Screenplay | None = None,
    aliases: dict[str, tuple[str, dict[str, str]]] | None = None,
    scene_aliases: dict[str, str] | None = None,
    project_style: Any = "",
    project_deliver: Any = None,
    project_surround: Any = None,
) -> dict[str, Any]:
    document = _read_yaml(path)
    scene_id = vtext(document, "scene") or _text(document.get("id"))
    if not scene_id:
        raise ProjectFormatError(f"Missing 'scene' in {path}")

    geography = field(document, "geography") or {}
    # SPEC-0010: a scene in a location takes the set's plan and adds its own.
    location_id = _text(_scene_field(document, "location", scene_aliases)).strip().upper()
    location_findings: list[Finding] = []
    if location_id:
        from .locations import load_locations, resolve

        location = load_locations(root).get(location_id)
        if location is None:
            location_findings.append(Finding(code="location_unknown", severity="error", scene_id=scene_id,
                message=f"The scene is set in {location_id}, which is not among the production's locations "
                        f"(locations/<id>/location.yaml)."))
        else:
            geography, differences = resolve(geography if isinstance(geography, dict) else {}, location)
            for difference in differences:
                location_findings.append(Finding(code="location_override", severity="advice", scene_id=scene_id,
                    message=f"In {location_id}, {difference}. Intended for this scene, or drift from the set?"))
    shots = _load_shots(document, path, root, declared_fields, aliases)
    assignments = _camera_assignments(geography)
    for shot in shots:
        if not shot["camera"]:
            shot["camera"] = assignments.get(shot["id"], "")

    directory = path.parent
    state = load_scene_state(directory, scene_id)
    _apply_state(shots, state)
    approved = state.approved_pictures()
    for shot in shots:
        shot["approved_picture"] = approved.get(shot["id"], "")
    _apply_cut_decisions(shots, state)
    _apply_reference_decisions(shots, state)
    location_findings.extend(_check_plates(root, location_id, shots, scene_id))

    try:
        geometry = parse_geometry(_geometry_document(geography))
    except ValidationError as error:
        raise ProjectFormatError(f"{error.message} (in {path})") from error
    move_findings = _expand_camera_moves(shots, scene_id, root)
    move_findings.extend(_expand_titles(shots, scene_id, root))
    move_findings.extend(_expand_effects(shots, scene_id, root))
    sound_beds, sound_findings = _expand_sounds(shots, document, scene_id, root)
    move_findings.extend(sound_findings)
    enter, enter_findings = _scene_enter(document, scene_id, root)
    move_findings.extend(enter_findings)
    style, style_findings = _scene_style(document, scene_id, root, project_style)
    people = {str(subject_id).upper() for subject_id in geometry.subjects}
    people |= {str(name).upper() for name in (_scene_field(document, "cast", scene_aliases) or {})}
    move_findings.extend(_expand_emotions(shots, document, scene_id, root, people,
                                          (style or {}).get("performance", {}).get("intensity", "clear")))
    if style:
        from .styles import departures

        style_findings.extend(
            Finding(code="style_departure", severity="advice", scene_id=scene_id, shots=(shot_id,) if shot_id else (),
                    message=f"{shot_id or scene_id} {what}.")
            for shot_id, what in departures(style, shots))
    move_findings.extend(style_findings)
    deliver = document.get("deliver") if document.get("deliver") is not None else project_deliver
    renditions: list[dict[str, Any]] = []
    if deliver:
        from .formats import renditions as parse_renditions
        from .styles import list_styles

        renditions, problems = parse_renditions(deliver, {entry["id"]: entry for entry in list_styles(root)})
        move_findings.extend(Finding(code="deliver_problem", severity="error", scene_id=scene_id, shots=(),
                                     message=f"{scene_id} {problem}.") for problem in problems)
    motions = shot_motions(geometry, shots, scene_id=scene_id)
    positions_by_shot = {motion.shot_id: motion.start_positions for motion in motions}
    findings = [
        finding.public_dict()
        for finding in check_geometry(
            geometry, shots, scene_id=scene_id, positions_by_shot=positions_by_shot
        )
    ]
    findings.extend(
        finding.public_dict()
        for finding in check_movement(geometry, shots, scene_id=scene_id, motions=motions)
    )
    if not geometry.is_empty():
        for shot, motion in zip(shots, motions):
            shot["motion"] = motion.public_dict()
        findings.extend(finding.public_dict() for finding in _check_hidden(geometry, shots, scene_id))
        findings.extend(finding.public_dict() for finding in _check_sizes(geometry, shots, scene_id))
    findings.extend(finding.public_dict() for finding in _check_shot_fields(shots, scene_id))
    findings.extend(finding.public_dict() for finding in move_findings)
    findings.extend(finding.public_dict() for finding in location_findings)
    findings.extend(
        finding.public_dict() for finding in _check_transitions(shots, scene_id, root)
    )
    script_link, script_findings = _link_screenplay(document, shots, scene_id, screenplay)
    findings.extend(finding.public_dict() for finding in script_findings)
    cuts, cut_findings = scene_cuts(
        shots,
        motions,
        geometry,
        scene_id=scene_id,
        screenplay_linked=bool(script_link and script_link.get("linked")),
        earlier=findings,
    )
    findings.extend(finding.public_dict() for finding in cut_findings)
    blocks = scene_blocks({"shots": shots}, work_directory_for(path), root)
    for block in blocks:
        if not block.contiguous:
            findings.append(Finding(
                code="block_not_contiguous", severity="warning", scene_id=scene_id, shots=tuple(block.shots),
                message=(f"Block {block.id} holds {', '.join(block.shots)}, which are not consecutive. "
                         f"A generation makes one continuous run of shots; the shots between would be cut out of it."),
            ).public_dict())

    decisions = [
        {
            "question": vtext(item, "question"),
            "status": normalize_status(item.get("status")) or "proposed",
            "answer": vtext(item, "proposal") or vtext(item, "answer"),
        }
        for item in (field(document, "decisions") or [])
        if isinstance(item, dict)
    ]

    stills = discover_stills(root, scene_id)
    for shot in shots:
        shot["still"] = stills.get(shot["id"], "")

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
        "script": script_link,
        "cuts": cuts,
        "blocks": [block.public_dict() for block in blocks],
        # SPEC-0009: workflow runs, newest first, and the gates they opened.
        "runs": sorted(state.workflows.values(), key=lambda run: run.get("created_at", ""), reverse=True),
        "gates": state.gates,
        # production-flow.md: fitting the storyboard, or producing what it defines.
        "phase": _phase(root, path, state),
        # SPEC-0003 / CT-0040: which variant of each cast member this scene
        # uses, how their voice sounds here, and any voice restated in full.
        "cast": _scene_field(document, "cast", scene_aliases) or {},
        "location": location_id,
        "voice_state": _scene_field(document, "voice_state", scene_aliases) or {},
        "voices": _scene_field(document, "voices", scene_aliases) or {},
        # How a generation model should refer to each speaker ("The man beside the bed").
        "refer_as": _scene_field(document, "refer_as", scene_aliases) or {},
        # CT-0048: beds under the whole scene, from the sound catalog.
        "ambience": sound_beds["ambience"],
        "music": sound_beds["music"],
        # How the scene is entered from the previous one in its sequence (SPEC-0007, CT-0051).
        "enter": enter,
        # The style in force (CT-0049): the scene's, else the production's.
        "style": style,
        # The same cut in other formats, delivered with every version (CT-0049).
        "deliver": renditions,
        # A surround mix beside the stereo, as a second track ("5.1", CT-0052).
        "surround": _surround(document.get("surround") if document.get("surround") is not None else project_surround),
        "findings": findings,
        "decision_log": list(reversed(state.decisions)),
        "pending_shots": pending_shots,
        "assemblies": [assembly.public_dict() for assembly in reversed(state.assemblies)],
        "approved_assembly": (
            state.approved_assembly().public_dict() if state.approved_assembly() else None
        ),
    }


def _scene_enter(document: dict[str, Any], scene_id: str, root: Path) -> tuple[dict[str, Any], list[Finding]]:
    """How the scene is entered from the one before it in its sequence (SPEC-0007, CT-0051).

    `enter: {type: hard, transition: {id: dip-to-black, duration_ms: 1000, reason: …}, reason: …}`.
    Declared on the incoming scene, as a shot's cut is.
    """

    from .cuts import CUT_TYPES

    raw = document.get("enter")
    if not isinstance(raw, dict) or not raw:
        return {}, []
    findings: list[Finding] = []
    cut_type = str(raw.get("type") or "hard").strip().lower()
    if cut_type not in CUT_TYPES:
        findings.append(Finding(code="cut_type_unknown", severity="error", scene_id=scene_id, shots=(),
                                message=f"{scene_id} is entered by a {cut_type!r} cut; the vocabulary is "
                                        f"{', '.join(CUT_TYPES)}."))
    transition = raw.get("transition") if isinstance(raw.get("transition"), dict) else {}
    if transition.get("id"):
        available = {item["id"] for item in list_transitions(root)}
        if transition["id"] not in available:
            findings.append(Finding(code="transition_unknown", severity="error", scene_id=scene_id, shots=(),
                                    message=f"{scene_id} is entered through the transition {transition['id']!r}, "
                                            "which is in no catalog. It would render as a cut."))
        elif not transition.get("reason"):
            findings.append(Finding(code="transition_reason_missing", severity="advice", scene_id=scene_id, shots=(),
                                    message=f"The transition into {scene_id} has no reason; a choice without a "
                                            "reason cannot be reviewed."))
    try:
        split = max(0.0, float(raw.get("split") or 0))
    except (TypeError, ValueError):
        split = 0.0
    enter = {"type": cut_type, "reason": str(raw.get("reason") or ""),
             "transition": {"id": str(transition["id"]), "duration_ms": transition.get("duration_ms"),
                            "reason": str(transition.get("reason") or "")} if transition.get("id") else None,
             **({"split": split} if split else {})}
    return enter, findings


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


def _check_plates(root: Path, location_id: str, shots: list[dict[str, Any]], scene_id: str) -> list[Finding]:
    """A picture made from a location's plate needs that plate: said before anyone pays for the edit."""

    from .locations import plate
    from .pictures import location_camera

    findings = []
    for shot in shots:
        camera = location_camera((shot.get("derive") or {}).get("from", ""), shot)
        if camera is None:
            continue
        if not location_id:
            message = f"{shot['id']} is made from its location's plate, but the scene is set in no location."
        elif not camera:
            message = f"{shot['id']} is made from the plate of its camera, but it has no camera."
        elif plate(root, location_id, camera) is None:
            message = (f"{shot['id']} is made from the plate of {camera} in {location_id}, which has none "
                       f"(references: {{path, kind: plate, camera: {camera}}} in its location.yaml).")
        else:
            continue
        findings.append(Finding(code="plate_missing", severity="warning", scene_id=scene_id, shots=(shot["id"],),
                                message=message))
    return findings


def _check_sizes(geometry, shots: list[dict[str, Any]], scene_id: str) -> list[Finding]:
    """A declared shot size that is not the scale's, or far from what the camera frames (one scale, CT-0049)."""

    from .board import SIZE_NAMES, canonical, framing

    plan = {"geometry": geometry.public_dict()}
    findings = []
    for shot in shots:
        declared = (shot.get("extra_fields") or {}).get("size") or shot.get("size")
        if not declared:
            continue
        name = canonical(declared)
        if name not in SIZE_NAMES:
            findings.append(Finding(code="shot_size_unknown", severity="warning", scene_id=scene_id, shots=(shot["id"],),
                                    message=f"{shot['id']} says its size is {declared!r}; the scale is "
                                            + ", ".join(SIZE_NAMES).lower() + "."))
            continue
        measured = framing(plan, shot)["size"]
        if measured and abs(SIZE_NAMES.index(measured) - SIZE_NAMES.index(name)) > 1:
            findings.append(Finding(code="shot_size_mismatch", severity="advice", scene_id=scene_id, shots=(shot["id"],),
                                    message=f"{shot['id']} is declared {name.lower()}, but its camera frames a "
                                            f"{measured.lower()} of its subject. Move the camera or change the lens, "
                                            "or the declaration."))
    return findings


def _check_hidden(geometry, shots: list[dict[str, Any]], scene_id: str) -> list[Finding]:
    """A camera following someone a set piece hides (CT-0025): the frame would show the piece."""

    from .blocking import hidden_targets

    if not geometry.set_pieces:
        return []
    plan = geometry.public_dict()
    labels = {piece.id: piece.label for piece in geometry.set_pieces.values()}
    findings = []
    for shot in shots:
        for moment, subject, piece in hidden_targets(plan, shot.get("motion") or {}):
            findings.append(Finding(
                code="subject_hidden", severity="warning", scene_id=scene_id, subjects=(subject,), shots=(shot["id"],),
                message=f"{shot['id']}: at its {moment}, the camera follows {subject}, but the {labels.get(piece, piece)} "
                        f"stands between them. Move the camera, the subject or the piece, or say the shot is on the {labels.get(piece, piece)}."))
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
        # A person is who they are. A production may also note where they sit
        # on screen (SINGULAR's `rotulo: esquerda`); that is not their name.
        name = _text(person.get("label")) or _text(person.get("nome")) or vtext(person, "label")
        subjects.append(
            {
                "id": person.get("id") or _identifier(name),
                "label": name,
                "position": [float(person["x"]), float(person["y"])],
                "eye_height": field(person, "eye_height"),
                "kind": field(person, "kind"),
                "width": field(person, "width"),
                "height": field(person, "height"),
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
                "target_height": field(camera, "target_height"),
            }
        )

    marks = [
        {
            "id": _text(mark.get("id")),
            "label": vtext(mark, "label") or _text(mark.get("id")),
            "position": [float(mark["x"]), float(mark["y"])],
        }
        for mark in field(geography, "marks") or []
        if isinstance(mark, dict) and "x" in mark
    ]

    set_pieces = [
        {
            "id": _text(piece.get("id")),
            "label": vtext(piece, "label") or _text(piece.get("id")),
            "position": [float(piece["x"]), float(piece["y"])],
            "width": field(piece, "width"), "depth": field(piece, "depth"), "height": field(piece, "height"),
            "rotation_deg": field(piece, "rotation") or 0,
        }
        for piece in field(geography, "set_pieces") or []
        if isinstance(piece, dict) and "x" in piece
    ]

    document: dict[str, Any] = {
        "units": "m",
        "subjects": subjects,
        "cameras": cameras,
        "marks": marks,
        "set_pieces": set_pieces,
    }
    if isinstance(room, (list, tuple)) and len(room) >= 2:
        document["room"] = {
            "width": float(room[0]),
            "depth": float(room[1]),
            "height": float(room[2]) if len(room) > 2 else 2.7,
            # Outdoors (a city, a road): ground only, no walls or ceiling.
            "exterior": bool(field(geography, "exterior")),
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


def _sequence_beds(raw: dict[str, Any], scene_ids: list[str],
                   root: Path) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """A sequence's `ambience` and `music`, placed over its scenes (`from`/`to`/`until` name scenes)."""

    beds: dict[str, list[dict[str, Any]]] = {"ambience": [], "music": []}
    if not any(raw.get(kind) for kind in beds):
        return beds, []
    from .sounds import expand, list_sounds

    catalog = {item["id"]: item for item in list_sounds(root)}
    problems: list[str] = []
    for kind in beds:
        beds[kind], found = expand(raw.get(kind), catalog, placed_on="scene", shots=tuple(scene_ids))
        problems.extend(f"The {kind} of sequence {raw.get('id')} {problem.replace('its shots', 'its scenes')}. "
                        "It would be lost, not guessed." for problem in found)
    return beds, problems


def _load_sequences(
    manifest: dict[str, Any],
    scenes: list[dict[str, Any]],
    path: Path,
) -> list[dict[str, Any]]:
    """Group scenes into the unit a director actually reviews."""

    raw_sequences = field(manifest, "sequences") or []
    if not isinstance(raw_sequences, list):
        raise ProjectFormatError(f"sequences must be a list in {path}")

    from .sequence_state import load as load_sequence_state

    sequence_versions = load_sequence_state(path.parent)["sequences"]
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

        beds, problems = _sequence_beds(raw, [scene["id"] for scene in members], path.parent)
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
                "versions": list(reversed(sequence_versions.get(sequence_id, {}).get("versions", []))),
                # CT-0051: sound over several scenes, from the sound catalog, and what is wrong with it.
                "ambience": beds["ambience"],
                "music": beds["music"],
                "problems": problems,
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


RENDERS_DIRECTORY = "renders"
STILLS_DIRECTORY = "stills"
RENDER_SUFFIXES = (".mp4", ".mov", ".webm")
STILL_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def discover_renders(root: Path) -> list[dict[str, Any]]:
    """Assembled files found in `renders/`, newest first.

    Nothing declares them, for the same reason nothing declares a take: a
    declaration is a second copy of a truth the filesystem already holds, and a
    second copy drifts. A render that exists is a render the interface shows.
    """

    directory = root / RENDERS_DIRECTORY
    if not directory.is_dir():
        return []
    found = []
    for path in directory.iterdir():
        if not path.is_file() or path.suffix.lower() not in RENDER_SUFFIXES:
            continue
        stat = path.stat()
        found.append(
            {
                "name": path.stem,
                "path": path.relative_to(root).as_posix(),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            }
        )
    return sorted(found, key=lambda item: item["modified_at"], reverse=True)


def discover_stills(root: Path, scene_id: str) -> dict[str, str]:
    """Frames drawn for a scene's shots, by shot id.

    A composed shot has no take, so without these a scene is text on a screen.
    """

    directory = root / STILLS_DIRECTORY / scene_id
    if not directory.is_dir():
        return {}
    stills: dict[str, str] = {}
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in STILL_SUFFIXES:
            stills[path.stem] = path.relative_to(root).as_posix()
    return stills


#: Scene fields a production may name in its own words (`scene_fields`).
SCENE_ALIAS_TARGETS = ("cast", "voice_state", "voices", "refer_as", "location")


def _scene_field_aliases(manifest: dict[str, Any]) -> dict[str, str]:
    """`scene_fields: {vozes: {maps_to: voices}}`, as for shots, for the few scene fields that allow it."""

    aliases: dict[str, str] = {}
    raw = manifest.get("scene_fields") or {}
    if isinstance(raw, dict):
        for name, value in raw.items():
            if isinstance(value, dict) and str(value.get("maps_to") or "") in SCENE_ALIAS_TARGETS:
                aliases[str(name)] = str(value["maps_to"])
    return aliases


def _scene_field(document: dict[str, Any], canonical: str, aliases: dict[str, str] | None) -> Any:
    value = document.get(canonical)
    if value is None:
        for alias, target in (aliases or {}).items():
            if target == canonical and document.get(alias) is not None:
                return document[alias]
    return value


def _shot_field_aliases(manifest: dict[str, Any]) -> dict[str, tuple[str, dict[str, str]]]:
    """Production fields that mean a core field: `shot_fields: {seg: {maps_to: duration}}`.

    The application's legacy map is frozen (vocabulary.py). A production whose
    own tools still write its dialect declares what those names mean, in its
    manifest, instead of the application learning another language. Only core
    shot fields can be targets.
    """

    aliases: dict[str, tuple[str, dict[str, str]]] = {}
    raw = manifest.get("shot_fields") or {}
    if isinstance(raw, dict):
        for name, value in raw.items():
            if isinstance(value, dict) and str(value.get("maps_to") or "") in CORE_SHOT_FIELDS:
                # `keys` renames the keys inside a mapping value, e.g. a trim
                # written {antes, depois} read as {before, after}.
                keys = value.get("keys") if isinstance(value.get("keys"), dict) else {}
                aliases[str(name)] = (str(value["maps_to"]), {str(k): str(v) for k, v in keys.items()})
    return aliases


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


_TITLE_KEY = re.compile(r"^[A-Za-z][A-Za-z ]*:")


def screenplay_files(manifest: dict[str, Any], root: Path) -> tuple[list[str], str]:
    """The screenplay's files in reading order, and what is wrong if none.

    ``paths.script`` may name one file, a directory whose ``.fountain`` files
    are read in name order (a feature split by act or arc), or an explicit
    list. Nothing is guessed: a declared path that does not exist, or several
    undeclared candidates, leave the production without a screenplay and say
    why, rather than quietly reading a draft or a work file.
    """

    paths = field(manifest, "paths") or {}
    declared = field(paths, "script")
    if isinstance(declared, list):
        files = [str(item) for item in declared]
        missing = [item for item in files if not (root / item).is_file()]
        if missing:
            return [], f"The declared screenplay files are missing: {', '.join(missing)}."
        return files, ""
    if declared:
        target = root / str(declared)
        if target.is_file():
            return [str(declared)], ""
        if target.is_dir():
            files = sorted(path for path in target.glob("*.fountain") if path.is_file())
            if files:
                return [path.relative_to(root).as_posix() for path in files], ""
            return [], f"The declared screenplay directory {declared} has no .fountain file."
        return [], f"The declared screenplay {declared} does not exist."
    candidates = sorted(path for path in root.glob("**/*.fountain") if path.is_file())
    if len(candidates) == 1:
        return [candidates[0].relative_to(root).as_posix()], ""
    if candidates:
        return [], (f"{len(candidates)} .fountain files and none declared: set paths.script to the "
                    f"screenplay (a file, a directory, or a list).")
    return [], ""


def _script_path(manifest: dict[str, Any], root: Path) -> str:
    """The screenplay as declared (a file or a directory), or the one file found."""

    files, _ = screenplay_files(manifest, root)
    if not files:
        return ""
    declared = field(field(manifest, "paths") or {}, "script")
    return str(declared) if declared and not isinstance(declared, list) else files[0]


def _strip_title_page(text: str) -> str:
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or not _TITLE_KEY.match(lines[0]):
        return text
    for index, line in enumerate(lines):
        if not line.strip():
            return "\n".join(lines[index + 1:])
    return ""


def screenplay_text(root: Path, files: list[str]) -> str:
    """The screenplay as one text: later parts lose their title page."""

    parts = []
    for index, name in enumerate(files):
        try:
            text = (root / name).read_text(encoding="utf-8")
        except OSError:
            continue
        parts.append(text if index == 0 else _strip_title_page(text))
    return "\n\n".join(part.strip("\n") for part in parts) + ("\n" if parts else "")


def _read_screenplay(root: Path, script_path: str | list[str]) -> script_model.Screenplay | None:
    """Parse the production's screenplay once; it is only ever read (ADR 0006)."""

    if not script_path:
        return None
    if isinstance(script_path, str):
        target = root / script_path
        files = ([p.relative_to(root).as_posix() for p in sorted(target.glob("*.fountain"))]
                 if target.is_dir() else [script_path])
    else:
        files = script_path
    text = screenplay_text(root, files)
    return script_model.parse(text) if text.strip() else None


def _link_screenplay(
    document: dict[str, Any],
    shots: list[dict[str, Any]],
    scene_id: str,
    screenplay: script_model.Screenplay | None,
) -> tuple[dict[str, Any] | None, list[Finding]]:
    """Resolve which screenplay scene this is and what each shot covers (SPEC-0006)."""

    declared = field(document, "script")
    if not declared:
        return None, []
    if isinstance(declared, str):
        declared = {"heading": declared}
    heading = vtext(declared, "heading")
    occurrence = int(declared.get("occurrence") or 1)
    findings: list[Finding] = []
    scene = screenplay.find_scene(heading, occurrence) if screenplay else None
    if scene is None:
        findings.append(
            Finding(
                code="script_scene_missing",
                severity="error",
                message=(
                    f"Scene {scene_id} is linked to screenplay heading {heading!r}"
                    + (f" (occurrence {occurrence})" if occurrence > 1 else "")
                    + (", which the screenplay does not contain." if screenplay else ", but the production has no screenplay.")
                ),
                scene_id=scene_id,
            )
        )
        return {"heading": heading, "occurrence": occurrence, "linked": False, "units": []}, findings

    covered_by: dict[int, list[str]] = {}
    for shot in shots:
        if not shot.get("covers"):
            continue
        coverage = script_model.shot_coverage(
            scene, shot["covers"], scene_id=scene_id, shot_id=shot["id"]
        )
        findings.extend(coverage.problems)
        speeches = [unit for unit in coverage.units if unit.kind == "speech"]
        dialogue, line_findings = script_model.compare_lines(
            shot["lines"], speeches, scene_id=scene_id, shot_id=shot["id"]
        )
        findings.extend(line_findings)
        shot["script"] = {
            "units": [unit.public_dict() for unit in coverage.units],
            "dialogue": dialogue,
            "action": [unit.text for unit in coverage.units if unit.kind == "action"],
        }
        for unit in coverage.units:
            covered_by.setdefault(unit.index, []).append(shot["id"])

    findings.extend(
        script_model.uncovered_dialogue(scene, set(covered_by), scene_id=scene_id)
    )
    units = []
    for unit in scene.units:
        entry = unit.public_dict()
        entry["shots"] = covered_by.get(unit.index, [])
        units.append(entry)
    return (
        {
            "heading": scene.heading,
            "occurrence": scene.occurrence,
            "number": scene.number,
            "linked": True,
            "units": units,
        },
        findings,
    )


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
    script_files, script_problem = screenplay_files(manifest, root)
    screenplay = _read_screenplay(root, script_files)
    scenes = [
        _load_scene(path, root, declared_fields, project_look, screenplay, _shot_field_aliases(manifest),
                    _scene_field_aliases(manifest), project_style=manifest.get("style"),
                    project_deliver=manifest.get("deliver"), project_surround=manifest.get("surround"))
        for path in scene_files(root, manifest)
    ]
    scenes.sort(key=lambda scene: (scene["order"], scene["id"]))
    scene_ids = [scene["id"] for scene in scenes]
    if len(scene_ids) != len(set(scene_ids)):
        raise ProjectFormatError("Scene ids must be unique")

    cast = load_cast(root, manifest)
    for scene_id, found in check_cast(scenes, cast).items():
        scene = next(item for item in scenes if item["id"] == scene_id)
        scene["findings"].extend(finding.public_dict() for finding in found)

    sequences = _load_sequences(manifest, scenes, manifest_path)
    for sequence in sequences:
        for scene_id in sequence["scene_ids"]:
            next(scene for scene in scenes if scene["id"] == scene_id)["sequence_id"] = sequence[
                "id"
            ]

    attention: list[dict[str, Any]] = []
    if script_problem:
        attention.append({"kind": "screenplay", "scene_id": "", "scene_title": "", "message": script_problem})
    for sequence in sequences:
        for problem in sequence.get("problems") or []:
            attention.append({"kind": "sound", "scene_id": "", "scene_title": sequence["label"], "message": problem})
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
        "style": manifest.get("style"),
        "deliver": manifest.get("deliver"),
        "renders": discover_renders(root),
        "script_path": _script_path(manifest, root),
        "script_files": script_files,
        "script_problem": script_problem,
        "cast": {key: {**member.public_dict(), "appearances": seen.get(key, [])}
                 for seen in [cast_appearances(scenes, cast)] for key, member in cast.items()},
        # SPEC-0010: each set declared once, with the scenes shot in it.
        "locations": _production_locations(root, scenes),
        # ADR 0016: a generated screenplay is read only in the editor.
        "script_generated_by": _text(manifest.get("screenplay_generated_by")),
        # Where a take's word timings are, beside it: `{stem}` is the take's
        # file name without its extension.
        "words_sidecar": _text(manifest.get("words_sidecar")) or "{stem}.words.json",
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


def writing_room(root: Path) -> dict[str, Any]:
    """Everything the writing side of the production needs, in one read.

    The interface has two halves. One asks "is this shot good?" and reads
    takes, geometry and decisions. This one asks "what is this scene?" and
    reads the screenplay, the frames, and who says what. They were never
    separable in the data; they are separable in attention, which is why they
    are separate rooms.
    """

    root = Path(root).expanduser().resolve()
    production = load_production(root)

    screenplay = screenplay_text(root, production["script_files"])

    scenes: list[dict[str, Any]] = []
    speakers: dict[str, dict[str, Any]] = {}
    for scene in production["scenes"]:
        frames = []
        lines = []
        for shot in scene["shots"]:
            frames.append(
                {
                    "shot_id": shot["id"],
                    "label": shot["label"],
                    "still": shot.get("still", ""),
                    "source": shot["source"],
                    "engine": shot["engine"],
                    "duration_seconds": shot["duration_seconds"],
                    "transition": shot.get("transition"),
                    "take_count": shot["take_count"],
                    # SPEC-0006: the screenplay this frame holds, in order.
                    "script": shot.get("script"),
                }
            )
            # A linked shot's words come from the screenplay; its authored
            # lines only add delivery, voice and mix. Unlinked shots keep theirs.
            spoken = (
                [
                    {
                        "who": line["who"],
                        "text": line["text"],
                        "extension": line.get("extension", ""),
                        "delivery": line.get("delivery", ""),
                        "voice": line.get("voice", ""),
                        "mix": line.get("mix", {}),
                        "en": line.get("en", ""),
                        "from_screenplay": True,
                    }
                    for line in shot["script"]["dialogue"]
                ]
                if shot.get("script")
                else shot["lines"]
            )
            for line in spoken:
                entry = {**line, "scene_id": scene["id"], "shot_id": shot["id"]}
                lines.append(entry)
                who = line["who"] or "UNATTRIBUTED"
                speaker = speakers.setdefault(who, {"who": who, "lines": 0, "scenes": set()})
                speaker["lines"] += 1
                speaker["scenes"].add(scene["id"])
        scenes.append(
            {
                "id": scene["id"],
                "title": scene["title"],
                "sequence": scene["sequence"],
                "summary": scene["summary"],
                "direction": scene["direction"],
                "look": scene["look"],
                "duration_seconds": scene["duration_seconds"],
                "frames": frames,
                "lines": lines,
                "script": scene.get("script"),
                "decisions": scene["decisions"],
                "open_questions": [
                    item for item in scene["decisions"] if not item.get("answer")
                ],
            }
        )

    cast = sorted(
        (
            {"who": item["who"], "lines": item["lines"], "scenes": sorted(item["scenes"])}
            for item in speakers.values()
        ),
        key=lambda item: (-item["lines"], item["who"]),
    )

    return {
        "id": production["id"],
        "title": production["title"],
        "logline": production["logline"],
        "script_path": production["script_path"],
        "script_files": production["script_files"],
        "screenplay": screenplay,
        "scenes": scenes,
        "cast": cast,
        "renders": production["renders"],
        "counts": {
            "scenes": len(scenes),
            "frames": sum(len(scene["frames"]) for scene in scenes),
            "stills": sum(1 for scene in scenes for f in scene["frames"] if f["still"]),
            "lines": sum(len(scene["lines"]) for scene in scenes),
            "speakers": len(cast),
            "open_questions": sum(len(scene["open_questions"]) for scene in scenes),
        },
    }
