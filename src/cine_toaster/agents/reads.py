"""What the assistant can look up by itself: reads, never changes (ADR 0017).

The overview goes with every turn, so the assistant always knows the film as a
whole. The reads are asked for by the model when a question needs more; each
returns short text, bounded, from the runtime's own API.
"""

from __future__ import annotations

from collections.abc import Callable
import json
from typing import Any

from ..production_context import WORK_POLICY, work_structure
from .runtime_client import RuntimeClient

LIMIT = 3500


def _cut(text: str) -> str:
    return text if len(text) <= LIMIT else text[:LIMIT] + "\n… (cut short)"


def overview(production: dict[str, Any], budget: dict[str, Any] | None = None) -> str:
    """The whole film in a few lines: every scene, what waits for the director, the money."""

    lines = [f"Film: {production.get('title', '')}" + (f" — {production['logline']}" if production.get("logline") else "")]
    by_id = {scene["id"]: scene for scene in production["scenes"]}
    placed: set[str] = set()
    for sequence in production.get("sequences") or []:
        ids = [scene_id for scene_id in sequence.get("scene_ids") or [] if scene_id in by_id]
        if ids:
            lines.append(f"Sequence {sequence.get('label') or sequence['id']}: {', '.join(ids)}")
            placed.update(ids)
    for scene in production["scenes"]:
        shots = scene["shots"]
        chosen = sum(1 for shot in shots if shot.get("selected_take"))
        waiting = [gate for gate in (scene.get("gates") or {}).values() if gate.get("state") == "waiting"]
        active = [run for run in scene.get("runs") or [] if run.get("state") in ("running", "waiting")]
        stage = "production" if (scene.get("phase") or {}).get("phase") == "production" else "fitting the storyboard"
        parts = [f"{len(shots)} shots, {chosen} with a chosen take", f"status {scene.get('status') or '—'}", stage]
        if scene.get("findings"):
            parts.append(f"{len(scene['findings'])} finding(s)")
        if waiting:
            parts.append(f"{len(waiting)} gate(s) waiting ({', '.join(gate['subject'] for gate in waiting)})")
        if active:
            parts.append(f"{len(active)} workflow run(s) active")
        if scene.get("approved_assembly"):
            parts.append("an approved version")
        lines.append(f"- {scene['id']} {scene.get('title', '')}: " + "; ".join(parts))
    unplaced = [scene["id"] for scene in production["scenes"] if scene["id"] not in placed]
    if production.get("sequences") and unplaced:
        lines.append(f"Scenes in no sequence: {', '.join(unplaced)}")
    places = production.get("locations") or {}
    if places:
        lines.append("Locations: " + "; ".join(f"{place.get('label') or key} ({', '.join(place.get('appearances') or []) or 'no scene yet'})"
                                                for key, place in places.items()))
    cast = production.get("cast") or {}
    if cast:
        lines.append("Cast: " + ", ".join(member.get("label") or key for key, member in cast.items()))
    if budget is not None:
        lines.append(f"Generation budget: US$ {budget.get('spent_usd', 0):.2f} spent of US$ {budget.get('limit_usd', 0):.2f}")
    # Keep the work/review contract and complete canonical roster outside the
    # lossy scene-detail summary. A large film must not lose its review scope.
    structure = work_structure(production)
    return ("Production work contract:\n" + WORK_POLICY
            + "\nCanonical work structure:\n" + json.dumps(
                {key: value for key, value in structure.items() if key != 'policy'}, ensure_ascii=False)
            + "\nFilm status (bounded detail):\n" + _cut("\n".join(lines)))


def _structure(runtime: RuntimeClient, args: dict[str, Any]) -> str:
    value = work_structure(runtime.production(), scene=str(args.get('scene') or ''),
                           sequence=str(args.get('sequence') or ''))
    return json.dumps(value, ensure_ascii=False)


