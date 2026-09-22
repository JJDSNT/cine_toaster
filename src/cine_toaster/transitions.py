from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any


BUILTIN_TRANSITIONS = Path(__file__).with_name("transition_assets")


class TransitionFormatError(ValueError):
    """Raised when a transition manifest cannot be used safely."""


def _roots(project_root: Path | None = None) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = [("built-in", BUILTIN_TRANSITIONS)]
    configured = os.environ.get("CINE_TOASTER_TRANSITIONS_PATH", "")
    for position, raw_path in enumerate(filter(None, configured.split(os.pathsep)), 1):
        roots.append((f"external-{position}", Path(raw_path).expanduser()))
    if project_root is not None:
        roots.append(("project", project_root.expanduser().resolve() / "transitions"))
    return roots


def _safe_asset(directory: Path, relative: str) -> Path:
    if not relative:
        raise TransitionFormatError(f"Empty asset path in {directory / 'transition.toml'}")
    try:
        candidate = (directory / relative).resolve()
        candidate.relative_to(directory.resolve())
    except (OSError, ValueError) as error:
        raise TransitionFormatError(f"Unsafe asset path {relative!r}") from error
    if not candidate.is_file():
        raise TransitionFormatError(f"Missing transition asset: {candidate}")
    return candidate


def _load_manifest(path: Path, origin: str) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise TransitionFormatError(f"Invalid TOML in {path}: {error}") from error

    required = ("id", "name", "kind", "description", "license")
    missing = [key for key in required if not document.get(key)]
    if missing:
        raise TransitionFormatError(f"Missing {', '.join(missing)} in {path}")

    transition_id = str(document["id"])
    kind = str(document["kind"])
    if kind not in {"glsl", "webm"}:
        raise TransitionFormatError(f"Unsupported transition kind {kind!r} in {path}")

    asset_name = str(document.get("asset", ""))
    asset_path = _safe_asset(path.parent, asset_name)
    preview_name = str(document.get("preview", ""))
    preview_path = _safe_asset(path.parent, preview_name) if preview_name else None

    return {
        "schema_version": int(document.get("schema_version", 1)),
        "id": transition_id,
        "name": str(document["name"]),
        "kind": kind,
        "category": str(document.get("category", "uncategorized")),
        "description": str(document["description"]),
        "guidance": str(document.get("guidance", "")),
        "energy": str(document.get("energy", "medium")),
        "motion": str(document.get("motion", "neutral")),
        "tags": list(document.get("tags", [])),
        "use_when": list(document.get("use_when", [])),
        "avoid_when": list(document.get("avoid_when", [])),
        "license": str(document["license"]),
        "author": str(document.get("author", "")),
        "source": str(document.get("source", "")),
        "duration_ms": int(document.get("duration_ms", 1000)),
        "webm_role": str(document.get("webm_role", "preview")),
        # How this item renders on each engine that can execute it,
        # declared by the item rather than inferred by a renderer.
        "render": dict(document.get("render", {})),
        "origin": origin,
        "asset": asset_name,
        "preview": preview_name or None,
        "asset_path": asset_path,
        "preview_path": preview_path,
    }


def list_transitions(project_root: Path | None = None) -> list[dict[str, Any]]:
    """Load built-in, external, and project transition catalogs.

    Later roots override earlier ones by id, so a project may deliberately pin
    or customize a shared transition without modifying the application.
    """

    by_id: dict[str, dict[str, Any]] = {}
    for origin, root in _roots(project_root):
        if not root.is_dir():
            continue
        for manifest in sorted(root.glob("*/transition.toml")):
            transition = _load_manifest(manifest, origin)
            by_id[transition["id"]] = transition
    return sorted(by_id.values(), key=lambda item: (item["category"], item["name"]))


def public_transition(transition: dict[str, Any]) -> dict[str, Any]:
    value = {key: item for key, item in transition.items() if not key.endswith("_path")}
    transition_id = transition["id"]
    value["asset_url"] = f"/transition-assets/{transition_id}/{transition['asset']}"
    if transition["preview"]:
        value["preview_url"] = f"/transition-assets/{transition_id}/{transition['preview']}"
    elif transition["kind"] == "webm":
        value["preview_url"] = value["asset_url"]
    else:
        value["preview_url"] = None
    return value


def transition_asset_path(
    transition_id: str,
    filename: str,
    project_root: Path | None = None,
) -> Path | None:
    for transition in list_transitions(project_root):
        if transition["id"] != transition_id:
            continue
        for key in ("asset_path", "preview_path"):
            path = transition.get(key)
            if path is not None and path.name == filename:
                return path
    return None
