from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


DONE_STATUSES = {"approved", "complete", "completed", "selected"}
ATTENTION_STATUSES = {"blocked", "needs_review", "in_review", "failed"}


class ProjectFormatError(ValueError):
    """Raised when a Cine Toaster project manifest is invalid."""


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ProjectFormatError(f"Invalid TOML in {path}: {error}") from error


def _require(document: dict[str, Any], key: str, path: Path) -> Any:
    value = document.get(key)
    if value in (None, ""):
        raise ProjectFormatError(f"Missing {key!r} in {path}")
    return value


def _load_scene(path: Path, root: Path) -> dict[str, Any]:
    document = _read_toml(path)
    workflow = document.get("workflow", [])
    shots = document.get("shots", [])
    decisions = document.get("decisions", [])
    iterations = document.get("iterations", [])
    if not isinstance(workflow, list) or not isinstance(shots, list):
        raise ProjectFormatError(f"workflow and shots must be arrays in {path}")

    completed = sum(
        1 for step in workflow if str(step.get("status", "")).lower() in DONE_STATUSES
    )
    progress = round((completed / len(workflow)) * 100) if workflow else 0
    status = str(document.get("status", "not_started"))
    blockers = document.get("blockers", [])

    return {
        "id": str(_require(document, "id", path)),
        "order": int(document.get("order", 0)),
        "title": str(_require(document, "title", path)),
        "sequence": str(document.get("sequence", "")),
        "status": status,
        "current_step": str(document.get("current_step", "script")),
        "iteration": int(document.get("iteration", 1)),
        "duration_seconds": int(document.get("duration_seconds", 0)),
        "summary": str(document.get("summary", "")),
        "updated_at": str(document.get("updated_at", "")),
        "path": path.parent.relative_to(root).as_posix(),
        "progress": progress,
        "workflow": workflow,
        "shots": shots,
        "decisions": decisions if isinstance(decisions, list) else [],
        "iterations": iterations if isinstance(iterations, list) else [],
        "blockers": blockers if isinstance(blockers, list) else [],
    }


def load_production(root: Path) -> dict[str, Any]:
    """Load the small, human-readable operational model for a project."""

    root = root.expanduser().resolve()
    manifest_path = root / "project.toml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"No Cine Toaster project manifest: {manifest_path}")

    manifest = _read_toml(manifest_path)
    project_id = str(_require(manifest, "id", manifest_path))
    title = str(_require(manifest, "title", manifest_path))
    paths = manifest.get("paths", {})
    scenes_directory = root / str(paths.get("scenes", "scenes"))

    scenes: list[dict[str, Any]] = []
    if scenes_directory.is_dir():
        for scene_path in sorted(scenes_directory.glob("*/scene.toml")):
            scenes.append(_load_scene(scene_path, root))
    scenes.sort(key=lambda scene: (scene["order"], scene["id"]))

    scene_ids = [scene["id"] for scene in scenes]
    if len(scene_ids) != len(set(scene_ids)):
        raise ProjectFormatError("Scene ids must be unique")

    approved = sum(scene["status"] in DONE_STATUSES for scene in scenes)
    in_progress = sum(
        scene["status"] not in DONE_STATUSES | {"not_started"} for scene in scenes
    )
    attention: list[dict[str, Any]] = []
    for scene in scenes:
        if scene["blockers"]:
            for blocker in scene["blockers"]:
                attention.append(
                    {
                        "kind": "blocker",
                        "scene_id": scene["id"],
                        "scene_title": scene["title"],
                        "message": str(blocker),
                    }
                )
        elif scene["status"] in ATTENTION_STATUSES:
            attention.append(
                {
                    "kind": "review" if "review" in scene["status"] else scene["status"],
                    "scene_id": scene["id"],
                    "scene_title": scene["title"],
                    "message": f"{scene['current_step'].replace('_', ' ').title()} needs attention",
                }
            )

    production = manifest.get("production", {})
    active_scene_id = str(production.get("active_scene", ""))
    active_scene = next((scene for scene in scenes if scene["id"] == active_scene_id), None)
    phases = manifest.get("phases", [])

    return {
        "schema_version": int(manifest.get("schema_version", 1)),
        "id": project_id,
        "title": title,
        "format": str(manifest.get("format", "Film")),
        "logline": str(manifest.get("logline", "")),
        "production": production,
        "phases": phases if isinstance(phases, list) else [],
        "scenes": scenes,
        "active_scene": active_scene,
        "attention": attention,
        "metrics": {
            "total_scenes": len(scenes),
            "approved_scenes": approved,
            "in_progress_scenes": in_progress,
            "attention_items": len(attention),
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
