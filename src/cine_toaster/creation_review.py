"""Agent-authored Inception readiness and human direction decisions (ADR 0028)."""
from __future__ import annotations

import uuid
from pathlib import Path

from .creation import _commit, content_digest, load_creation, reference_snapshot
from .errors import CineToasterError, PermissionDeniedError, ResourceNotFoundError, RevisionConflictError, ValidationError
from .events import Event, append_event
from .project import load_production
from .references import digest, load_references
from .state import Actor, now, scene_lock

DESTINATIONS = ("screenplay", "storyboard", "masters")
READINESS = ("ready", "needs_work", "not_assessed")
OUTCOMES = ("approved", "changes_requested")


def _text(value, name: str, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError(f"{name} must be non-empty text of at most {limit} characters")
    return value.strip()


def _validate_assessment(title, summary, readiness, proposal):
    _text(title, "title", 240); _text(summary, "summary")
    if not isinstance(readiness, list) or not 1 <= len(readiness) <= len(DESTINATIONS):
        raise ValidationError("readiness must assess one or more distinct destinations")
    seen = set()
    for item in readiness:
        if not isinstance(item, dict) or not isinstance(item.get("destination"), str):
            raise ValidationError("Invalid readiness judgment")
        destination = item["destination"]
        if destination not in DESTINATIONS or destination in seen or item.get("status") not in READINESS:
            raise ValidationError("Invalid or repeated readiness destination/status")
        seen.add(destination)
        _text(item.get("summary"), "readiness summary")
        if not isinstance(item.get("gaps"), list) or len(item["gaps"]) > 20:
            raise ValidationError("gaps must be a list of at most 20 actionable gaps")
        for gap in item["gaps"]:
            if not isinstance(gap, dict) or gap.get("owner") not in ("agent", "human"):
                raise ValidationError("Each gap must name an agent or human owner")
            _text(gap.get("description"), "gap description")
            _text(gap.get("next_action"), "gap next action")
    if not isinstance(proposal, dict) or proposal.get("destination") not in seen:
        raise ValidationError("The proposal must name an assessed destination")
    for key in ("question", "scope", "why", "next_step"):
        _text(proposal.get(key), f"proposal {key}")
    if proposal.get("sequence") is not None and (not isinstance(proposal["sequence"], str) or not proposal["sequence"].strip()
                                   or len(proposal["sequence"]) > 120):
        raise ValidationError("proposal sequence must be a canonical sequence id")


def validate_review_records(state: dict):
    """Called by the journal reader; malformed production truth is never empty."""
    assessments = state.get("assessments", [])
    decisions = state.get("assessment_decisions", [])
    if not isinstance(assessments, list) or not isinstance(decisions, list):
        raise ValueError("Invalid Inception review journal lists")
    known = set()
    try:
        for item in assessments:
            if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in known
                    or not isinstance(item.get("materials"), dict) or not isinstance(item.get("materials_sha256"), str)):
                raise ValueError("Invalid retained Inception assessment")
            _validate_assessment(item.get("title"), item.get("summary"), item.get("readiness"), item.get("proposal"))
            refs = item["materials"].get("references")
            if (not isinstance(refs, list) or any(not isinstance(ref, dict) or not isinstance(ref.get("id"), str) for ref in refs)
                    or content_digest(item["materials"]) != item["materials_sha256"]):
                raise ValueError("Invalid assessment material snapshot")
            known.add(item["id"])
        decided = set()
        for item in decisions:
            if (not isinstance(item, dict) or item.get("assessment") not in known or item["assessment"] in decided
                    or item.get("outcome") not in OUTCOMES or not isinstance(item.get("guidance"), str)
                    or not isinstance(item.get("actor"), dict) or item["actor"].get("kind") != "human"
                    or not isinstance(item.get("next_agent_action"), dict)
                    or not isinstance(item["next_agent_action"].get("instruction"), str)
                    or item["next_agent_action"].get("status") != "not_dispatched"):
                raise ValueError("Invalid retained Inception direction decision")
            decided.add(item["assessment"])
    except ValidationError as error:
        raise ValueError(error.message) from error


