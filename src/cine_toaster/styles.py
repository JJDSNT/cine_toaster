"""Styles: a catalog of ways to make a film -- direction, animation technique, format (CT-0049).

Not only a director's manner: a movement (neorealism), an approach (slow
cinema), a genre (noir), an animation technique (stop-motion, cel, 3D
feature), or a format with its own rules (a vertical viral video, a
commercial spot, a music video, a trailer).

An entry (`style_assets/<id>/style.toml`) describes it in our own words, and says what it means for Cine Toaster's own
vocabularies:

- framing habits and lens, in words;
- camera moves it prefers and avoids (the camera-move catalog, CT-0027);
- editing: a shot-length range, cut types and transitions it prefers and
  avoids (SPEC-0007, the transition catalog);
- performance: the emotion intensity it defaults to and the most it allows
  (the emotion catalog, CT-0048);
- colour and light, sound and music, titles, in words;
- `format`, for formats: aspect ratio, a total length, a hook in the first
  seconds, burned-in captions, an end card; `frame_rate` for a technique
  that animates on twos or threes;
- `prompt`: what a video model is told about the image, in words of craft;
- `aka`: the names people know it by ("Ghibli", "Wes Anderson", "TikTok"),
  shown in the catalog and accepted by `style:`;
- `inspired_by`: films and filmmakers it comes from, with `references` as
  links. The prompt describes the traits in words of craft rather than
  naming them: a model follows described traits more reliably than a name,
  and no entry claims an endorsement.

A production names one (`style:` in `project.yaml`), a scene may name
another; the nearest wins, and the level that decided is reported, as for
looks. The prompt and the brief read it; a shot that departs from it is
told so as advice (`style_departure`), since a departure can be the point.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from .errors import ValidationError

BUILTIN = Path(__file__).with_name("style_assets")
KINDS = ("movement", "approach", "genre", "manner", "animation", "format")
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
    return sorted(by_id.values(), key=lambda item: (order.get(item["kind"], 99), item["name"]))


def lookup(catalog: dict[str, dict[str, Any]], name: str) -> dict[str, Any] | None:
    """A style by a name people know it by (`aka`), ignoring case: `style: Ghibli`."""

    wanted = name.strip().lower()
    return next((item for item in catalog.values()
                 if wanted in {alias.lower() for alias in item["aka"]} or wanted == item["name"].lower()), None)


def resolve(catalog: dict[str, dict[str, Any]], *, scene: str = "", project: str = "") -> tuple[
        dict[str, Any] | None, str, str]:
    """(the style in force, the level that decided it, a problem): the scene's, else the production's."""

    for level, value in (("scene", scene), ("project", project)):
        if value:
            item = catalog.get(value) or lookup(catalog, value)
            if item is None:
                return None, level, f"names the style {value!r}, which is not in the style catalog"
            return item, level, ""
    return None, "", ""


def summary(item: dict[str, Any], level: str) -> dict[str, Any]:
    """What a scene carries of its style: enough for the prompt, the brief and the checks."""

    return {"id": item["id"], "name": item["name"], "level": level, "says": item["says"], "prompt": item["prompt"],
            "framing": item["framing"], "camera": item["camera"], "editing": item["editing"],
            "performance": item["performance"], "colour": item["colour"], "sound": item["sound"],
            "kind": item["kind"], "format": item["format"]}


def departures(style: dict[str, Any], shots: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(shot id, what departs from the style) for each shot that does; advice, never a refusal."""

    found: list[tuple[str, str]] = []
    name = style["name"]
    low, high = (style["editing"]["shot_seconds"] or [0.0, 0.0])
    cap = INTENSITY_ORDER.index(style["performance"]["max"]) if style["performance"]["max"] in INTENSITY_ORDER else 2
    for shot in shots:
        move = (shot.get("move") or {}).get("id") if isinstance(shot.get("move"), dict) else None
        if move and move in style["camera"]["avoid"]:
            found.append((shot["id"], f"moves by {move}, which {name} avoids"))
        cut = (shot.get("cut") or {}).get("type") if isinstance(shot.get("cut"), dict) else None
        if cut and cut in style["editing"]["avoid_cuts"]:
            found.append((shot["id"], f"is entered by a {cut} cut, which {name} avoids"))
        transition = (shot.get("transition") or {}).get("id") if isinstance(shot.get("transition"), dict) else None
        if transition and transition in style["editing"]["avoid_transitions"]:
            found.append((shot["id"], f"is entered through {transition}, which {name} avoids"))
        seconds = float(shot.get("duration_seconds") or 0)
        if seconds and high and not low <= seconds <= high:
            found.append((shot["id"], f"runs {seconds:g} s; {name} holds a shot {low:g} to {high:g} s"))
        for feeling in shot.get("emotion") or []:
            if INTENSITY_ORDER.index(feeling["intensity"]) > cap:
                found.append((shot["id"], f"plays {feeling['id']} {feeling['intensity']}; {name} goes no further "
                                          f"than {style['performance']['max']}"))
    form = style.get("format") or {}
    if shots and form.get("hook_seconds"):
        first = float(shots[0].get("duration_seconds") or 0)
        if first > form["hook_seconds"] * 1.5:
            found.append((shots[0]["id"], f"opens for {first:g} s before anything changes; {name} hooks within "
                                          f"{form['hook_seconds']:g} s"))
    total = sum(float(shot.get("duration_seconds") or 0) for shot in shots if not shot.get("out_of_cut"))
    if form.get("total_seconds") and total:
        low, high = form["total_seconds"]
        if not low <= total <= high:
            found.append(("", f"runs {total:g} s; {name} runs {low:g} to {high:g} s"))
    return found
