"""Emotions: a catalog of how a feeling is described, asked of a model, and put on a face (CT-0048).

An entry (`emotion_assets/<id>/emotion.toml`) holds three things, in our own
words -- the references are cited by link, never copied:

- **describe**: the feeling, its family, and what shows -- face, body, voice;
- **ask**: how a video model is asked to act it, at three intensities
  (subtle, clear, overwhelming), as observable behaviour rather than a
  label -- a model renders "the jaw tightens and the eyes hold" better than
  "angry";
- **express**: FACS action units with a weight per intensity, and from
  them the ARKit blendshapes most rigs read (Unity, Blender, Unreal through
  Live Link), so the expression can drive a 3D face.

A shot names one or several:

    emotion: {id: dread, who: MARA, intensity: clear, arc: builds, reason: the reply is her own voice}

`arc` is how it moves over the shot: holds, builds, fades, breaks (arrives
suddenly). The generation prompt and the brief read it; a line the person
speaks without its own delivery takes the entry's voice. The catalog
offers vocabulary and mechanisms; how a character feels is the director's.

Catalogs layer: built in, `CINE_TOASTER_EMOTIONS_PATH`, the production's
`emotions/`.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from .errors import ValidationError

BUILTIN = Path(__file__).with_name("emotion_assets")
INTENSITIES = ("subtle", "clear", "overwhelming")
ARCS = ("holds", "builds", "fades", "breaks")
FAMILIES = ("joy", "sadness", "fear", "anger", "surprise", "disgust", "connection", "self", "thought")
PLACEMENT_KEYS = {"id", "who", "intensity", "arc", "reason"}

#: FACS action units as ARKit blendshapes (the 52 coefficients of Apple's face tracking, which Unity,
#: Blender add-ons and Unreal's Live Link read). Several AUs have no single shape; the nearest are listed.
AU_TO_ARKIT: dict[int, list[str]] = {
    1: ["browInnerUp"],
    2: ["browOuterUpLeft", "browOuterUpRight"],
    4: ["browDownLeft", "browDownRight"],
    5: ["eyeWideLeft", "eyeWideRight"],
    6: ["cheekSquintLeft", "cheekSquintRight"],
    7: ["eyeSquintLeft", "eyeSquintRight"],
    9: ["noseSneerLeft", "noseSneerRight"],
    10: ["mouthUpperUpLeft", "mouthUpperUpRight"],
    12: ["mouthSmileLeft", "mouthSmileRight"],
    14: ["mouthDimpleLeft", "mouthDimpleRight"],
    15: ["mouthFrownLeft", "mouthFrownRight"],
    16: ["mouthLowerDownLeft", "mouthLowerDownRight"],
    17: ["mouthShrugLower"],
    18: ["mouthPucker"],
    20: ["mouthStretchLeft", "mouthStretchRight"],
    22: ["mouthFunnel"],
    23: ["mouthPressLeft", "mouthPressRight"],
    24: ["mouthPressLeft", "mouthPressRight"],
    25: ["mouthClose"],  # lips part: mouthClose lowered; see below
    26: ["jawOpen"],
    27: ["jawOpen"],
    28: ["mouthRollLower", "mouthRollUpper"],
    43: ["eyeBlinkLeft", "eyeBlinkRight"],
    45: ["eyeBlinkLeft", "eyeBlinkRight"],
    61: ["eyeLookOutLeft", "eyeLookInRight"],
    62: ["eyeLookInLeft", "eyeLookOutRight"],
    63: ["eyeLookUpLeft", "eyeLookUpRight"],
    64: ["eyeLookDownLeft", "eyeLookDownRight"],
}
#: FACS names, for people reading an entry.
AU_NAMES = {
    1: "inner brow raiser", 2: "outer brow raiser", 4: "brow lowerer", 5: "upper lid raiser", 6: "cheek raiser",
    7: "lid tightener", 9: "nose wrinkler", 10: "upper lip raiser", 12: "lip corner puller", 14: "dimpler",
    15: "lip corner depressor", 16: "lower lip depressor", 17: "chin raiser", 18: "lip pucker",
    20: "lip stretcher", 22: "lip funneler", 23: "lip tightener", 24: "lip pressor", 25: "lips part",
    26: "jaw drop", 27: "mouth stretch", 28: "lip suck", 43: "eyes closed", 45: "blink", 51: "head turn left",
    52: "head turn right", 53: "head up", 54: "head down", 55: "head tilt left", 56: "head tilt right",
    61: "eyes turn left", 62: "eyes turn right", 63: "eyes up", 64: "eyes down",
}
#: How strong each intensity makes the action units, against the entry's own weights.
INTENSITY_SCALE = {"subtle": 0.35, "clear": 0.7, "overwhelming": 1.0}


def _roots(project_root: Path | None) -> list[tuple[str, Path]]:
    roots = [("built-in", BUILTIN)]
    for position, raw in enumerate(filter(None, os.environ.get("CINE_TOASTER_EMOTIONS_PATH", "").split(os.pathsep)), 1):
        roots.append((f"external-{position}", Path(raw).expanduser()))
    if project_root is not None:
        roots.append(("project", Path(project_root).expanduser().resolve() / "emotions"))
    return roots


def _load(path: Path, origin: str) -> dict[str, Any]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValidationError(f"Unreadable emotion {path}: {error}") from error
    signals = raw.get("signals") or {}
    ask = raw.get("ask") or {}
    voice = raw.get("voice") or {}
    return {
        "id": str(raw.get("id") or path.parent.name),
        "name": str(raw.get("name") or path.parent.name),
        "family": str(raw.get("family") or "thought"),
        "says": str(raw.get("says") or ""),
        "near": [str(item) for item in raw.get("near") or []],
        "signals": {part: [str(item) for item in signals.get(part) or []] for part in ("face", "body", "voice")},
        "ask": {level: str(ask.get(level) or "") for level in INTENSITIES},
        "voice": {level: str(voice.get(level) or "") for level in INTENSITIES},
        "facs": {int(key): float(value) for key, value in (raw.get("facs") or {}).items()},
        "references": [str(item) for item in raw.get("references") or []],
        "origin": origin,
        "directory": str(path.parent),
    }


def list_emotions(project_root: Path | None = None) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for origin, root in _roots(project_root):
        if root.is_dir():
            for manifest in sorted(root.glob("*/emotion.toml")):
                item = _load(manifest, origin)
                by_id[item["id"]] = item
    order = {name: index for index, name in enumerate(FAMILIES)}
    return sorted(by_id.values(), key=lambda item: (order.get(item["family"], 99), item["name"]))


def expand(raw: Any, catalog: dict[str, dict[str, Any]], *, people: set[str] | None = None,
           default_intensity: str = "clear") -> tuple[
        list[dict[str, Any]], list[str]]:
    """A shot's `emotion` with its entry's words: (emotions, problems).

    `raw` is an id, a mapping, or a list of them. `people` are the names the
    scene knows (cast and subjects, upper case); a `who` outside them is a
    problem only when they are given.
    """

    if raw in (None, "", [], {}):
        return [], []
    expanded, problems = [], []
    for entry in raw if isinstance(raw, list) else [raw]:
        declared = {"id": str(entry)} if isinstance(entry, str) else dict(entry or {})
        item = catalog.get(str(declared.get("id") or ""))
        if item is None:
            problems.append(f"names the emotion {declared.get('id')!r}, which is not in the emotion catalog")
            continue
        unknown = sorted(set(declared) - PLACEMENT_KEYS)
        # Unsaid, the intensity is the style's register (CT-0049), else clear.
        intensity = str(declared.get("intensity") or default_intensity).strip().lower()
        arc = str(declared.get("arc") or "holds").strip().lower()
        who = str(declared.get("who") or "").strip()
        if unknown:
            problems.append(f"gives {item['id']!r} {', '.join(unknown)}, which an emotion does not have")
        elif intensity not in INTENSITIES:
            problems.append(f"plays {item['id']!r} {intensity!r}; the intensities are {', '.join(INTENSITIES)}")
        elif arc not in ARCS:
            problems.append(f"moves {item['id']!r} as {arc!r}; the arcs are {', '.join(ARCS)}")
        elif people and who and who.upper() not in people:
            problems.append(f"gives {item['id']!r} to {who}, who is not in the scene")
        else:
            expanded.append({"id": item["id"], "name": item["name"], "who": who, "intensity": intensity, "arc": arc,
                             "reason": str(declared.get("reason") or ""), "ask": acting(item, intensity, arc),
                             "voice": item["voice"][intensity]})
    return expanded, problems


def _lower(text: str) -> str:
    text = " ".join(text.split()).rstrip(".")
    return text[0].lower() + text[1:] if text else text


def acting(item: dict[str, Any], intensity: str, arc: str) -> str:
    """The words a video model gets: observable behaviour at an intensity, moving as the arc says."""

    at = item["ask"][intensity] or item["ask"]["clear"]
    if arc == "builds":
        start = item["ask"]["subtle"] if intensity != "subtle" else ""
        return (f"at first only {_lower(start)}, growing until {_lower(at)}" if start
                else f"slowly, {_lower(at)}")
    if arc == "fades":
        return f"{_lower(at)}, then it eases away"
    if arc == "breaks":
        return f"suddenly, partway through, {_lower(at)}"
    return _lower(at)


def face(item: dict[str, Any], intensity: str = "clear") -> dict[str, Any]:
    """The expression on a 3D face: FACS action units and ARKit blendshape weights, 0 to 1."""

    if intensity not in INTENSITIES:
        raise ValidationError(f"The intensities are {', '.join(INTENSITIES)}")
    scale = INTENSITY_SCALE[intensity]
    units = {unit: round(min(1.0, weight * scale), 3) for unit, weight in sorted(item["facs"].items())}
    shapes: dict[str, float] = {}
    for unit, weight in units.items():
        for shape in AU_TO_ARKIT.get(unit, []):
            if unit == 25:  # lips part: the closed-mouth shape goes the other way
                continue
            shapes[shape] = max(shapes.get(shape, 0.0), weight)
    head = {AU_NAMES[unit]: weight for unit, weight in units.items() if 51 <= unit <= 56}
    return {"emotion": item["id"], "intensity": intensity,
            "action_units": [{"au": unit, "name": AU_NAMES.get(unit, ""), "weight": weight}
                             for unit, weight in units.items()],
            "arkit": dict(sorted(shapes.items())), "head": head}