def _materials(root: Path, state: dict, references: list[str]):
    from .storyboard import load_storyboard
    production = load_production(root)
    scripts = []
    for name in production.get("script_files") or []:
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValidationError("Screenplay material must stay inside the production")
        scripts.append({"path": name, "sha256": digest(path)})
    drawings = []
    for item in load_storyboard(root)["candidates"]:
        path = (root / item["image"]["path"]).resolve()
        if not path.is_relative_to(root):
            raise ValidationError("Storyboard material must stay inside the production")
        drawings.append({"id": item["id"], "scene": item["scene"], "shot": item["shot"],
                         "record_sha256": content_digest(item), "image_sha256": digest(path) if path.is_file() else None})
    return {"references": reference_snapshot(root, references), "screenplay": scripts, "storyboard": drawings,
            "creative_context_sha256": content_digest({"title": production["title"], "logline": production.get("logline"),
                "cast": production.get("cast"), "drafts": state["drafts"], "rounds": state["rounds"],
                **({"art_briefs": state["art_briefs"]} if state.get("art_briefs") else {}),
                "scenes": [{"id": scene["id"], "direction": scene.get("direction"), "style": scene.get("style"),
                    "shots": [{key: shot.get(key) for key in ("id", "label", "script", "camera", "covers", "duration_seconds")}
                              for shot in scene["shots"]]} for scene in production["scenes"]]})}


def _unchanged(root: Path, state: dict, assessment: dict):
    continuity_review = assessment.get("proposal", {}).get("continuity_review")
    if continuity_review:
        from .directing import current_direction_review
        if not current_direction_review(root, state, assessment["proposal"].get("direction_plan"), continuity_review):
            return False
    review_id = assessment.get("proposal", {}).get("visual_review")
    if review_id:
        from .art_direction import art_view
        reviews = art_view(root, state, inception_source_digest(root, state))["reviews"]
        review = next((item for item in reviews if item["id"] == review_id), None)
        if (not review or review["stale"] or review["verdict"] != "ready_for_human"
                or assessment["proposal"].get("art_brief") != review["brief"]
                or any(item["brief"] == review["brief"] for item in reviews[reviews.index(review) + 1:])):
            return False
    current = _materials(root, state, [item["id"] for item in assessment["materials"]["references"]])
    return content_digest(current) == assessment["materials_sha256"]


def inception_source_digest(root: Path, state: dict) -> str:
    """Publication precondition for the whole source set read by an agent."""
    root = Path(root).expanduser().resolve()
    return content_digest(_materials(root, state, [item["id"] for item in load_references(root)]))


def inception_review_view(root: Path, state: dict):
    history = state.get("assessments", [])
    if not history:
        return {"current": None, "history": [], "decisions": state.get("assessment_decisions", [])}
    current = history[-1]
    decision = next((item for item in state.get("assessment_decisions", []) if item["assessment"] == current["id"]), None)
    try:
        changed = not _unchanged(Path(root).resolve(), state, current)
        handoff = next((item for item in state.get('stage_handoffs', []) if decision and item['decision'] == decision['id']), None)
        if handoff:
            from .stage_handoff import handoff_current
            changed = not handoff_current(Path(root).resolve(), state, handoff)
    except (CineToasterError, OSError):
        changed = True
    status = "needs_reassessment" if changed else decision["outcome"] if decision else "awaiting_decision"
    from .stage_handoff import preview_handoff
    preview = preview_handoff(root, current, state)
    return {"current": {**current, "status": status, "material_changed": changed, "decision": decision,
                         "handoff_preview": preview,
                         "next_agent_action": decision["next_agent_action"] if decision else None},
            "history": history, "decisions": state.get("assessment_decisions", [])}