def production_work(value: dict, text: str = '') -> str:
    """Keep canonical work ahead of asset dumps, with explicit context limits."""
    work = value.get('sequence_work') or {}
    items = [item for item in work.get('items', [])
             if not text or text in (item['id'], item['sequence'])]
    return json.dumps({'project_id': value.get('project_id'), 'pending_count': work.get('pending_count', 0),
        'matching_count': len(items), 'more_available': len(items) > 8,
        'execution': work.get('execution', 'No background execution is implied.'),
        'items': [{key: item.get(key) for key in ('id', 'title', 'sequence', 'scene_ids', 'current_scene_ids',
             'owner', 'state', 'dispatch_status', 'sources_changed', 'gaps', 'next_action', 'instruction',
             'human_action_required', 'execution_supported', 'url')} for item in items[:8]]}, ensure_ascii=False)


def _work(runtime: RuntimeClient, args: dict[str, Any]) -> str:
    return production_work(runtime.creation(), str(args.get('text') or ''))


def _scene(runtime: RuntimeClient, args: dict[str, Any]) -> str:
    from .assistant import scene_digest

    return scene_digest(runtime.scene(str(args.get("scene", ""))))


def _shot(runtime: RuntimeClient, args: dict[str, Any]) -> str:
    scene = runtime.scene(str(args.get("scene", "")))
    wanted = str(args.get("shot", "")).upper()
    shot = next((item for item in scene["shots"] if item["id"].upper() in (wanted, f"P{wanted}")), None)
    if shot is None:
        return f"{scene['id']} has no shot {wanted}; its shots are {', '.join(item['id'] for item in scene['shots'])}."
    lines = [f"{scene['id']} {shot['id']}: {shot.get('label', '')}",
             f"Action: {shot.get('description') or '—'}",
             f"Camera: {shot.get('camera') or '—'} {shot.get('camera_text') or ''}".rstrip(),
             f"Duration: {shot.get('duration_seconds') or 0} s; block: {shot.get('block') or '—'}"]
    for line in shot.get("lines") or []:
        lines.append(f"Line — {line.get('who')}: {line.get('en') or line.get('text')}"
                     + (f" ({line['delivery']})" if line.get("delivery") else ""))
    if shot.get("derive"):
        lines.append(f"Master picture: an edit of {shot['derive'].get('from')} with {', '.join(shot['derive'].get('with') or [])}; "
                     f"approved: {shot.get('approved_picture') or 'not yet'}")
    for take in shot.get("takes") or []:
        kind = (take.get("provenance") or {}).get("kind", "")
        lines.append(f"Take {take['id']}: {take.get('status', '')}{' — chosen' if take.get('selected') else ''}"
                     + (f" ({kind})" if kind else ""))
    return _cut("\n".join(lines))


def _cast(runtime: RuntimeClient, args: dict[str, Any]) -> str:
    cast = runtime.production().get("cast") or {}
    if not cast:
        return "The production has no cast sheets."
    lines = []
    for key, member in cast.items():
        voice = (member.get("voice") or {}).get("described") or "no voice declared"
        seen = member.get("appearances") or []
        lines.append(f"{member.get('label') or key} ({key}): decides {', '.join(member.get('authoritative_for') or [])}; "
                     f"voice: {voice}; variants: {', '.join(member.get('variants') or {}) or 'none'}; "
                     f"appears in {len(seen)} scene(s)")
    return _cut("\n".join(lines))


def _screenplay(runtime: RuntimeClient, args: dict[str, Any]) -> str:
    query = str(args.get("text", "")).strip().lower()
    if not query:
        return "Say what to look for in the screenplay."
    found = []
    for document in runtime.screenplay().get("files") or []:
        for number, line in enumerate((document.get("text") or "").splitlines(), 1):
            if query in line.lower():
                found.append(f"{document['path']}:{number}: {line.strip()}")
    return _cut("\n".join(found[:25]) if found else f"Nothing in the screenplay mentions {query!r}.")


