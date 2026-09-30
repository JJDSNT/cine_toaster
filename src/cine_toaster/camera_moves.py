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

import math

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


# --- previews ---------------------------------------------------------------------

#: The stage every move is previewed on: one person, a column and a cabinet behind for parallax.
PREVIEW_STAGE = {
    "id": "preview",
    "geometry": {
        "room": {"width": 7.0, "depth": 6.0, "height": 3.0},
        "subjects": [{"id": "A", "label": "Subject", "position": [3.5, 3.2], "eye_height": 1.6, "kind": "person"}],
        "set_pieces": [
            {"id": "COLUMN", "label": "", "position": [2.1, 4.7], "width": 0.4, "depth": 0.4, "height": 3.0},
            {"id": "CABINET", "label": "", "position": [5.1, 5.1], "width": 1.2, "depth": 0.5, "height": 1.4},
        ],
        "marks": [],
    },
}
PREVIEW_SECONDS = 2.0
PREVIEW_FPS = 12


def _turn(point: tuple[float, float], pivot: tuple[float, float], degrees: float) -> list[float]:
    angle = math.radians(degrees)
    dx, dy = point[0] - pivot[0], point[1] - pivot[1]
    return [pivot[0] + dx * math.cos(angle) - dy * math.sin(angle), pivot[1] + dx * math.sin(angle) + dy * math.cos(angle)]


def preview_motion(move: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """The start and end of a move on the preview stage, and what the plan cannot show of it."""

    implies = move.get("implies") or {}
    kind, direction = implies.get("kind") or "", implies.get("direction") or ""
    subject = (3.5, 3.2)
    start = {"position": [3.5, 0.8], "target": list(subject), "target_ref": "", "lens_mm": 35.0, "height": 1.5,
             "aim_height": 1.6}
    end = dict(start)
    subjects_start, subjects_end = {"A": list(subject)}, {"A": list(subject)}
    note = ""
    sign = 1 if direction in ("in", "up", "left") else -1
    if kind == "dolly":
        end["position"] = [3.5, 0.8 + 1.2 * sign]
        if implies.get("rig") == "drone":
            start["height"] = end["height"] = 2.8
    elif kind == "zoom":
        start["lens_mm"], end["lens_mm"] = (28.0, 70.0) if sign > 0 else (70.0, 28.0)
    elif kind == "truck":
        end["position"] = [3.5 - 1.2 * sign, 0.8]  # screen left is -x from this camera
        end["target"] = [3.5 - 1.2 * sign, subject[1]]
    elif kind == "pan":
        degrees = 80.0 if implies.get("speed") == "snap" else 35.0
        end["target"] = _turn(subject, tuple(start["position"]), degrees * sign)
    elif kind == "tilt":
        end["aim_height"] = 1.6 + 1.1 * sign
    elif kind == "arc":
        end["position"] = _turn(tuple(start["position"]), subject, -60.0 * sign)
    elif kind == "pedestal":
        end["height"] = 1.5 + 0.8 * sign
        start["aim_height"], end["aim_height"] = start["height"], end["height"]  # a pedestal stays level
    elif kind == "crane":
        end["height"] = 1.5 + 1.4 * sign if sign > 0 else 0.6
    elif kind == "track":
        subjects_start["A"], subjects_end["A"] = [2.3, 3.2], [4.7, 3.2]
        start.update(position=[2.3, 0.8], target=[2.3, 3.2])
        end.update(position=[4.7, 0.8], target=[4.7, 3.2])
    else:
        note = (f"The plan cannot show a {implies.get('rig') or 'rig'}'s feel: the preview holds still."
                if kind != "static" else "")
    for secondary in implies.get("secondary") or []:
        if secondary.startswith("zoom") and kind == "dolly":
            # A dolly zoom: the lens follows the distance, so the subject keeps its size.
            end["lens_mm"] = round(start["lens_mm"] * math.dist(end["position"], subject)
                                   / math.dist(start["position"], subject), 1)
        elif secondary.startswith("zoom"):
            end["lens_mm"] = 20.0 if secondary.endswith("out") else 70.0
    motion = {"kind": kind or "static", "speed": implies.get("speed") or "",
              "start": {"camera": start, "subjects": subjects_start},
              "end": {"camera": end, "subjects": subjects_end}}
    return motion, note


def preview(move: dict[str, Any]) -> dict[str, Any]:
    """A move as a short animatic on the preview stage: blocking frames, derived, never stored."""

    from .blocking import blocking_frame, render_svg

    motion, note = preview_motion(move)
    shot = {"id": move["id"], "motion": motion}
    count = int(PREVIEW_SECONDS * PREVIEW_FPS) + 1
    frames = [render_svg(blocking_frame(PREVIEW_STAGE, shot, index / (count - 1))) for index in range(count)]
    return {"id": move["id"], "fps": PREVIEW_FPS, "frames": frames, "note": note}