def record_inception_assessment(root: Path, *, title: str, summary: str, readiness: list[dict], proposal: dict,
                                references: list[str], expected_revision: int, actor: Actor,
                                expected_source_digest: str | None = None):
    _validate_assessment(title, summary, readiness, proposal)
    if actor.kind not in ("agent", "system"):
        raise PermissionDeniedError("Readiness is authored by the agent; human direction is a separate decision")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError("expected_revision must be a non-negative integer")
    root = Path(root).expanduser().resolve()
    with scene_lock(root):
        state = load_creation(root)
        if state["revision"] != expected_revision:
            raise RevisionConflictError(expected_revision, state["revision"])
        if expected_source_digest is not None and expected_source_digest != inception_source_digest(root, state):
            raise ValidationError("Inception source material changed; reread it and reassess before publishing")
        materials = _materials(root, state, references)
        assessment = {"id": "assessment_" + uuid.uuid4().hex[:16], "title": title.strip(), "summary": summary.strip(),
            "readiness": readiness, "proposal": proposal, "materials": materials, "materials_sha256": content_digest(materials),
            "actor": actor.public_dict(), "created_at": now()}
        if (proposal.get("visual_review") or proposal.get("continuity_review")) and not _unchanged(root, state, assessment):
            raise ValidationError("The proposal needs a current successful specialist review")
        committed = {**state, "revision": state["revision"] + 1, "assessments": [*state.get("assessments", []), assessment]}
        _commit(root, committed)
        append_event(root, Event.create("creation.assessed", state["project_id"], assessment_id=assessment["id"],
                     revision=committed["revision"], actor=actor.public_dict()))
        return {"revision": committed["revision"], "assessment": assessment}


def decide_inception_assessment(root: Path, *, assessment: str, outcome: str, guidance: str,
                                expected_revision: int, actor: Actor, advance: bool = False, expected_handoff_digest: str = ''):
    if actor.kind != "human":
        raise PermissionDeniedError("Only a human can approve an Inception direction or request changes")
    if outcome not in OUTCOMES:
        raise ValidationError("outcome must be approved or changes_requested")
    if type(advance) is not bool or advance and outcome != 'approved':
        raise ValidationError('Only an approved direction can advance')
    if not isinstance(guidance, str) or len(guidance) > 4000:
        raise ValidationError("guidance must be text of at most 4000 characters")
    if outcome == "changes_requested":
        _text(guidance, "Direction for the next pass")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError("expected_revision must be a non-negative integer")
    root = Path(root).expanduser().resolve()
    with scene_lock(root):
        state = load_creation(root)
        if state["revision"] != expected_revision:
            raise RevisionConflictError(expected_revision, state["revision"])
        current = next((item for item in state.get("assessments", []) if item["id"] == assessment), None)
        if current is None:
            raise ResourceNotFoundError("No saved Inception assessment with that id")
        if current != state["assessments"][-1] or any(item["assessment"] == assessment for item in state.get("assessment_decisions", [])):
            raise ValidationError("This assessment was superseded or already decided; inspect the current request")
        if not _unchanged(root, state, current):
            raise ValidationError("Material changed since the assessment; the agent must reassess before approval")
        action = current["proposal"]["next_step"] if outcome == "approved" else guidance.strip()
        decision = {"id": "direction_" + uuid.uuid4().hex[:16], "assessment": assessment, "outcome": outcome,
            "guidance": guidance.strip(), "actor": actor.public_dict(), "created_at": now(),
            "next_agent_action": {"instruction": action, "status": "not_dispatched", "owner": "agent"}}
        committed = {**state, "revision": state["revision"] + 1,
                     "assessment_decisions": [*state.get("assessment_decisions", []), decision]}
        handoff = None
        if advance:
            from .stage_handoff import make_handoff
            handoff = make_handoff(root, state, current, decision, expected_handoff_digest)
            committed['stage_handoffs'] = [*state.get('stage_handoffs', []), handoff]
        _commit(root, committed)
        append_event(root, Event.create("creation.direction_decided", state["project_id"], assessment_id=assessment,
                     outcome=outcome, revision=committed["revision"], actor=actor.public_dict()))
        return {"revision": committed["revision"], "decision": decision, **({'handoff': handoff} if handoff else {})}