def _creation(runtime: RuntimeClient, args: dict[str, Any]) -> str:
    value = runtime.creation()
    wanted = str(args.get("text") or "")
    drafts = [draft for draft in value["drafts"] if not wanted or wanted in draft["id"] or wanted.lower() in draft["title"].lower()]
    lines = [f"Creation journal revision {value['revision']}; drafts are candidates, not the current screenplay."]
    assessment = value.get("inception_review", {}).get("current")
    if assessment:
        lines.append(f"Inception assessment {assessment['id']}: {assessment['status']}\n{assessment['summary']}")
        for item in assessment["readiness"]:
            lines.append(f"{item['destination']}: {item['status']} — {item['summary']}")
            lines.extend(f"Gap ({gap['owner']}): {gap['description']}; next: {gap['next_action']}" for gap in item["gaps"])
        lines.append("Proposed question: " + assessment["proposal"]["question"])
        if assessment.get("decision"):
            lines.append("Human direction: " + assessment["decision"]["guidance"])
            lines.append("Retained next instruction (not a live execution-state record): " + assessment["next_agent_action"]["instruction"])
    for round_ in value.get("active_rounds", value.get("rounds", []))[-3:]:
        lines.append(f"Exploration round {round_['id']}: {round_['title']}\nPurpose: {round_['rationale'][:350]}\nSource: {round_['source'][:250]}")
        lines.append("Creative corrections (not image inputs or approvals): " + ", ".join(
            f"{pair['previous']} -> {pair['current']}" for pair in round_["corrections"]))
    for draft in drafts[-6:]:
        lines.append(f"{draft['id']} ({draft['kind']}): {draft['title']}\n{draft['text'][:1200]}")
        lines.append("Inputs: " + ", ".join(f"{item['kind']} {item['id']} sha256={item['sha256']}" for item in draft["inputs"]))
    for ref in value["references"]:
        lines.append(f"Reference {ref['id']}: {ref.get('title', '')}")
    return _cut("\n".join(lines))


def _storyboard(runtime: RuntimeClient, args: dict[str, Any]) -> str:
    value = runtime.storyboard(str(args.get("scene") or ""))
    lines = [f"Storyboard journal revision {value['revision']}. Drawings are candidates, not approved masters."]
    for item in value["coverage"]:
        lines.append(f"{item['scene']}: {item['with_candidates']}/{item['shots']} shots have recorded candidates; not an approval count.")
    for item in value["candidates"][-12:]:
        lines.append(f"{item['id']} {item['scene']}/{item['shot']} v{item['version']}: {item['title']} ({item['review']})")
        lines.append("Inputs: " + ", ".join(f"{source['id']} sha256={source['sha256']}" for source in item["inputs"]))
        lines.extend(finding["message"] for finding in item["findings"])
    return _cut("\n".join(lines))


def _budget(runtime: RuntimeClient, args: dict[str, Any]) -> str:
    budget = runtime.budget()
    lines = [f"US$ {budget['spent_usd']:.2f} spent of US$ {budget['limit_usd']:.2f}"]
    lines += [f"{entry.get('at', '')[:16]} US$ {entry.get('usd', 0):.3f} {entry.get('what', '')} ({entry.get('status', '')})"
              for entry in budget.get("recent") or []]
    return "\n".join(lines)


#: name -> (what it answers, what it needs, how)
READS: dict[str, tuple[str, str, Callable[[RuntimeClient, dict[str, Any]], str]]] = {
    "production_work": ("explicit canonical pending agent work, Coordinator ownership, sequence scope and blockers; not running jobs or human approvals",
                        "optional text = exact work or sequence id", _work),
    "work_structure": ("canonical ordered sequences, scene membership and agent/human production-flow responsibilities; no approval inferred",
                       "optional sequence id, scene id", _structure),
    "storyboard": ("story drawings, pinned references and missing/changed evidence, not approved masters", "optional scene", _storyboard),
    "creation": ("saved concept/screenplay candidates and exploratory references", "optional text or draft id", _creation),
    "scene": ("one scene's records: blocks, workflow runs, gates, pictures, findings", "scene", _scene),
    "shot": ("one shot: action, camera, lines, master picture, takes and where they came from", "scene, shot", _shot),
    "cast": ("every cast member: what the sheet decides, voice, variants, how many scenes", "", _cast),
    "screenplay": ("screenplay lines containing a text", "text", _screenplay),
    "budget": ("the generation budget and the latest spending", "", _budget),
}


def read(runtime: RuntimeClient, name: str, args: dict[str, Any]) -> str:
    if name not in READS:
        return f"There is no read called {name!r}; the reads are {', '.join(READS)}."
    try:
        return READS[name][2](runtime, args or {})
    except Exception as error:
        return f"The read failed: {getattr(error, 'message', error)}"
