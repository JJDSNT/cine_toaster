"""Styles: three independent axes of how a film is made (CT-0049).

- **direction** -- a movement (neorealism), an approach (slow cinema), a
  genre (noir), a filmmaker's manner (symmetrical tableau, "Wes
  Anderson-like");
- **technique** -- how the image is made: live action by default, or an
  animation technique (stop-motion, hand-drawn 2D, 3D feature, pixel
  art...);
- **format** -- the communication format with its own rules (a viral
  vertical, a commercial spot, a music video, a trailer, an explainer).

They are not alternatives: a film can be stop-motion, Wes Anderson-like and
a viral vertical at once. Each axis is chosen on its own, and cascades on
its own -- the production's, unless a scene names another:

    style: {technique: stop-motion, direction: symmetrical-tableau, format: viral-vertical}
    style: noir                     # one name: its axis is the entry's
    style: [Ghibli, TikTok]         # several, at most one per axis
    style: {format: none}           # on a scene: no format here

An entry (`style_assets/<id>/style.toml`) describes it in our own words, and
says what it means for Cine Toaster's own vocabularies: framing and lens;
camera moves preferred and avoided (CT-0027); shot lengths, cuts and
transitions (SPEC-0007); the emotion register and ceiling (CT-0048); colour,
sound, titles; `format` rules (aspect, total length, hook, captions, end
card, frame rate); `prompt`, words of craft for a model; `aka`, the names
people know it by ("Ghibli", "TikTok"), shown and accepted by `style:`;
`inspired_by` and `references`, for people. The prompt describes traits
rather than naming them: a model follows described traits more reliably,
and no entry claims an endorsement.

Combined, each field has an owner: the **format** decides shot lengths,
hook, aspect and total length; the **technique** opens the prompt and sets
the frame rate; the **direction** sets the performance register; the
strictest ceiling of intensity holds; what any axis avoids is avoided, and
advice (`style_departure`, never a refusal) names the axis it comes from.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from .errors import ValidationError

BUILTIN = Path(__file__).with_name("style_assets")
KINDS = ("movement", "approach", "genre", "manner", "animation", "format")
#: The axis each kind of entry belongs to; the axes combine, the kinds within an axis do not.
AXES = ("technique", "direction", "format")
AXIS_OF = {"movement": "direction", "approach": "direction", "genre": "direction", "manner": "direction",
           "animation": "technique", "technique": "technique", "format": "format"}
INTENSITY_ORDER = ("subtle", "clear", "overwhelming")


def _roots(project_root: Path | None) -> list[tuple[str, Path]]:
    roots = [("built-in", BUILTIN)]
    for position, raw in enumerate(filter(None, os.environ.get("CINE_TOASTER_STYLES_PATH", "").split(os.pathsep)), 1):
        roots.append((f"external-{position}", Path(raw).expanduser()))
    if project_root is not None:
        roots.append(("project", Path(project_root).expanduser().resolve() / "styles"))
    return roots


def _words(raw: Any) -> list[str]:
    return [str(item) for item in raw or []]


def _load(path: Path, origin: str) -> dict[str, Any]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValidationError(f"Unreadable style {path}: {error}") from error
    camera = raw.get("camera") or {}
    editing = raw.get("editing") or {}
    performance = raw.get("performance") or {}
    seconds = editing.get("shot_seconds") or []
    form = raw.get("format") or {}
    total = form.get("total_seconds") or []
    return {
        "id": str(raw.get("id") or path.parent.name),
        "name": str(raw.get("name") or path.parent.name),
        "kind": str(raw.get("kind") or "approach"),
        "axis": AXIS_OF.get(str(raw.get("kind") or "approach"), "direction"),
        "says": str(raw.get("says") or ""),
        "aka": _words(raw.get("aka")),
        "inspired_by": _words(raw.get("inspired_by")),
        "framing": _words(raw.get("framing")),
        "camera": {"lens": str(camera.get("lens") or ""), "prefer": _words(camera.get("prefer")),
                   "avoid": _words(camera.get("avoid"))},
        "editing": {"shot_seconds": [float(value) for value in seconds[:2]] if len(seconds) >= 2 else [],
                    "prefer_cuts": _words(editing.get("prefer_cuts")), "avoid_cuts": _words(editing.get("avoid_cuts")),
                    "prefer_transitions": _words(editing.get("prefer_transitions")),
                    "avoid_transitions": _words(editing.get("avoid_transitions"))},
        "performance": {"intensity": str(performance.get("intensity") or "clear"),
                        "max": str(performance.get("max") or "overwhelming"),
                        "notes": str(performance.get("notes") or "")},
        "colour": str(raw.get("colour") or ""),
        "sound": str(raw.get("sound") or ""),
        "titles": _words(raw.get("titles")),
        "format": {"aspect": str(form.get("aspect") or ""),
                   "total_seconds": [float(value) for value in total[:2]] if len(total) >= 2 else [],
                   "hook_seconds": float(form.get("hook_seconds") or 0), "captions": bool(form.get("captions")),
                   "end_card": bool(form.get("end_card")), "frame_rate": float(form.get("frame_rate") or 0)},
        "prompt": str(raw.get("prompt") or ""),
        "use_when": _words(raw.get("use_when")),
        "avoid_when": _words(raw.get("avoid_when")),
        "references": _words(raw.get("references")),
        "origin": origin,
        "directory": str(path.parent),
    }


def list_styles(project_root: Path | None = None) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for origin, root in _roots(project_root):
        if root.is_dir():
            for manifest in sorted(root.glob("*/style.toml")):
                item = _load(manifest, origin)
                by_id[item["id"]] = item
    order = {name: index for index, name in enumerate(KINDS)}
    axes = {name: index for index, name in enumerate(AXES)}
    return sorted(by_id.values(), key=lambda item: (axes[item["axis"]], order.get(item["kind"], 99), item["name"]))


def lookup(catalog: dict[str, dict[str, Any]], name: str) -> dict[str, Any] | None:
    """A style by a name people know it by (`aka`), ignoring case: `style: Ghibli`."""

    wanted = name.strip().lower()
    return next((item for item in catalog.values()
                 if wanted in {alias.lower() for alias in item["aka"]} or wanted == item["name"].lower()), None)


def _declared(value: Any, catalog: dict[str, dict[str, Any]], level: str) -> tuple[
        dict[str, dict[str, Any] | None], list[str]]:
    """One level's `style:` as {axis: entry, or None for "none"}, and what is wrong with it."""

    chosen: dict[str, dict[str, Any] | None] = {}
    problems: list[str] = []
    if isinstance(value, dict):
        pairs = [(str(axis).strip().lower(), name) for axis, name in value.items()]
    elif isinstance(value, list):
        pairs = [("", name) for name in value]
    else:
        pairs = [("", value)]
    for axis, name in pairs:
        name = str(name or "").strip()
        if axis and axis not in AXES:
            problems.append(f"The {level} names a style axis {axis!r}; the axes are {', '.join(AXES)}")
            continue
        if not name:
            continue
        if name.lower() == "none":
            if axis:
                chosen[axis] = None
            continue
        item = catalog.get(name) or lookup(catalog, name)
        if item is None:
            problems.append(f"The {level} names the style {name!r}, which is not in the style catalog")
            continue
        if axis and item["axis"] != axis:
            problems.append(f"The {level} names {item['name']} as its {axis}, but it is a {item['axis']}")
            continue
        if chosen.get(item["axis"]):
            problems.append(f"The {level} names two {item['axis']}s, {chosen[item['axis']]['name']} and "
                            f"{item['name']}: an axis takes one")
            continue
        chosen[item["axis"]] = item
    return chosen, problems


