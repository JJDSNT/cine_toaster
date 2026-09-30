"""The camera-move catalog (CT-0027), shaped like the transition catalog.

A move has editorial guidance (what it says, when to use it, when to avoid
it), the geometry it implies under SPEC-0005 -- so `toast check` can compare
a declared move with the one the shot's poses derive -- and the words a video
model is given for it. Catalogs layer: built in, external paths
(`CINE_TOASTER_CAMERA_MOVES_PATH`), then the production's `camera_moves/`;
a later layer replaces an earlier move with the same id.

The built-in moves are written here. aicameramovements.com's taxonomy was used
only as a checklist of names: it states no licence, so none of its text is used.

A shot names a move with `move: {id: push-in}`. Its kind, direction and rig
come from the catalog unless the shot says otherwise.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from .errors import ValidationError

BUILTIN = Path(__file__).with_name("camera_move_assets")
CATEGORIES = ("static", "pan/tilt", "zoom/lens", "dolly/track", "physical", "drone/crane", "human", "specials")


def _roots(project_root: Path | None) -> list[tuple[str, Path]]:
    roots = [("built-in", BUILTIN)]
    for position, raw in enumerate(filter(None, os.environ.get("CINE_TOASTER_CAMERA_MOVES_PATH", "").split(os.pathsep)), 1):
        roots.append((f"external-{position}", Path(raw).expanduser()))
    if project_root is not None:
        roots.append(("project", Path(project_root).expanduser().resolve() / "camera_moves"))
    return roots


def _load(path: Path, origin: str) -> dict[str, Any]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValidationError(f"Unreadable camera move {path}: {error}") from error
    implies = raw.get("implies") or {}
    return {
        "id": str(raw.get("id") or path.parent.name),
        "name": str(raw.get("name") or path.parent.name),
        "category": str(raw.get("category") or "specials"),
        "says": str(raw.get("says") or ""),
        "energy": str(raw.get("energy") or ""),
        "use_when": [str(item) for item in raw.get("use_when") or []],
        "avoid_when": [str(item) for item in raw.get("avoid_when") or []],
        "implies": {"kind": str(implies.get("kind") or ""), "direction": str(implies.get("direction") or ""),
                    "rig": str(implies.get("rig") or ""), "speed": str(implies.get("speed") or ""),
                    "secondary": [str(item) for item in implies.get("secondary") or []]},
        "prompt": str((raw.get("prompt") or {}).get("text") or ""),
        "origin": origin,
    }


def list_moves(project_root: Path | None = None) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for origin, root in _roots(project_root):
        if root.is_dir():
            for manifest in sorted(root.glob("*/move.toml")):
                move = _load(manifest, origin)
                by_id[move["id"]] = move
    order = {name: index for index, name in enumerate(CATEGORIES)}
    return sorted(by_id.values(), key=lambda move: (order.get(move["category"], 99), move["name"]))


def expand(move: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], str]:
    """A shot's `move` with its catalog id filled in: (move, problem)."""

    move_id = str(move.get("id") or "").strip()
    if not move_id:
        return move, ""
    found = catalog.get(move_id)
    if found is None:
        return move, f"names the camera move {move_id!r}, which is not in the catalog"
    implies = found["implies"]
    kind = "_".join(filter(None, [implies["kind"], implies["direction"]]))
    filled = dict(move)
    if kind and not move.get("kind"):
        filled["kind"] = kind
    for key in ("rig", "speed"):
        if implies[key] and not move.get(key):
            filled[key] = implies[key]
    filled["name"] = found["name"]
    filled["prompt"] = found["prompt"]
    return filled, ""
