from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import ResourceNotFoundError, ValidationError
from .geometry import check_geometry, parse_geometry
from .state import SceneState, load_scene_state
from .takes import discover, shot_key, work_directory_for


PROJECT_FILE = "project.yaml"
SCENE_FILE = "decupagem.yaml"

DONE_STATUSES = {"approved", "complete", "completed", "selected", "aprovado"}
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

    paths = manifest.get("caminhos") or {}
    directory = root / _text(paths.get("cenas") or "cenas")
    if not directory.is_dir():
        return []

    wanted = _text((manifest.get("producao") or {}).get("variante"))
    by_scene: dict[str, tuple[int, Path]] = {}
    for path in sorted(directory.glob(f"*/**/{SCENE_FILE}")) + sorted(
        directory.glob(f"*/{SCENE_FILE}")
    ):
        document = _read_yaml(path)
        scene_id = _text(document.get("cena") or document.get("id"))
        if not scene_id:
            continue
        variant = _text(document.get("variante"))
        # A file matching the production variant wins; otherwise the plain one.
        rank = 2 if (wanted and variant == wanted) else (0 if variant else 1)
        current = by_scene.get(scene_id)
        if current is None or rank > current[0]:
            by_scene[scene_id] = (rank, path)
    return [path for _rank, path in sorted(by_scene.values(), key=lambda item: str(item[1]))]


def _load_shots(document: dict[str, Any], path: Path, root: Path) -> list[dict[str, Any]]:
    raw_shots = document.get("planos") or []
    if not isinstance(raw_shots, list):
        raise ProjectFormatError(f"planos must be a list in {path}")

    work = work_directory_for(path)
    shots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_shots:
        if not isinstance(raw, dict):
            raise ProjectFormatError(f"Each plano must be a mapping in {path}")
        number = raw.get("n")
        if number in (None, ""):
            raise ProjectFormatError(f"A plano is missing its number in {path}")
        shot_id = f"P{shot_key(number)}"
        if shot_id in seen:
            raise ProjectFormatError(f"Duplicate plano {number!r} in {path}")
        seen.add(shot_id)

        kind = _text(raw.get("tipo"))
        takes = (
            []
            if kind in {"preto", "branco", "cartela", "imagem"}
            else [take.public_dict() for take in discover(work, number, relative_to=root)]
        )
        shots.append(
            {
                "id": shot_id,
                "number": _text(number),
                "label": _text(raw.get("plano"))[:160] or shot_id,
                "kind": kind,
                "camera": _text(raw.get("camera_id") or raw.get("_camera")),
                "subject": _text(raw.get("sujeito")),
                "looks_at": _text(raw.get("olha_para")),
                "description": _text(raw.get("atuacao")),
                "duration_seconds": float(raw.get("dur") or 0),
                "authored_status": "",
                "authored_selected_take": "",
                "out_of_cut": bool(raw.get("fora_do_corte")),
                "takes": takes,
                "take_count": len(takes),
            }
        )
    return shots


def _camera_assignments(geography: dict[str, Any]) -> dict[str, str]:
    """Which camera covers which shot, read from the geography plan."""

    assignments: dict[str, str] = {}
    for camera in (geography or {}).get("cameras") or []:
        if not isinstance(camera, dict):
            continue
        camera_id = _text(camera.get("id"))
        if not camera_id:
            continue
        for number in str(camera.get("planos", "")).split():
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


def _load_scene(path: Path, root: Path) -> dict[str, Any]:
    document = _read_yaml(path)
    scene_id = _text(_require(document, "cena", path))

    geography = document.get("geografia") or {}
    shots = _load_shots(document, path, root)
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

    decisions = [
        {
            "question": _text(item.get("pergunta")),
            "status": _text(item.get("status") or "proposed"),
            "answer": _text(item.get("proposta") or item.get("resposta")),
        }
        for item in (document.get("decisoes") or [])
        if isinstance(item, dict)
    ]

    pending_shots = [shot["id"] for shot in shots if shot["status"] == "needs_review"]
    decided = sum(1 for shot in shots if shot["selected_take"])
    total_decidable = sum(1 for shot in shots if shot["take_count"])

    return {
        "id": scene_id,
        "order": int(document.get("ordem") or 0),
        "title": _text(document.get("titulo")) or scene_id,
        "sequence": _text(document.get("sequencia")),
        "sequence_id": "",
        "variant": _text(document.get("variante")),
        "status": "in_review" if pending_shots else ("selected" if decided else "not_started"),
        "current_step": _text(document.get("etapa") or "review"),
        "iteration": len(state.assemblies) or 1,
        "duration_seconds": sum(shot["duration_seconds"] for shot in shots),
        "summary": _text(document.get("situacao")),
        "direction": _text(document.get("direcao")),
        "updated_at": state.updated_at,
        "path": directory.relative_to(root).as_posix(),
        "file": path.relative_to(root).as_posix(),
        "progress": round(decided / total_decidable * 100) if total_decidable else 0,
        "revision": state.revision,
        "workflow": document.get("etapas") or [],
        "shots": shots,
        "decisions": decisions,
        "iterations": [],
        "blockers": document.get("impedimentos") or [],
        "geometry": geometry.public_dict(),
        "findings": findings,
        "decision_log": list(reversed(state.decisions)),
        "pending_shots": pending_shots,
        "assemblies": [assembly.public_dict() for assembly in reversed(state.assemblies)],
        "approved_assembly": (
            state.approved_assembly().public_dict() if state.approved_assembly() else None
        ),
    }


