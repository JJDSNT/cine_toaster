"""The continuity ledger: what holds from scene to scene (the Script Supervisor's first slice).

The geometry checks (`docs/continuity-checks.md`) read one scene: positions,
screen direction, eyelines. This ledger reads the film in order and carries
what a scene leaves behind into the next one: who wears what (the cast
variant, and any fact the author declares), what is carried, broken, open,
the time and the weather.

A scene declares it in its YAML::

    continuity:
      continues: true        # follows the previous scene with no gap in story time
      time: night
      weather: rain
      facts:                 # what holds here: subject -> attribute -> value
        KAEL: {jacket: none, carries: laptop}
        window: closed
      changes:               # a fact changing during the scene, from a shot on
        - at: P7
          KAEL: {carries: nothing}
      exceptions:            # a break the author accepts, and why
        - {subject: KAEL, attribute: variant, reason: the dream begins here}

Every fact keeps where it comes from (`declared` by the author, or `cast`: the
variant the scene names), and a finding says whether it is a break the author
declared impossible (`continues: true`) or a question the ledger only infers
(the same place, the next scene, nothing said). It reports; it never decides
what the film shows.
"""

from __future__ import annotations

from typing import Any

from .geometry import Finding

#: Attributes of the scene itself rather than of anyone in it.
SCENE = "SCENE"
SCENE_ATTRIBUTES = ("time", "weather")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).strip()


def parse(raw: Any, shot_ids: list[str]) -> dict[str, Any]:
    """A scene's `continuity:` block, normalised; what cannot be read becomes a problem, not an exception."""

    out: dict[str, Any] = {"continues": None, "time": "", "weather": "", "facts": {}, "changes": [],
                           "exceptions": [], "problems": []}
    if raw is None:
        return out
    if not isinstance(raw, dict):
        out["problems"].append("continuity must be a mapping (continues, time, weather, facts, changes, exceptions)")
        return out
    continues = raw.get("continues")
    if continues is not None:
        if isinstance(continues, bool):
            out["continues"] = continues
        else:
            out["problems"].append(f"continuity.continues must be true or false, not {continues!r}")
    for key in SCENE_ATTRIBUTES:
        out[key] = _text(raw.get(key))
    out["facts"] = _facts(raw.get("facts"), "continuity.facts", out["problems"])
    for position, item in enumerate(raw.get("changes") or []):
        if not isinstance(item, dict) or not item.get("at"):
            out["problems"].append(f"continuity.changes[{position}] needs `at: <shot>` and the facts that change")
            continue
        at = _text(item["at"])
        if at not in shot_ids:
            out["problems"].append(f"continuity.changes[{position}] is at {at}, which is not a shot of this scene")
            continue
        facts = _facts({key: value for key, value in item.items() if key != "at"},
                       f"continuity.changes[{position}]", out["problems"])
        if facts:
            out["changes"].append({"at": at, "facts": facts})
    for position, item in enumerate(raw.get("exceptions") or []):
        if not isinstance(item, dict) or not item.get("subject") or not item.get("attribute"):
            out["problems"].append(f"continuity.exceptions[{position}] needs subject, attribute and reason")
            continue
        out["exceptions"].append({"subject": _text(item["subject"]), "attribute": _text(item["attribute"]),
                                  "reason": _text(item.get("reason"))})
    return out