def resolve(catalog: dict[str, dict[str, Any]], *, scene: Any = None, project: Any = None) -> tuple[
        list[tuple[dict[str, Any], str]], list[str]]:
    """The styles in force, one per axis, each with the level that decided it; and the problems.

    Each axis cascades on its own: the scene's, else the production's.
    """

    scene_parts, problems = _declared(scene, catalog, "scene") if scene else ({}, [])
    project_parts, more = _declared(project, catalog, "production") if project else ({}, [])
    parts = []
    for axis in AXES:
        if axis in scene_parts:
            if scene_parts[axis]:
                parts.append((scene_parts[axis], "scene"))
        elif project_parts.get(axis):
            parts.append((project_parts[axis], "project"))
    return parts, problems + more


def _first(parts: list[dict[str, Any]], axes: tuple[str, ...], test) -> dict[str, Any] | None:
    by_axis = {part["axis"]: part for part in parts}
    return next((by_axis[axis] for axis in axes if axis in by_axis and test(by_axis[axis])), None)


def summary(parts: list[tuple[dict[str, Any], str]]) -> dict[str, Any] | None:
    """The axes in force, combined into what the prompt, the brief and the checks read."""

    if not parts:
        return None
    items = [item for item, _ in parts]
    avoid_moves = {move: item["name"] for item in items for move in item["camera"]["avoid"]}
    avoid_cuts = {cut: item["name"] for item in items for cut in item["editing"]["avoid_cuts"]}
    avoid_transitions = {name: item["name"] for item in items for name in item["editing"]["avoid_transitions"]}

    def union(values):
        return list(dict.fromkeys(values))

    lengths = _first(items, ("format", "direction", "technique"), lambda item: item["editing"]["shot_seconds"])
    register = _first(items, ("direction", "format", "technique"), lambda item: True)
    ceiling = min(items, key=lambda item: INTENSITY_ORDER.index(item["performance"]["max"])
                  if item["performance"]["max"] in INTENSITY_ORDER else 2)
    form_owner = _first(items, ("format",), lambda item: True)
    rate_owner = _first(items, ("technique", "format"), lambda item: item["format"]["frame_rate"])
    form = dict((form_owner or {}).get("format") or {"aspect": "", "total_seconds": [], "hook_seconds": 0.0,
                                                     "captions": False, "end_card": False, "frame_rate": 0.0})
    form["frame_rate"] = rate_owner["format"]["frame_rate"] if rate_owner else 0.0
    lens = _first(items, ("direction", "format", "technique"), lambda item: item["camera"]["lens"])
    return {
        "name": " + ".join(item["name"] for item in items),
        "level": ", ".join(f"{item['axis']} from the {'scene' if level == 'scene' else 'production'}"
                           for item, level in parts),
        "parts": [{"axis": item["axis"], "id": item["id"], "name": item["name"], "level": level, "says": item["says"]}
                  for item, level in parts],
        "says": " ".join(item["says"] for item in items),
        "prompt": "; ".join(item["prompt"] for item in items if item["prompt"]),
        "framing": union(habit for item in items for habit in item["framing"]),
        "camera": {"lens": lens["camera"]["lens"] if lens else "",
                   "prefer": [move for move in union(m for item in items for m in item["camera"]["prefer"])
                              if move not in avoid_moves],
                   "avoid": list(avoid_moves), "avoided_by": avoid_moves},
        "editing": {"shot_seconds": lengths["editing"]["shot_seconds"] if lengths else [],
                    "shot_seconds_by": lengths["name"] if lengths else "",
                    "prefer_cuts": [cut for cut in union(c for item in items for c in item["editing"]["prefer_cuts"])
                                    if cut not in avoid_cuts],
                    "avoid_cuts": list(avoid_cuts), "avoided_cuts_by": avoid_cuts,
                    "prefer_transitions": [name for name in union(t for item in items
                                                                  for t in item["editing"]["prefer_transitions"])
                                           if name not in avoid_transitions],
                    "avoid_transitions": list(avoid_transitions), "avoided_transitions_by": avoid_transitions},
        "performance": {"intensity": register["performance"]["intensity"], "max": ceiling["performance"]["max"],
                        "max_by": ceiling["name"], "notes": register["performance"]["notes"]},
        "colour": "; ".join(item["colour"] for item in items if item["colour"]),
        "sound": "; ".join(item["sound"] for item in items if item["sound"]),
        "format": form, "format_by": form_owner["name"] if form_owner else "",
    }


