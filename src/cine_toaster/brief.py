"""A scene's generation brief, derived from its records (CT-0022, plan step 4).

The brief is written in Auteur Script's shape -- a STAGING block for what holds
for the whole scene, then one EXECUTION state per shot -- but nothing in it is
authored as a brief. Every slot is taken from a record and says which:

- ``authored``: a field of the scene or shot file;
- ``screenplay``: the screenplay text the shot covers (SPEC-0006);
- ``derived``: computed from geometry, movement, or the cut record, so it
  cannot contradict `toast check`;
- ``missing``: a slot the brief needs and no record fills. The text names
  what to add.

The brief is provider-neutral. An adapter decides how much of it a model
receives. It is also exported as a SceneFlow project so the written intent can
be reviewed against a generated video.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .blocking import blocking_frame, public_frame

SOURCES = ("authored", "screenplay", "derived", "missing")

#: Shot size from the frame height at the subject's distance, in metres.
SHOT_SIZES = (
    (0.25, "ECU", "extreme close-up"),
    (0.45, "CU", "close-up"),
    (0.8, "MCU", "medium close-up"),
    (1.3, "MS", "medium shot"),
    (1.9, "MWS", "medium wide shot"),
    (4.0, "WS", "wide shot"),
    (math.inf, "EWS", "extreme wide shot"),
)
SENSOR_HEIGHT_MM = 36.0 * 9 / 16

CUT_NAMES = {"hard": "Hard cut", "match": "Match cut", "action": "Cut on action", "j": "J-cut",
             "l": "L-cut", "smash": "Smash cut", "jump": "Jump cut",
             "continuation": "Continuation of the previous shot (next generation, no visible cut)"}

#: SceneFlow's cue types, by the tag that produced the text.
_CUE_TYPES = {"CAM": "camera", "BLOCK": "shot", "ACT": "action", "DIAL": "dialogue",
              "AUDIO": "audio", "CUT IN": "transition", "ACTING": "action"}


@dataclass(slots=True)
class Slot:
    tag: str
    text: str
    source: str
    shot: str | None = None
    speaker: str | None = None

    def public_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "text": self.text, "source": self.source,
                "shot": self.shot, "speaker": self.speaker}


@dataclass(slots=True)
class Brief:
    scene: str
    staging: list[Slot] = field(default_factory=list)
    states: list[dict[str, Any]] = field(default_factory=list)

    def slots(self) -> list[Slot]:
        return self.staging + [slot for state in self.states for slot in state["slots"]]

    def missing(self) -> list[Slot]:
        return [slot for slot in self.slots() if slot.source == "missing"]

    def text(self) -> str:
        return render_text(self)[0]

    def public_dict(self) -> dict[str, Any]:
        text, _ = render_text(self)
        return {
            "scene": self.scene,
            "staging": [slot.public_dict() for slot in self.staging],
            "states": [
                {**{k: v for k, v in state.items() if k != "slots"},
                 "slots": [slot.public_dict() for slot in state["slots"]]}
                for state in self.states
            ],
            "missing": len(self.missing()),
            "text": text,
        }


def shot_size(frame_height_m: float) -> tuple[str, str]:
    for limit, code, name in SHOT_SIZES:
        if frame_height_m < limit:
            return code, name
    return SHOT_SIZES[-1][1:]


def _labels(scene: dict[str, Any]) -> dict[str, str]:
    return {item["id"]: item["label"] for item in (scene.get("geometry") or {}).get("subjects", [])}


def _framing(frame: dict[str, Any] | None) -> str:
    if not frame:
        return ""
    parts = []
    for figure in frame["figures"]:
        if figure["behind"]:
            continue
        if abs(figure["x"]) <= 1.0:
            where = "centre frame" if figure["side"] == "centred" else f"frame {figure['side']}"
        else:
            where = f"off {figure['side']}"
        parts.append(f"{figure['label']} {where}")
    return ", ".join(parts) or "nobody in frame"


def _camera_text(scene: dict[str, Any], shot: dict[str, Any], labels: dict[str, str]) -> str | None:
    motion = shot.get("motion") or {}
    pose = (motion.get("start") or {}).get("camera")
    if not pose:
        return None
    subject = pose.get("target_ref") or ""
    positions = (motion.get("start") or {}).get("subjects") or {}
    aim = positions.get(subject) or pose["target"]
    distance = math.dist(pose["position"], aim)
    frame_height = 2 * distance * (SENSOR_HEIGHT_MM / 2) / pose["lens_mm"]
    code, name = shot_size(frame_height)
    parts = [f"{code} ({name}), {pose['lens_mm']:g} mm"]
    if pose.get("height") is not None:
        parts.append(f"lens at {pose['height']:.2f} m")
    on = labels.get(subject, subject)
    parts.append(f"{distance:.1f} m from {on}" if on else f"aimed at a point {distance:.1f} m away")
    kind = motion.get("kind") or "static"
    if kind == "static":
        parts.append("locked off")
    else:
        move = kind.replace("_", " ")
        if motion.get("direction"):
            move += f" {motion['direction']}"
        detail = ", ".join(value for value in (motion.get("speed"), motion.get("rig")) if value)
        parts.append(f"{move}{f' ({detail})' if detail else ''}")
    return "; ".join(parts)


def _moves_text(scene: dict[str, Any], shot: dict[str, Any], labels: dict[str, str]) -> str:
    motion = shot.get("motion") or {}
    marks = {mark["id"]: mark for mark in (scene.get("geometry") or {}).get("marks", [])}
    moved = []
    for move in shot.get("subjects_move") or []:
        if not isinstance(move, dict):
            continue
        who = labels.get(move.get("subject", ""), move.get("subject", ""))
        mark = marks.get(move.get("to", ""))
        moved.append(f"{who} moves to {mark['label'] if mark and mark.get('label') else move.get('to')}")
    if not moved and motion.get("moved_subjects"):
        moved = [f"{labels.get(s, s)} moves" for s in motion["moved_subjects"]]
    return "; ".join(moved)


def _logic(scene: dict[str, Any], labels: dict[str, str]) -> Slot:
    geometry = scene.get("geometry") or {}
    sides: dict[str, set[str]] = {}
    for shot in scene.get("shots", []):
        for at in ("start", "end"):
            for item in ((shot.get("motion") or {}).get(at) or {}).get("framed", []):
                if item["side"] != "centred":
                    sides.setdefault(item["subject"], set()).add(item["side"])
    rules = []
    between = (geometry.get("axis") or {}).get("between") or []
    if len(between) == 2:
        rules.append(f"Line of action between {labels.get(between[0], between[0])} and "
                     f"{labels.get(between[1], between[1])}; every camera stays on one side of it.")
    for subject, seen in sorted(sides.items()):
        if len(seen) == 1:
            rules.append(f"{labels.get(subject, subject)} is always screen {next(iter(seen))}.")
    direction = " ".join((scene.get("direction") or "").split())
    if not rules and not direction:
        return Slot("LOGIC", "No geometry: add the scene's plan (subjects, cameras, axis) so "
                    "screen direction can be derived.", "missing")
    text = " ".join(rules + ([direction] if direction else []))
    return Slot("LOGIC", text, "derived" if rules else "authored")


def _aesthetic(scene: dict[str, Any], looks: dict[str, dict[str, Any]]) -> Slot:
    look = looks.get(scene.get("look") or "")
    if not look:
        return Slot("AESTHETIC", "No look: declare one in looks/ and name it on the scene "
                    "(palette, lighting, grain, lens character).", "missing")
    parts = [look.get("label") or look.get("id", "")]
    for name in ("palette", "lighting", "texture", "lens"):
        value = look.get(name)
        if isinstance(value, dict):
            value = ", ".join(f"{k} {v}" for k, v in value.items())
        if value:
            parts.append(f"{name}: {value}")
    return Slot("AESTHETIC", "; ".join(str(part) for part in parts if part), "authored")


def _voices(scene: dict[str, Any], cast: dict[str, dict[str, Any]]) -> Slot | None:
    """Each speaker's voice: who they sound like (the cast sheet), then how they sound here."""

    from .cast import cast_key

    speakers: list[str] = []
    for shot in scene.get("shots", []):
        for line in (shot.get("script") or {}).get("dialogue") or []:
            speakers.append(line["who"])
        if not shot.get("script"):
            speakers += [line.get("who", "") for line in shot.get("lines") or []]
    speakers = list(dict.fromkeys(name for name in speakers if name))
    if not speakers:
        return None
    by_name = {}
    for member in cast.values():
        for name in [member["id"], member["label"], *member.get("names", [])]:
            by_name.setdefault(cast_key(name), member)
    states = {cast_key(name): str(text) for name, text in (scene.get("voice_state") or {}).items()}
    parts, missing = [], []
    for speaker in speakers:
        member = by_name.get(cast_key(speaker))
        voice = ((member or {}).get("voice") or {}).get("described", "")
        state = states.get(cast_key(speaker)) or (states.get(member["id"]) if member else "")
        if not voice:
            missing.append(speaker)
            continue
        parts.append(f"{speaker}: {voice}" + (f"; here, {state}" if state else ""))
    if missing and not parts:
        return Slot("VOICES", f"No voice for {', '.join(missing)}: declare it on the cast sheet.", "missing")
    text = ". ".join(parts) + (f". No voice declared for {', '.join(missing)}." if missing else "")
    return Slot("VOICES", text, "authored")