def _facts(raw: Any, where: str, problems: list[str]) -> dict[str, dict[str, str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        problems.append(f"{where} must map a subject to its facts")
        return {}
    facts: dict[str, dict[str, str]] = {}
    for subject, value in raw.items():
        if isinstance(value, dict):
            facts[_text(subject)] = {_text(key): _text(item) for key, item in value.items()}
        else:  # a prop or a set with one state: `window: closed`
            facts[_text(subject)] = {"state": _text(value)}
    return facts


def _subject(name: str, cast_names: dict[str, str]) -> str:
    """A cast member under the scene's own spelling of its id; anything else as written."""

    return cast_names.get(name.upper(), name)


def _declared(scene: dict[str, Any]) -> dict[tuple[str, str], tuple[str, str]]:
    """What the scene itself says at its start: (subject, attribute) -> (value, source)."""

    record = scene.get("continuity") or {}
    cast = scene.get("cast") or {}
    names = {name.upper(): name for name in cast}
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for name, variant in cast.items():
        if variant:
            out[(name, "variant")] = (str(variant), "cast")
    for key in SCENE_ATTRIBUTES:
        if record.get(key):
            out[(SCENE, key)] = (record[key], "declared")
    for subject, facts in (record.get("facts") or {}).items():
        for attribute, value in facts.items():
            out[(_subject(subject, names), attribute)] = (value, "declared")
    return out


def ledger(production: dict[str, Any]) -> dict[str, Any]:
    """The film read in order: per scene, what holds at its start, what it changes, and what breaks."""

    known: dict[tuple[str, str], dict[str, str]] = {}  # last known value, with where it was set
    rows: list[dict[str, Any]] = []
    findings: dict[str, list[Finding]] = {}
    previous: dict[str, Any] | None = None
    for scene in production["scenes"]:
        record = scene.get("continuity") or {}
        found = findings.setdefault(scene["id"], [])
        for problem in record.get("problems") or []:
            found.append(Finding(code="continuity_problem", severity="error", scene_id=scene["id"], message=problem))
        continues = record.get("continues")
        same_place = bool(previous and scene.get("location") and scene.get("location") == previous.get("location"))
        excepted = {(item["subject"].upper(), item["attribute"]): item["reason"]
                    for item in record.get("exceptions") or []}
        events = []
        for (subject, attribute), (value, source) in _declared(scene).items():
            before = known.get((subject, attribute))
            if subject == SCENE and before and before["scene"] != (previous or {}).get("id"):
                before = None  # the time of day is the previous scene's, never an older one's
            if before and before["value"] != value:
                event = {"subject": subject, "attribute": attribute, "from": before["value"], "to": value,
                         "since": before["scene"], "source": source}
                reason = excepted.get((subject.upper(), attribute))
                adjacent = previous is not None and before["scene"] == previous["id"]
                what = (f"{subject} {attribute}" if subject != SCENE else attribute)
                if reason is not None:
                    event["kind"] = "excepted"
                    event["reason"] = reason
                elif continues and adjacent:
                    event["kind"] = "break"
                    found.append(Finding(
                        code="continuity_break", severity="warning", scene_id=scene["id"],
                        subjects=(subject,) if subject != SCENE else (),
                        message=(f"{scene['id']} continues {previous['id']}, but {what} goes from "
                                 f"{before['value']!r} to {value!r}. Declare the change in {previous['id']} "
                                 f"(continuity.changes) or accept it (continuity.exceptions)."),
                    ))
                elif continues is None and adjacent and same_place:
                    event["kind"] = "unconfirmed"
                    found.append(Finding(
                        code="continuity_unconfirmed", severity="advice", scene_id=scene["id"],
                        subjects=(subject,) if subject != SCENE else (),
                        message=(f"{what} is {before['value']!r} in {previous['id']} and {value!r} here, in the "
                                 f"same place. Inferred, not declared: say whether {scene['id']} continues "
                                 f"{previous['id']} (continuity.continues: true or false)."),
                    ))
                else:
                    event["kind"] = "between_scenes"
                events.append(event)
            known[(subject, attribute)] = {"value": value, "scene": scene["id"], "source": source}
        at_start = _snapshot(known)
        for change in record.get("changes") or []:
            for subject, facts in change["facts"].items():
                for attribute, value in facts.items():
                    key = (_subject(subject, {name.upper(): name for name in scene.get("cast") or {}}), attribute)
                    before = known.get(key)
                    events.append({"subject": key[0], "attribute": attribute, "from": (before or {}).get("value", ""),
                                   "to": value, "at": change["at"], "kind": "declared_change", "source": "declared"})
                    known[key] = {"value": value, "scene": scene["id"], "shot": change["at"], "source": "declared"}
        rows.append({"id": scene["id"], "title": scene.get("title") or "", "location": scene.get("location") or "",
                     "continues": continues, "at_start": at_start, "events": events,
                     "changes": record.get("changes") or [], "exceptions": record.get("exceptions") or []})
        previous = scene
    return {"scenes": rows, "findings": {key: value for key, value in findings.items() if value}}


def _snapshot(known: dict[tuple[str, str], dict[str, str]]) -> dict[str, dict[str, dict[str, str]]]:
    out: dict[str, dict[str, dict[str, str]]] = {}
    for (subject, attribute), item in sorted(known.items()):
        out.setdefault(subject, {})[attribute] = dict(item)
    return out


def state_at(production: dict[str, Any], scene_id: str, shot_id: str = "") -> dict[str, dict[str, dict[str, str]]]:
    """What holds at a shot: the scene's start, then its declared changes up to and including that shot."""

    rows = {row["id"]: row for row in ledger(production)["scenes"]}
    row = rows.get(scene_id)
    if row is None:
        return {}
    scene = next(item for item in production["scenes"] if item["id"] == scene_id)
    order = [shot["id"] for shot in scene["shots"]]
    state = {subject: {key: dict(value) for key, value in facts.items()} for subject, facts in row["at_start"].items()}
    limit = order.index(shot_id) if shot_id in order else -1
    for event in row["events"]:
        if event["kind"] == "declared_change" and limit >= 0 and order.index(event["at"]) <= limit:
            state.setdefault(event["subject"], {})[event["attribute"]] = {
                "value": event["to"], "scene": scene_id, "shot": event["at"], "source": "declared"}
    return state


def describe(state: dict[str, dict[str, dict[str, str]]], scene_id: str) -> list[str]:
    """One line per subject, each fact with where it was set when that is another scene."""

    lines = []
    for subject, facts in state.items():
        parts = []
        for attribute, item in facts.items():
            origin = item["scene"] if item["scene"] != scene_id else ""
            where = ", ".join(filter(None, [origin, item.get("shot", ""), item["source"]]))
            parts.append(f"{attribute} {item['value']} ({where})")
        lines.append(f"{subject}: " + "; ".join(parts))
    return lines


def render_text(report: dict[str, Any]) -> str:
    lines = []
    for row in report["scenes"]:
        joined = {True: "continues the previous scene", False: "after a gap", None: "join not declared"}[row["continues"]]
        lines.append(f"{row['id']} {row['title']} -- {joined}{', at ' + row['location'] if row['location'] else ''}")
        for line in describe(row["at_start"], row["id"]):
            lines.append(f"    {line}")
        for event in row["events"]:
            what = f"{event['subject']} {event['attribute']}" if event["subject"] != SCENE else event["attribute"]
            if event["kind"] == "declared_change":
                lines.append(f"    at {event['at']}: {what} becomes {event['to']}")
            else:
                note = f" -- {event['reason']}" if event.get("reason") else ""
                kind = "changed since " + event["since"] if event["kind"] == "between_scenes" else event["kind"]
                lines.append(f"    {kind}: {what} {event['from']} -> {event['to']}{note}")
        for finding in report["findings"].get(row["id"], []):
            if finding.code == "continuity_problem":
                lines.append(f"    problem: {finding.message}")
    return "\n".join(lines)
