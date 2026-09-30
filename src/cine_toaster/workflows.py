"""The built-in workflow: master picture, a person's approval, video, takes (SPEC-0009).

A run is a list of steps kept in the scene's state, beside the gates it
opens. `advance` moves it as far as it can go: it submits the next job,
adopts what a finished job made, opens a gate and stops there. It is called
by the command that starts a run, by the decision on a gate, and by the Job
Manager when a job the run started finishes. It is idempotent, so calling it
again never repeats work.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from .commands import CommandResult, _check_revision, _check_writable, _clean_rationale, _new_command_id
from .errors import ResourceNotFoundError, ValidationError
from .events import Event, append_event
from .project import load_production, scene_directory
from .state import Actor, load_scene_state, now, scene_lock, with_progress, write_scene_state

TEMPLATES = ("block", "shot")
GATE_OUTCOMES = ("approved", "changes_requested", "rejected")
#: What can be wrong with a master picture: a closed list, so refusals can be
#: counted and compared across scenes, models and prompts later. Free text
#: says the rest.
REJECTION_REASONS = ("subject_moved", "identity", "geometry", "light", "detail_lost", "anatomy", "other")
FINISHED_RUN = ("done", "failed", "cancelled")
FINISHED_STEP = ("done", "skipped")

_RUNTIME: dict[str, Any] = {"manager": None}


# --- the runtime that runs the jobs ---------------------------------------------


def attach(manager) -> None:
    """Let this runtime's Job Manager move workflows when their jobs finish."""

    _RUNTIME["manager"] = manager
    if _on_job not in manager.listeners:
        manager.listeners.append(_on_job)


def _manager():
    manager = _RUNTIME["manager"]
    if manager is None:
        raise ValidationError("No runtime is running jobs here; workflows move inside `toast serve` or `toast workflow`")
    return manager


def _on_job(manager, job: dict[str, Any]) -> None:
    root, scene_id = Path(job["project_root"]), str((job.get("params") or {}).get("scene", ""))
    if not scene_id:
        return
    try:
        state = load_scene_state(scene_directory(root, scene_id), scene_id)
    except Exception:
        return
    for run in state.workflows.values():
        if run.get("state") not in FINISHED_RUN and any(step.get("job") == job["id"] for step in run["steps"]):
            advance(root, scene_id, run["id"])


# --- planning a run ---------------------------------------------------------------


def _masters(scene: dict[str, Any], shot_ids: list[str]) -> list[dict[str, Any]]:
    """The derived pictures a run of shots is made from, in order, once each."""

    from .takes import shot_key

    by_number = {shot_key(shot.get("number")): shot for shot in scene["shots"]}
    by_id = {shot["id"]: shot for shot in scene["shots"]}
    found: dict[str, dict[str, Any]] = {}
    for shot_id in shot_ids:
        shot = by_id[shot_id]
        candidates = [shot] + [by_number.get(shot_key(item.get("ref"))) for item in shot.get("from") or []
                               if isinstance(item, dict)]
        for candidate in candidates:
            if candidate and candidate.get("derive"):
                found.setdefault(candidate["id"], candidate)
                break
    return list(found.values())


def _block_steps(scene: dict[str, Any], block_id: str) -> list[dict[str, Any]]:
    from .blocks import scene_blocks

    block = next((item for item in scene_blocks(scene, None, Path(".")) if item.id == block_id), None)
    if block is None:
        raise ValidationError(f"{scene['id']} has no block {block_id!r}")
    if not block.contiguous:
        raise ValidationError(f"Block {block_id} is not a run of consecutive shots")
    steps: list[dict[str, Any]] = []
    for master in _masters(scene, block.shots):
        steps.append({"id": f"picture-{master['id']}", "kind": "picture", "shot": master["id"],
                      "label": f"Picture {master['number']}", "state": "pending", "seed": 1})
        steps.append({"id": f"approve-{master['id']}", "kind": "gate", "shot": master["id"],
                      "label": f"Approve picture {master['number']}", "state": "pending"})
    steps.append({"id": "generate", "kind": "generate", "label": f"Generate block {block_id}", "state": "pending"})
    steps.append({"id": "slice", "kind": "slice", "label": "Slice into takes", "state": "pending"})
    return steps


# --- commands -----------------------------------------------------------------------