def scene_brief(scene: dict[str, Any], looks: dict[str, dict[str, Any]] | None = None,
                cast: dict[str, dict[str, Any]] | None = None) -> Brief:
    """The brief for one loaded scene (`load_production`'s scene dict)."""

    labels = _labels(scene)
    brief = Brief(scene=scene["id"])
    summary = (scene.get("summary") or "").strip()
    brief.staging.append(
        Slot("INTENT", summary, "authored") if summary
        else Slot("INTENT", "No summary: say what the scene is for.", "missing")
    )
    brief.staging.append(_logic(scene, labels))
    brief.staging.append(_aesthetic(scene, looks or {}))
    style = scene.get("style")
    if style:
        lines = [f"{style['name']} ({style['level']}): {style['says']}"]
        if style["framing"]:
            lines.append("framing: " + "; ".join(style["framing"]))
        if style["camera"]["prefer"]:
            lines.append("moves: " + ", ".join(style["camera"]["prefer"]))
        seconds = style["editing"]["shot_seconds"]
        if seconds:
            lines.append(f"shots of {seconds[0]:g}-{seconds[1]:g} s")
        lines.append(f"performance: {style['performance']['intensity']}, at most {style['performance']['max']}")
        form = style.get("format") or {}
        if form.get("aspect"):
            lines.append(f"aspect {form['aspect']}")
        if form.get("hook_seconds"):
            lines.append(f"hook within {form['hook_seconds']:g} s")
        if form.get("captions"):
            lines.append("burned-in captions")
        brief.staging.append(Slot("STYLE", " · ".join(lines), "authored"))
    voices = _voices(scene, cast or {})
    if voices:
        brief.staging.append(voices)

    shots = scene.get("shots", [])
    cuts = {cut["to"]: cut for cut in scene.get("cuts") or []}
    first = shots[0] if shots else None
    opening = blocking_frame(scene, first, "start") if first else None
    if opening:
        camera = _camera_text(scene, first, labels)
        brief.staging.append(Slot("OPENING", f"{camera}. {_framing(public_frame(opening))}.", "derived"))
    else:
        brief.staging.append(Slot("OPENING", "No camera on the first shot: place it in the scene's "
                                  "geometry to derive the first frame.", "missing"))

    for number, shot in enumerate(shots, 1):
        slots: list[Slot] = []
        shot_id = shot["id"]
        cut = cuts.get(shot_id)
        if cut:
            text = CUT_NAMES.get(cut["type"], cut["type"])
            if cut.get("chain"):
                text += ", opening on the previous shot's last frame"
            transition = cut.get("transition") or {}
            if transition.get("id"):
                text += f", through {transition['id']}"
            reason = cut.get("reason") or transition.get("reason")
            if reason:
                text += f": {reason}"
            slots.append(Slot("CUT IN", text, "authored" if cut["type"] != "hard" or reason else "derived", shot_id))

        camera = _camera_text(scene, shot, labels)
        slots.append(Slot("CAM", camera, "derived", shot_id) if camera
                     else Slot("CAM", "No camera: name one from the scene geometry.", "missing", shot_id))

        start, end = blocking_frame(scene, shot, "start"), blocking_frame(scene, shot, "end")
        if start:
            block = f"Start: {_framing(public_frame(start))}."
            moves = _moves_text(scene, shot, labels)
            if moves:
                block += f" {moves}."
            end_text = _framing(public_frame(end)) if end else ""
            if end_text and end_text != _framing(public_frame(start)):
                block += f" End: {end_text}."
            slots.append(Slot("BLOCK", block, "derived", shot_id))

        description = (shot.get("description") or "").strip()
        script = shot.get("script") or {}
        actions = [unit["text"] for unit in script.get("units", []) if unit["kind"] == "action"]
        if description:
            slots.append(Slot("ACT", description, "authored", shot_id))
        if actions:
            slots.append(Slot("ACT", " ".join(actions), "screenplay", shot_id))
        if shot.get("avoid") or scene.get("avoid"):
            # What must not happen, kept apart from the directing words (docs/generation.md).
            slots.append(Slot("AVOID", "; ".join([*(scene.get("avoid") or []), *(shot.get("avoid") or [])]),
                              "authored", shot_id))
        for item in shot.get("emotion") or []:
            who = f"{item['who']}: " if item.get("who") else ""
            reason = f" ({item['reason']})" if item.get("reason") else ""
            slots.append(Slot("ACTING", f"{who}{item['name'].lower()}, {item['intensity']}, {item['arc']} -- "
                              f"{item['ask']}{reason}", "authored", shot_id, speaker=item.get("who") or None))
        if not description and not actions:
            slots.append(Slot("ACT", "No action: describe what happens, or link the screenplay "
                              "(`covers`).", "missing", shot_id))

        for line in script.get("dialogue") or []:
            speaker = line["who"] + (f" ({line['extension']})" if line.get("extension") else "")
            parentheticals = [part["text"] for part in line.get("parts", []) if part["kind"] == "parenthetical"]
            text = f"{speaker}: \"{line['text']}\""
            manner = "; ".join(parentheticals + ([line["delivery"]] if line.get("delivery") else []))
            if manner:
                text += f" -- {manner}"
            slots.append(Slot("DIAL", text, "screenplay", shot_id, speaker=line["who"]))
        if not script:
            for line in shot.get("lines") or []:
                text = f"{line.get('who', '')}: \"{line.get('text', '')}\""
                if line.get("delivery"):
                    text += f" -- {line['delivery']}"
                slots.append(Slot("DIAL", text, "authored", shot_id, speaker=line.get("who")))

        sound = shot.get("sound")
        if sound:
            slots.append(Slot("AUDIO", sound if isinstance(sound, str) else str(sound), "authored", shot_id))

        ends_on = (shot.get("ends_on") or "").strip()
        if ends_on:
            slots.append(Slot("STATE OUT", ends_on, "authored", shot_id))
        elif end:
            slots.append(Slot("STATE OUT", f"{_framing(public_frame(end))}.", "derived", shot_id))
        else:
            slots.append(Slot("STATE OUT", "No end state: add `ends_on`, or geometry to derive it.",
                              "missing", shot_id))

        brief.states.append({"n": number, "shot": shot_id, "label": shot.get("label") or "",
                             "duration_seconds": float(shot.get("duration_seconds") or 0.0),
                             "slots": slots})
    return brief