def _geometry_document(geography: dict[str, Any]) -> dict[str, Any] | None:
    """Translate the breakdown's plan into the Core's geometry vocabulary.

    The file speaks the production's language; the domain model speaks one of
    its own. This is the only place the two meet.
    """

    if not geography:
        return None

    room = geography.get("sala")
    subjects: list[dict[str, Any]] = []
    for person in geography.get("pessoas") or []:
        if not isinstance(person, dict) or "x" not in person:
            continue
        name = _text(person.get("nome"))
        subjects.append(
            {
                "id": person.get("id") or _identifier(name),
                "label": name,
                "position": [float(person["x"]), float(person["y"])],
                "eye_height": person.get("altura_olhos"),
            }
        )

    by_position = {
        (round(item["position"][0], 2), round(item["position"][1], 2)): item["id"]
        for item in subjects
    }
    cameras: list[dict[str, Any]] = []
    seen: set[str] = set()
    for camera in geography.get("cameras") or []:
        if not isinstance(camera, dict) or "x" not in camera:
            continue
        camera_id = _text(camera.get("id"))
        if not camera_id or camera_id in seen:
            continue
        seen.add(camera_id)
        aim = camera.get("mira")
        target: Any = aim
        if isinstance(aim, (list, tuple)) and len(aim) == 2:
            key = (round(float(aim[0]), 2), round(float(aim[1]), 2))
            target = by_position.get(key, [float(aim[0]), float(aim[1])])
        cameras.append(
            {
                "id": camera_id,
                "label": _text(camera.get("o")) or camera_id,
                "position": [float(camera["x"]), float(camera["y"])],
                "height": camera.get("altura"),
                "target": target,
                "lens_mm": camera.get("lente", 50),
            }
        )

    document: dict[str, Any] = {"units": "m", "subjects": subjects, "cameras": cameras}
    if isinstance(room, (list, tuple)) and len(room) >= 2:
        document["room"] = {
            "width": float(room[0]),
            "depth": float(room[1]),
            "height": float(room[2]) if len(room) > 2 else 2.7,
        }
    axis = geography.get("eixo")
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
        if _text(_read_yaml(path).get("cena")) == scene_id:
            return path.parent
    raise ResourceNotFoundError(f"Scene {scene_id!r} is not part of this production")


def _load_sequences(
    manifest: dict[str, Any],
    scenes: list[dict[str, Any]],
    path: Path,
) -> list[dict[str, Any]]:
    """Group scenes into the unit a director actually reviews."""

    raw_sequences = manifest.get("sequencias") or []
    if not isinstance(raw_sequences, list):
        raise ProjectFormatError(f"sequencias must be a list in {path}")

    by_id = {scene["id"]: scene for scene in scenes}
    claimed: set[str] = set()
    sequences: list[dict[str, Any]] = []
    for raw in raw_sequences:
        if not isinstance(raw, dict):
            raise ProjectFormatError(f"Each sequencia must be a mapping in {path}")
        sequence_id = _text(_require(raw, "id", path))
        members: list[dict[str, Any]] = []
        missing: list[str] = []
        for scene_id in raw.get("cenas") or []:
            scene = by_id.get(_text(scene_id))
            if scene is None:
                missing.append(_text(scene_id))
                continue
            members.append(scene)
            claimed.add(scene["id"])
        if missing:
            raise ProjectFormatError(
                f"sequencia {sequence_id!r} lists unknown scenes {', '.join(missing)} in {path}"
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
                "label": _text(raw.get("rotulo")) or sequence_id,
                "act": _text(raw.get("ato")),
                "status": _text(raw.get("status") or "in_progress"),
                "render": _text(raw.get("montagem")),
                "summary": _text(raw.get("resumo")),
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


def load_production(root: Path) -> dict[str, Any]:
    """Load the operational model of one production, straight from its files."""

    root = root.expanduser().resolve()
    manifest_path = root / PROJECT_FILE
    if not manifest_path.is_file():
        raise FileNotFoundError(f"No Cine Toaster project file: {manifest_path}")

    manifest = _read_yaml(manifest_path)
    project_id = _text(_require(manifest, "id", manifest_path))
    title = _text(_require(manifest, "titulo", manifest_path))

    scenes = [_load_scene(path, root) for path in scene_files(root, manifest)]
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

    production = manifest.get("producao") or {}
    active_scene_id = _text(production.get("cena_ativa"))
    active_scene = next((scene for scene in scenes if scene["id"] == active_scene_id), None)

    return {
        "schema_version": int(manifest.get("schema_version") or 1),
        "id": project_id,
        "title": title,
        "format": _text(manifest.get("formato")) or "Film",
        "logline": _text(manifest.get("logline")),
        "production": production,
        "phases": manifest.get("fases") or [],
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