def _scene(root: Path, scene_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    production = load_production(root)
    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        raise ResourceNotFoundError(f"Scene {scene_id!r} is not part of this production")
    return production, scene


def _result(kind: str, production: dict[str, Any], scene_id: str, revision: int, event: Event,
            shot_id: str = "") -> CommandResult:
    return CommandResult(command_id=event.payload.get("command_id", _new_command_id()), type=kind,
                         project_id=production["id"], scene_id=scene_id, shot_id=shot_id, take_id=None,
                         previous_take_id=None, revision=revision, event=event.public_dict())


def _shot_steps(scene: dict[str, Any], shot_id: str) -> list[dict[str, Any]]:
    """One shot outside any block: its master pictures, their approval, then its generation as a take."""

    shot = next((item for item in scene["shots"] if item["id"] == shot_id), None)
    if shot is None:
        raise ValidationError(f"{scene['id']} has no shot {shot_id!r}")
    if shot.get("block"):
        raise ValidationError(f"{shot_id} is part of block {shot['block']}: start the block's workflow")
    steps: list[dict[str, Any]] = []
    for master in _masters(scene, [shot_id]):
        steps.append({"id": f"picture-{master['id']}", "kind": "picture", "shot": master["id"],
                      "label": f"Picture {master['number']}", "state": "pending", "seed": 1})
        steps.append({"id": f"approve-{master['id']}", "kind": "gate", "shot": master["id"],
                      "label": f"Approve picture {master['number']}", "state": "pending"})
    steps.append({"id": "generate", "kind": "generate", "label": f"Generate {shot_id} as a take", "state": "pending"})
    return steps


def start_workflow(root: Path, *, scene_id: str, block_id: str, actor: Actor, template: str = "block",
                   expected_revision: int | None = None, shot_id: str = "") -> CommandResult:
    if shot_id:
        template = "shot"
    if template not in TEMPLATES:
        raise ValidationError(f"Unknown workflow template {template!r}", available=list(TEMPLATES))
    production, scene = _scene(root, scene_id)
    steps = _shot_steps(scene, shot_id) if template == "shot" else _block_steps(scene, block_id)
    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    command_id = _new_command_id()
    with scene_lock(directory):
        state = load_scene_state(directory, scene_id)
        _check_revision(expected_revision, state.revision)
        subject = {"scene": scene_id, "block": "" if template == "shot" else block_id, "shot": shot_id}
        active = [run for run in state.workflows.values() if run.get("state") not in FINISHED_RUN
                  and run.get("subject", {}).get("block", "") == subject["block"]
                  and run.get("subject", {}).get("shot", "") == subject["shot"]]
        if active:
            what = f"Shot {shot_id}" if template == "shot" else f"Block {block_id}"
            raise ValidationError(f"{what} already has a workflow in progress ({active[0]['id']})")
        run_id = "wf_" + uuid.uuid4().hex[:12]
        stamp = now()
        run = {"id": run_id, "template": template, "subject": subject,
               "state": "running", "steps": steps, "created_at": stamp, "updated_at": stamp,
               "started_by": actor.public_dict()}
        record = {"kind": "workflow.started", "workflow": run_id, "block": subject["block"], "shot": shot_id,
                  "actor": actor.public_dict(),
                  "decided_at": stamp, "command_id": command_id, "rationale": ""}
        committed = state.with_decision(decision=record, workflows={**state.workflows, run_id: run})
        write_scene_state(directory, committed)
    event = append_event(root, Event.create("workflow.started", production["id"], scene_id=scene_id,
                                            workflow=run_id, block=subject["block"], shot=shot_id,
                                            command_id=command_id))
    advance(root, scene_id, run_id)
    return _result("workflow.started", production, scene_id, committed.revision, event)


def decide_gate(root: Path, *, scene_id: str, gate_id: str, outcome: str, actor: Actor, chosen: str = "",
                rationale: str | None = None, reasons: list[str] | None = None,
                expected_revision: int | None = None) -> CommandResult:
    if outcome not in GATE_OUTCOMES:
        raise ValidationError(f"A gate is decided as one of {', '.join(GATE_OUTCOMES)}", outcome=outcome)
    tags = [str(item) for item in reasons or []]
    unknown = sorted(set(tags) - set(REJECTION_REASONS))
    if unknown:
        raise ValidationError(f"Unknown reason(s) {', '.join(unknown)}", allowed=list(REJECTION_REASONS))
    production, _ = _scene(root, scene_id)
    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    text = _clean_rationale(rationale)
    command_id = _new_command_id()
    with scene_lock(directory):
        state = load_scene_state(directory, scene_id)
        _check_revision(expected_revision, state.revision)
        gate = state.gates.get(gate_id)
        if gate is None:
            raise ResourceNotFoundError(f"No gate {gate_id!r} in {scene_id}")
        if gate["state"] != "waiting":
            raise ValidationError(f"Gate {gate_id} was already decided ({gate['state']}); a new question opens a new gate")
        if outcome == "approved":
            if chosen not in gate.get("candidates", []):
                raise ValidationError("Approve one of the gate's candidates", candidates=gate.get("candidates", []))
        elif not text and not tags:
            # A refusal is only useful if it says what is wrong: that is what the
            # next version has to fix, and what a later analysis learns from.
            raise ValidationError("Say what is wrong: a reason, or at least one of "
                                  f"{', '.join(REJECTION_REASONS)}", reasons=list(REJECTION_REASONS))
        stamp = now()
        decided = {**gate, "state": outcome, "chosen": chosen if outcome == "approved" else "",
                   "decided_at": stamp, "decided_by": actor.public_dict(), "rationale": text, "reasons": tags}
        record = {"kind": "gate.decided", "gate": gate_id, "outcome": outcome, "chosen": decided["chosen"],
                  "shot_id": gate.get("subject", ""), "actor": actor.public_dict(), "rationale": text,
                  "reasons": tags, "decided_at": stamp, "command_id": command_id}
        committed = state.with_decision(decision=record, gates={**state.gates, gate_id: decided})
        write_scene_state(directory, committed)
    event = append_event(root, Event.create("gate.decided", production["id"], scene_id=scene_id, gate=gate_id,
                                            outcome=outcome, chosen=decided["chosen"], shot_id=gate.get("subject", ""),
                                            actor=actor.public_dict(), rationale=text, command_id=command_id))
    if gate.get("workflow") and _RUNTIME["manager"] is not None:
        advance(root, scene_id, gate["workflow"])
    return _result("gate.decided", production, scene_id, committed.revision, event, gate.get("subject", ""))


def _breakdown_digest(root: Path, scene: dict[str, Any]) -> str:
    import hashlib

    path = root / scene["file"]
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.is_file() else ""


def decide_storyboard(root: Path, *, scene_id: str, approved: bool, actor: Actor, rationale: str | None = None,
                      expected_revision: int | None = None) -> CommandResult:
    """The phase gate (production-flow.md): the storyboard is approved as what will be produced, or reopened.

    A person's act, recorded as a gate with the breakdown's digest at that
    moment, so a later change to the breakdown shows. It blocks nothing.
    """

    if actor.kind != "human":
        raise ValidationError("The storyboard is approved or reopened by a person")
    production, scene = _scene(root, scene_id)
    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    text = _clean_rationale(rationale)
    command_id = _new_command_id()
    with scene_lock(directory):
        state = load_scene_state(directory, scene_id)
        _check_revision(expected_revision, state.revision)
        stamp = now()
        gate_id = "storyboard_" + uuid.uuid4().hex[:10]
        gate = {"id": gate_id, "kind": "approve_storyboard", "subject": scene_id, "workflow": None,
                "state": "approved" if approved else "reopened", "candidates": [], "chosen": "",
                "breakdown_digest": _breakdown_digest(root, scene), "requested_at": stamp,
                "requested_by": actor.public_dict(), "decided_at": stamp, "decided_by": actor.public_dict(),
                "rationale": text, "reasons": []}
        kind = "storyboard.approved" if approved else "storyboard.reopened"
        record = {"kind": kind, "gate": gate_id, "actor": actor.public_dict(), "rationale": text,
                  "decided_at": stamp, "command_id": command_id}
        committed = state.with_decision(decision=record, gates={**state.gates, gate_id: gate})
        write_scene_state(directory, committed)
    event = append_event(root, Event.create(kind, production["id"], scene_id=scene_id, gate=gate_id,
                                            actor=actor.public_dict(), rationale=text, command_id=command_id))
    return _result(kind, production, scene_id, committed.revision, event)


def phase(root: Path, scene: dict[str, Any], gates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Which phase the scene is in: fitting the storyboard, or producing what it defines."""

    latest = max((gate for gate in gates.values() if gate.get("kind") == "approve_storyboard"),
                 key=lambda gate: gate.get("decided_at", ""), default=None)
    if not latest or latest.get("state") != "approved":
        return {"phase": "fitting", "since": (latest or {}).get("decided_at", ""), "changed_since": False}
    return {"phase": "production", "since": latest.get("decided_at", ""),
            "approved_by": latest.get("decided_by"), "rationale": latest.get("rationale", ""),
            "changed_since": latest.get("breakdown_digest") != _breakdown_digest(root, scene)}


def cancel_workflow(root: Path, *, scene_id: str, workflow_id: str, actor: Actor,
                    rationale: str | None = None, expected_revision: int | None = None) -> CommandResult:
    production, _ = _scene(root, scene_id)
    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    command_id = _new_command_id()
    with scene_lock(directory):
        state = load_scene_state(directory, scene_id)
        _check_revision(expected_revision, state.revision)
        run = state.workflows.get(workflow_id)
        if run is None:
            raise ResourceNotFoundError(f"No workflow {workflow_id!r} in {scene_id}")
        if run["state"] in FINISHED_RUN:
            raise ValidationError(f"Workflow {workflow_id} is already {run['state']}")
        for step in run["steps"]:
            if step.get("state") == "running" and step.get("job") and _RUNTIME["manager"] is not None:
                _RUNTIME["manager"].cancel(step["job"])
        stamp = now()
        cancelled = {**run, "state": "cancelled", "updated_at": stamp}
        gates = {gate_id: ({**gate, "state": "rejected", "decided_at": stamp, "decided_by": actor.public_dict(),
                            "rationale": "workflow cancelled"}
                           if gate.get("workflow") == workflow_id and gate.get("state") == "waiting" else gate)
                 for gate_id, gate in state.gates.items()}
        record = {"kind": "workflow.cancelled", "workflow": workflow_id, "actor": actor.public_dict(),
                  "rationale": _clean_rationale(rationale), "decided_at": stamp, "command_id": command_id}
        committed = state.with_decision(decision=record, workflows={**state.workflows, workflow_id: cancelled},
                                        gates=gates)
        write_scene_state(directory, committed)
    event = append_event(root, Event.create("workflow.cancelled", production["id"], scene_id=scene_id,
                                            workflow=workflow_id, command_id=command_id))
    return _result("workflow.cancelled", production, scene_id, committed.revision, event)


# --- moving a run -------------------------------------------------------------------


def _save(root: Path, scene_id: str, directory: Path, state, run: dict[str, Any], gates=None) -> Any:
    run["updated_at"] = now()
    committed = with_progress(state, gates=state.gates if gates is None else gates,
                              workflows={**state.workflows, run["id"]: run})
    write_scene_state(directory, committed)
    return committed


def _notify(root: Path, production_id: str, scene_id: str, run: dict[str, Any], step: dict[str, Any]) -> None:
    append_event(root, Event.create("workflow.step", production_id, scene_id=scene_id, workflow=run["id"],
                                    step=step["id"], state=step["state"], run_state=run["state"]))


def advance(root: Path, scene_id: str, run_id: str) -> dict[str, Any]:
    """Move the run as far as it can go now; return it."""

    directory = scene_directory(root, scene_id)
    with scene_lock(directory):
        while True:
            production, scene = _scene(root, scene_id)
            state = load_scene_state(directory, scene_id)
            run = state.workflows.get(run_id)
            if run is None:
                raise ResourceNotFoundError(f"No workflow {run_id!r} in {scene_id}")
            run = {**run, "steps": [dict(step) for step in run["steps"]]}
            if run["state"] in FINISHED_RUN:
                return run
            step = next((item for item in run["steps"] if item["state"] not in FINISHED_STEP), None)
            if step is None:
                run["state"] = "done"
                _save(root, scene_id, directory, state, run)
                append_event(root, Event.create("workflow.done", production["id"], scene_id=scene_id, workflow=run_id))
                return run
            moved = _STEPS[step["kind"]](root, production, scene, state, run, step, directory)
            if not moved:
                return run


def _submit(root: Path, run: dict[str, Any], step: dict[str, Any], kind: str, params: dict[str, Any]) -> bool:
    """Start the step's job; a refusal (the budget, a missing picture) fails the run."""

    try:
        job = _manager().submit(kind, root, params)
    except Exception as error:
        step["state"], step["note"] = "failed", getattr(error, "message", None) or str(error)
        run["state"] = "failed"
        return False
    step["state"], step["job"] = "running", job["id"]
    return True


def _collect(root: Path, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any] | None:
    """The finished job's result, adopted; None while it runs or when it failed."""

    manager = _manager()
    job = manager.get(step["job"])
    if job["state"] in ("queued", "running"):
        return None
    if job["state"] != "succeeded":
        step["state"], step["note"] = "failed", job.get("error") or job["state"]
        run["state"] = "failed"
        return None
    if not job.get("adopted_at"):
        job = manager.adopt(job["id"])
    return job["result"]["summary"]


def _job_step(kind: str, params, output):
    def handle(root, production, scene, state, run, step, directory) -> bool:
        if step["state"] == "pending":
            started = _submit(root, run, step, kind, params(scene, run, step))
            _save(root, scene["id"], directory, state, run)
            _notify(root, production["id"], scene["id"], run, step)
            return False
        summary = _collect(root, run, step)
        if summary is None:
            if run["state"] == "failed":
                _save(root, scene["id"], directory, state, run)
                _notify(root, production["id"], scene["id"], run, step)
            return False
        step["state"], step["outputs"] = "done", output(summary)
        _save(root, scene["id"], directory, state, run)
        _notify(root, production["id"], scene["id"], run, step)
        return True
    return handle


def _picture_step(root, production, scene, state, run, step, directory) -> bool:
    if step["state"] == "pending" and not step.get("again"):
        from .pictures import picture_stem, picture_versions
        from .takes import work_directory_for

        shot = next(item for item in scene["shots"] if item["id"] == step["shot"])
        work = work_directory_for(root / scene["file"])
        versions = picture_versions(work, picture_stem(work, str(shot["number"])))
        if versions:
            step["state"], step["note"] = "skipped", f"{len(versions)} version(s) already exist"
            _save(root, scene["id"], directory, state, run)
            _notify(root, production["id"], scene["id"], run, step)
            return True
    return _job_step("derive_picture",
                     lambda scene, run, step: {"scene": scene["id"], "shot": step["shot"], "seed": step.get("seed", 1),
                                               **({"feedback": step["feedback"]} if step.get("feedback") else {})},
                     lambda summary: [summary["picture"]])(root, production, scene, state, run, step, directory)


def _gate_step(root, production, scene, state, run, step, directory) -> bool:
    from .pictures import picture_stem, picture_versions, relative
    from .takes import work_directory_for

    if step["state"] == "pending":
        approved = state.approved_pictures().get(step["shot"])
        if approved and not step.get("again"):
            step["state"], step["note"], step["outputs"] = "skipped", "already approved", [approved]
            _save(root, scene["id"], directory, state, run)
            _notify(root, production["id"], scene["id"], run, step)
            return True
        shot = next(item for item in scene["shots"] if item["id"] == step["shot"])
        work = work_directory_for(root / scene["file"])
        candidates = [relative(root, path) for path in picture_versions(work, picture_stem(work, str(shot["number"])))]
        gate_id = "gate_" + uuid.uuid4().hex[:12]
        gate = {"id": gate_id, "kind": "approve_picture", "subject": step["shot"], "workflow": run["id"],
                "step": step["id"], "state": "waiting", "candidates": candidates, "chosen": "",
                "requested_at": now(), "requested_by": {"id": "workflow", "kind": "system"}}
        step["state"], step["gate"] = "waiting", gate_id
        run["state"] = "waiting"
        _save(root, scene["id"], directory, state, run, gates={**state.gates, gate_id: gate})
        append_event(root, Event.create("gate.opened", production["id"], scene_id=scene["id"], gate=gate_id,
                                        shot_id=step["shot"], workflow=run["id"]))
        return False
    gate = state.gates.get(step.get("gate", ""), {})
    if gate.get("state") in (None, "waiting"):
        return False
    if gate["state"] == "approved":
        step["state"], step["outputs"] = "done", [gate["chosen"]]
        run["state"] = "running"
    elif gate["state"] == "changes_requested":
        # Another version of the picture, then the question again with every version.
        picture = next(item for item in run["steps"] if item["id"] == f"picture-{step['shot']}")
        # What was wrong travels with the request for the next version.
        feedback = {"reasons": list(gate.get("reasons") or []), "text": gate.get("rationale", "")}
        picture.update(state="pending", again=True, seed=int(picture.get("seed", 1)) + 1, job=None, note="",
                       feedback=feedback)
        step.update(state="pending", again=True, gate=None)
        run["state"] = "running"
    else:
        step["state"], step["note"] = "failed", "rejected"
        run["state"] = "cancelled"
    _save(root, scene["id"], directory, state, run)
    _notify(root, production["id"], scene["id"], run, step)
    return run["state"] == "running"


def _generated_clip(run: dict[str, Any]) -> str:
    step = next(item for item in run["steps"] if item["id"] == "generate")
    return (step.get("outputs") or [""])[0].rsplit("/", 1)[-1]


_STEPS = {
    "picture": _picture_step,
    "gate": _gate_step,
    "generate": _job_step("generate_block",
                          lambda scene, run, step: ({"scene": scene["id"], "shot": run["subject"]["shot"]}
                                                    if run["subject"].get("shot")
                                                    else {"scene": scene["id"], "block": run["subject"]["block"]}),
                          lambda summary: [summary["clip"]]),
    "slice": _job_step("slice_block",
                       lambda scene, run, step: {"scene": scene["id"], "block": run["subject"]["block"],
                                                 "clip": _generated_clip(run)},
                       lambda summary: [f"{item['shot']}: {item['take']}" for item in summary["slices"]]),
}