def render_text(brief: Brief) -> tuple[str, list[tuple[Slot, int, int]]]:
    """The brief as Auteur Script text, and where each slot's text sits in it."""

    out = ""
    spans: list[tuple[Slot, int, int]] = []

    def line(prefix: str, slot: Slot | None = None) -> None:
        nonlocal out
        if slot is None:
            out += prefix + "\n"
            return
        text = slot.text if slot.source != "missing" else f"<missing> {slot.text}"
        out += prefix
        spans.append((slot, len(out), len(out) + len(text)))
        out += text + "\n"

    line("[[STAGING]]")
    for slot in brief.staging:
        line(f"[[{slot.tag}]] ", slot)
    line("")
    line("[[EXECUTION]]")
    for index, state in enumerate(brief.states):
        heading = f"S{state['n']} · {state['shot']}"
        if state["label"]:
            heading += f" · {state['label']}"
        if state["duration_seconds"]:
            heading += f" · {state['duration_seconds']:g} s"
        line(heading)
        for slot in state["slots"]:
            line(f"[{slot.tag}] ", slot)
        if index < len(brief.states) - 1:
            line("->")
    return out, spans


def sceneflow_project(brief: Brief, video: str = "", shot: str | None = None) -> dict[str, Any]:
    """A SceneFlow-shaped review project: the brief as script, one cue per slot.

    ``video`` is a **local** file, relative to the production (a take's
    media). Cine Toaster's own review player reads it; SceneFlow itself plays
    only YouTube, so ``youtubeId`` stays empty and SceneFlow would need a
    local-video patch to open the file. With ``shot``, only that shot's cues
    are kept and they start at zero, because a take holds one shot. Times come
    from the planned durations until a review corrects them.
    """

    text, spans = render_text(brief)
    starts: dict[str, tuple[float, float]] = {}
    clock = 0.0
    for state in brief.states:
        duration = state["duration_seconds"] or 0.0
        if shot is not None:
            clock = 0.0
        starts[state["shot"]] = (clock, clock + duration)
        clock += duration
    cues = []
    for slot, start_index, end_index in spans:
        if slot.shot is None or slot.source == "missing" or slot.tag not in _CUE_TYPES:
            continue
        if shot is not None and slot.shot != shot:
            continue
        start_time, end_time = starts[slot.shot]
        cues.append(
            {
                "id": f"cue-{len(cues) + 1:03d}",
                "type": _CUE_TYPES[slot.tag],
                "selectedText": text[start_index:end_index],
                "startIndex": start_index,
                "endIndex": end_index,
                "startTime": round(start_time, 2),
                "endTime": round(end_time, 2),
                "speaker": slot.speaker,
            }
        )
    zero = {"before": 0, "after": 0}
    return {
        "youtubeId": "",
        "video": video,
        "shot": shot,
        "scriptText": text,
        "cues": cues,
        "settings": {
            "general": {"before": 1, "after": 1},
            "dialogue": {"before": 0.5, "after": 1},
            "action": {"before": -0.5, "after": -0.5},
            **{name: dict(zero) for name in ("camera", "shot", "audio", "vfx", "transition", "environment")},
        },
    }


def production_brief(root, scene_id: str, production: dict[str, Any] | None = None) -> tuple[dict[str, Any], Brief] | None:
    """Load a production (unless given) and derive one scene's brief, with its looks."""

    from .looks import load_looks
    from .project import load_production

    production = production if production is not None else load_production(root)
    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        return None
    looks = {name: look.public_dict() for name, look in load_looks(root).items()}
    return scene, scene_brief(scene, looks, production.get("cast") or {})


def take_review(scene: dict[str, Any], brief: Brief, shot_id: str, take_id: str | None = None) -> dict[str, Any] | None:
    """The review project for one shot's take: its local video and its cues.

    Without ``take_id`` the selected take is used, or the shot's first take.
    """

    shot = next((item for item in scene["shots"] if item["id"] == shot_id), None)
    if shot is None:
        return None
    takes = [take for take in shot.get("takes") or [] if take.get("media")]
    if take_id:
        take = next((item for item in takes if item["id"] == take_id), None)
    else:
        take = next((item for item in takes if item.get("selected")), None) or (takes[0] if takes else None)
    if take is None:
        return None
    return {**sceneflow_project(brief, video=take["media"], shot=shot_id), "take": take["id"]}