def departures(style: dict[str, Any], shots: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(shot id, what departs from the style, and from which axis) for each shot that does; advice, never a refusal."""

    found: list[tuple[str, str]] = []
    camera, editing, performance = style["camera"], style["editing"], style["performance"]
    low, high = editing["shot_seconds"] or [0.0, 0.0]
    cap = INTENSITY_ORDER.index(performance["max"]) if performance["max"] in INTENSITY_ORDER else 2
    for shot in shots:
        move = (shot.get("move") or {}).get("id") if isinstance(shot.get("move"), dict) else None
        if move and move in camera["avoided_by"]:
            found.append((shot["id"], f"moves by {move}, which {camera['avoided_by'][move]} avoids"))
        cut = (shot.get("cut") or {}).get("type") if isinstance(shot.get("cut"), dict) else None
        if cut and cut in editing["avoided_cuts_by"]:
            found.append((shot["id"], f"is entered by a {cut} cut, which {editing['avoided_cuts_by'][cut]} avoids"))
        transition = (shot.get("transition") or {}).get("id") if isinstance(shot.get("transition"), dict) else None
        if transition and transition in editing["avoided_transitions_by"]:
            found.append((shot["id"], f"is entered through {transition}, which "
                                      f"{editing['avoided_transitions_by'][transition]} avoids"))
        seconds = float(shot.get("duration_seconds") or 0)
        if seconds and high and not low <= seconds <= high:
            found.append((shot["id"], f"runs {seconds:g} s; {editing['shot_seconds_by']} holds a shot "
                                      f"{low:g} to {high:g} s"))
        for feeling in shot.get("emotion") or []:
            if INTENSITY_ORDER.index(feeling["intensity"]) > cap:
                found.append((shot["id"], f"plays {feeling['id']} {feeling['intensity']}; {performance['max_by']} "
                                          f"goes no further than {performance['max']}"))
    form, owner = style.get("format") or {}, style.get("format_by") or ""
    if shots and form.get("hook_seconds"):
        first = float(shots[0].get("duration_seconds") or 0)
        if first > form["hook_seconds"] * 1.5:
            found.append((shots[0]["id"], f"opens for {first:g} s before anything changes; {owner} hooks within "
                                          f"{form['hook_seconds']:g} s"))
    from .formats import end_card_missing

    if end_card_missing(style, shots):
        kept = [shot for shot in shots if not shot.get("out_of_cut")]
        found.append((kept[-1]["id"], f"ends the scene, but {owner} ends on an end card: a title card shot "
                                      "(`title:` with no take) with the brand or the title"))
    total = sum(float(shot.get("duration_seconds") or 0) for shot in shots if not shot.get("out_of_cut"))
    if form.get("total_seconds") and total:
        low, high = form["total_seconds"]
        if not low <= total <= high:
            found.append(("", f"runs {total:g} s; {owner} runs {low:g} to {high:g} s"))
    return found
