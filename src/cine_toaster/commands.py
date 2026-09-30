from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .errors import (
    PermissionDeniedError,
    ResourceNotFoundError,
    RevisionConflictError,
    TakeNotEligibleError,
    ValidationError,
)
from .events import Event, append_event
from .project import load_production, scene_directory
from .state import (
    ASSEMBLY_VERDICTS,
    Actor,
    Assembly,
    Selection,
    decision_record,
    load_scene_state,
    now,
    write_scene_state,
)


MAX_RATIONALE_LENGTH = 2000


@dataclass(frozen=True, slots=True)
class CommandResult:
    """What a committed command changed.

    Every interface returns this same shape, so the CLI, the HTTP API, the UI,
    and a future agent tool cannot drift into different semantics.
    """

    command_id: str
    type: str
    project_id: str
    scene_id: str
    shot_id: str
    take_id: str | None
    previous_take_id: str | None
    revision: int
    event: dict[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "type": self.type,
            "project_id": self.project_id,
            "scene_id": self.scene_id,
            "shot_id": self.shot_id,
            "take_id": self.take_id,
            "previous_take_id": self.previous_take_id,
            "revision": self.revision,
            "event": self.event,
        }


def _new_command_id() -> str:
    return "cmd_" + uuid.uuid4().hex[:16]


def _clean_rationale(value: str | None) -> str:
    rationale = (value or "").strip()
    if len(rationale) > MAX_RATIONALE_LENGTH:
        raise ValidationError(
            f"Rationale is longer than {MAX_RATIONALE_LENGTH} characters",
            length=len(rationale),
        )
    return rationale


def _locate(root: Path, scene_id: str, shot_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    production = load_production(root)
    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        raise ResourceNotFoundError(f"Scene {scene_id!r} is not part of this production")
    shot = next((item for item in scene["shots"] if item["id"] == shot_id), None)
    if shot is None:
        raise ResourceNotFoundError(
            f"Shot {shot_id!r} is not part of scene {scene_id!r}",
            scene_id=scene_id,
        )
    return production, scene, shot


def _check_revision(expected: int | None, actual: int) -> None:
    if expected is not None and expected != actual:
        raise RevisionConflictError(expected=expected, actual=actual)


def _check_writable(directory: Path, scene_id: str) -> None:
    """Refuse a mutation on a read-only source before touching anything.

    Required by SPEC-0002: a read-only project may be browsed, but a canonical
    command fails with a typed permission error rather than an I/O error halfway
    through a write.
    """

    if not os.access(directory, os.W_OK):
        raise PermissionDeniedError(
            f"Scene {scene_id!r} is on a read-only project source",
            scene_id=scene_id,
            path=str(directory),
        )


def select_take(
    root: Path,
    *,
    scene_id: str,
    shot_id: str,
    take_id: str,
    actor: Actor,
    expected_revision: int | None = None,
    rationale: str | None = None,
) -> CommandResult:
    """Adopt one alternative for a shot.

    This is the first canonical write in Cine Toaster and the template for every
    later one: validate, check the expected revision, commit atomically, then
    emit the event.
    """

    root = root.expanduser().resolve()
    rationale_text = _clean_rationale(rationale)
    take_id = (take_id or "").strip()
    if not take_id:
        raise ValidationError("A take id is required")

    production, _scene, shot = _locate(root, scene_id, shot_id)
    take = next((item for item in shot["takes"] if item["id"] == take_id), None)
    if take is None:
        raise ResourceNotFoundError(
            f"Take {take_id!r} is not registered on shot {shot_id!r}",
            scene_id=scene_id,
            shot_id=shot_id,
            available=[item["id"] for item in shot["takes"]],
        )
    if not take["selectable"]:
        raise TakeNotEligibleError(
            f"Take {take_id!r} has status {take['status']!r} and cannot be selected",
            scene_id=scene_id,
            shot_id=shot_id,
            take_id=take_id,
            status=take["status"],
        )

    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    state = load_scene_state(directory, scene_id)
    _check_revision(expected_revision, state.revision)

    previous = state.selections.get(shot_id)
    previous_take_id = previous.take_id if previous else None
    if previous_take_id == take_id and not rationale_text:
        # Re-selecting the same take without new reasoning is a no-op rather
        # than a fresh decision, so history stays meaningful.
        return CommandResult(
            command_id=_new_command_id(),
            type="take.selected",
            project_id=production["id"],
            scene_id=scene_id,
            shot_id=shot_id,
            take_id=take_id,
            previous_take_id=previous_take_id,
            revision=state.revision,
            event={},
        )

    command_id = _new_command_id()
    record = decision_record(
        kind="take.selected",
        shot_id=shot_id,
        take_id=take_id,
        previous_take_id=previous_take_id,
        actor=actor,
        rationale=rationale_text,
        command_id=command_id,
    )
    selections = dict(state.selections)
    selections[shot_id] = Selection(
        take_id=take_id,
        actor=actor,
        decided_at=record["decided_at"],
        rationale=rationale_text,
        media=take["media"],
    )
    committed = state.with_decision(decision=record, selections=selections)
    write_scene_state(directory, committed)

    event = append_event(
        root,
        Event.create(
            "take.selected",
            production["id"],
            scene_id=scene_id,
            shot_id=shot_id,
            take_id=take_id,
            previous_take_id=previous_take_id,
            revision=committed.revision,
            actor=actor.public_dict(),
            rationale=rationale_text,
            command_id=command_id,
        ),
    )
    return CommandResult(
        command_id=command_id,
        type="take.selected",
        project_id=production["id"],
        scene_id=scene_id,
        shot_id=shot_id,
        take_id=take_id,
        previous_take_id=previous_take_id,
        revision=committed.revision,
        event=event.public_dict(),
    )


def clear_selection(
    root: Path,
    *,
    scene_id: str,
    shot_id: str,
    actor: Actor,
    expected_revision: int | None = None,
    rationale: str | None = None,
) -> CommandResult:
    """Return a shot to undecided without erasing why it was decided before."""

    root = root.expanduser().resolve()
    rationale_text = _clean_rationale(rationale)
    production, _scene, _shot = _locate(root, scene_id, shot_id)

    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    state = load_scene_state(directory, scene_id)
    _check_revision(expected_revision, state.revision)

    previous = state.selections.get(shot_id)
    if previous is None:
        raise ValidationError(
            f"Shot {shot_id!r} has no committed selection to clear",
            scene_id=scene_id,
            shot_id=shot_id,
        )

    command_id = _new_command_id()
    record = decision_record(
        kind="take.cleared",
        shot_id=shot_id,
        take_id=None,
        previous_take_id=previous.take_id,
        actor=actor,
        rationale=rationale_text,
        command_id=command_id,
    )
    selections = {key: value for key, value in state.selections.items() if key != shot_id}
    committed = state.with_decision(decision=record, selections=selections)
    write_scene_state(directory, committed)

    event = append_event(
        root,
        Event.create(
            "take.cleared",
            production["id"],
            scene_id=scene_id,
            shot_id=shot_id,
            previous_take_id=previous.take_id,
            revision=committed.revision,
            actor=actor.public_dict(),
            rationale=rationale_text,
            command_id=command_id,
        ),
    )
    return CommandResult(
        command_id=command_id,
        type="take.cleared",
        project_id=production["id"],
        scene_id=scene_id,
        shot_id=shot_id,
        take_id=None,
        previous_take_id=previous.take_id,
        revision=committed.revision,
        event=event.public_dict(),
    )


def _validated_cut(root: Path, scene: dict[str, Any], shot_id: str, cut: dict[str, Any]) -> dict[str, Any]:
    """A cut as it will be recorded, or refused: the SPEC-0007 vocabulary and a catalogue transition."""

    from .cuts import CHAINS, CUT_TYPES
    from .transitions import list_transitions

    if not any(item["id"] == shot_id for item in scene["shots"]):
        raise ResourceNotFoundError(f"Shot {shot_id!r} is not part of scene {scene['id']!r}", scene_id=scene["id"])
    if scene["shots"] and scene["shots"][0]["id"] == shot_id:
        raise ValidationError(f"{shot_id} opens the scene: there is no cut into it (cuts between scenes belong "
                              "to the sequence)", scene_id=scene["id"], shot_id=shot_id)
    cut_type = str(cut.get("type") or "hard").strip().lower()
    if cut_type not in CUT_TYPES:
        raise ValidationError(f"Unknown cut type {cut_type!r}", allowed=list(CUT_TYPES))
    chain = str(cut.get("chain") or "").strip().lower()
    if chain and chain not in CHAINS:
        raise ValidationError(f"Unknown chain {chain!r}", allowed=list(CHAINS))
    transition = None
    raw = cut.get("transition") or {}
    if isinstance(raw, dict) and raw.get("id"):
        known = {item["id"] for item in list_transitions(root)}
        if raw["id"] not in known:
            raise ValidationError(f"No transition {raw['id']!r} in the catalog")
        milliseconds = raw.get("duration_ms")
        transition = {"id": str(raw["id"]), "duration_ms": int(milliseconds) if milliseconds else None,
                      "reason": _clean_rationale(raw.get("reason"))}
    return {"type": cut_type, "chain": chain, "reason": _clean_rationale(cut.get("reason")), "transition": transition}


def set_cut(
    root: Path,
    *,
    scene_id: str,
    shot_id: str,
    actor: Actor,
    cut: dict[str, Any],
    expected_revision: int | None = None,
    rationale: str | None = None,
) -> CommandResult:
    """Decide how a shot is entered from the previous one (plan step 13, SPEC-0007).

    `cut` holds `type`, optional `chain` and `reason`, and an optional catalog
    `transition` `{id, duration_ms, reason}`. The decision stands over the
    breakdown's own cut without rewriting it (ADR 0006).
    """

    root = root.expanduser().resolve()
    production, scene, _shot = _locate(root, scene_id, shot_id)
    validated = _validated_cut(root, scene, shot_id, cut)
    rationale_text = _clean_rationale(rationale)
    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    state = load_scene_state(directory, scene_id)
    _check_revision(expected_revision, state.revision)

    command_id = _new_command_id()
    stamp = now()
    decision = {**validated, "decided_at": stamp, "decided_by": actor.public_dict()}
    record = {"kind": "cut.set", "shot_id": shot_id, "cut": validated,
              "previous": state.cuts.get(shot_id), "actor": actor.public_dict(), "rationale": rationale_text,
              "decided_at": stamp, "command_id": command_id}
    committed = state.with_decision(decision=record, cuts={**state.cuts, shot_id: decision})
    write_scene_state(directory, committed)
    event = append_event(root, Event.create("cut.set", production["id"], scene_id=scene_id, shot_id=shot_id,
                                            cut=record["cut"], revision=committed.revision, actor=actor.public_dict(),
                                            rationale=rationale_text, command_id=command_id))
    return CommandResult(command_id=command_id, type="cut.set", project_id=production["id"], scene_id=scene_id,
                         shot_id=shot_id, take_id=None, previous_take_id=None, revision=committed.revision,
                         event=event.public_dict())


def set_cuts(
    root: Path,
    *,
    scene_id: str,
    cuts: list[dict[str, Any]],
    actor: Actor,
    expected_revision: int | None = None,
    rationale: str | None = None,
) -> CommandResult:
    """Decide several cuts of a scene as one decision: all of them, or none (CT-0046).

    `cuts` is `[{shot, cut}]`, each `cut` as for `set_cut`. Every cut is
    checked before anything is written; one refusal refuses the set, and an
    accepted set is one revision with one entry in the history. This is how
    a proposal of several cuts (an agent's, a person's) is taken or left whole.
    """

    root = root.expanduser().resolve()
    production = load_production(root)
    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        raise ResourceNotFoundError(f"Scene {scene_id!r} is not part of this production")
    if not cuts:
        raise ValidationError("A set of cuts needs at least one cut")
    validated: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(cuts):
        shot_id = str((item or {}).get("shot") or "").strip()
        if not shot_id:
            raise ValidationError(f"Cut {index + 1} of the set names no shot")
        if shot_id in validated:
            raise ValidationError(f"The set decides the cut into {shot_id} twice")
        try:
            validated[shot_id] = _validated_cut(root, scene, shot_id, (item or {}).get("cut") or {})
        except ValidationError as error:
            raise ValidationError(f"Cut into {shot_id}: {error.message}; none of the set was applied",
                                  shot_id=shot_id) from error
    rationale_text = _clean_rationale(rationale)
    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    state = load_scene_state(directory, scene_id)
    _check_revision(expected_revision, state.revision)

    command_id = _new_command_id()
    stamp = now()
    decided = {shot_id: {**cut, "decided_at": stamp, "decided_by": actor.public_dict()}
               for shot_id, cut in validated.items()}
    record = {"kind": "cuts.set", "shot_id": "", "shots": list(validated), "cuts": validated,
              "previous": {shot_id: state.cuts.get(shot_id) for shot_id in validated},
              "actor": actor.public_dict(), "rationale": rationale_text, "decided_at": stamp,
              "command_id": command_id}
    committed = state.with_decision(decision=record, cuts={**state.cuts, **decided})
    write_scene_state(directory, committed)
    event = append_event(root, Event.create("cuts.set", production["id"], scene_id=scene_id, shots=list(validated),
                                            cuts=validated, revision=committed.revision, actor=actor.public_dict(),
                                            rationale=rationale_text, command_id=command_id))
    return CommandResult(command_id=command_id, type="cuts.set", project_id=production["id"], scene_id=scene_id,
                         shot_id="", take_id=None, previous_take_id=None, revision=committed.revision,
                         event=event.public_dict())


def clear_cut(
    root: Path,
    *,
    scene_id: str,
    shot_id: str,
    actor: Actor,
    expected_revision: int | None = None,
    rationale: str | None = None,
) -> CommandResult:
    """Return a cut to what the breakdown says, keeping the decision in the history."""

    root = root.expanduser().resolve()
    production, _scene, _shot = _locate(root, scene_id, shot_id)
    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    state = load_scene_state(directory, scene_id)
    _check_revision(expected_revision, state.revision)
    if shot_id not in state.cuts:
        raise ValidationError(f"The cut into {shot_id} was not decided here; it is the breakdown's",
                              scene_id=scene_id, shot_id=shot_id)
    command_id = _new_command_id()
    stamp = now()
    record = {"kind": "cut.cleared", "shot_id": shot_id, "previous": state.cuts[shot_id], "actor": actor.public_dict(),
              "rationale": _clean_rationale(rationale), "decided_at": stamp, "command_id": command_id}
    committed = state.with_decision(decision=record, cuts={k: v for k, v in state.cuts.items() if k != shot_id})
    write_scene_state(directory, committed)
    event = append_event(root, Event.create("cut.cleared", production["id"], scene_id=scene_id, shot_id=shot_id,
                                            revision=committed.revision, actor=actor.public_dict(), command_id=command_id))
    return CommandResult(command_id=command_id, type="cut.cleared", project_id=production["id"], scene_id=scene_id,
                         shot_id=shot_id, take_id=None, previous_take_id=None, revision=committed.revision,
                         event=event.public_dict())


def _made_from(root: Path, scene: dict[str, Any], shot: dict[str, Any], ref: str) -> str:
    """A reference as the breakdown writes it (a shot's number, a master, a file), or refused."""

    from .pictures import source_picture
    from .takes import shot_key

    match = next((item for item in scene["shots"]
                  if item["id"] == ref or shot_key(item.get("number")) == shot_key(ref)), None)
    if match is not None:
        if match["id"] == shot["id"]:
            raise ValidationError(f"{shot['id']} cannot be made from itself")
        return str(match.get("number") or match["id"])
    if source_picture(root, scene, ref) is None:
        raise ValidationError(f"{ref!r} is neither a shot of {scene['id']} nor a picture file",
                              scene_id=scene["id"], shot_id=shot["id"])
    return ref


def _check_no_cycle(scene: dict[str, Any], shot: dict[str, Any], ref: str) -> None:
    from .takes import shot_key

    by_number = {shot_key(item.get("number")): item for item in scene["shots"]}
    seen, current = {shot_key(shot.get("number"))}, ref
    while current:
        key = shot_key(current)
        if key in seen:
            raise ValidationError(f"{shot['id']} made from {ref} would be made from itself, through {current}")
        seen.add(key)
        other = by_number.get(key)
        lineage = (other or {}).get("from") or []
        current = str(lineage[0].get("ref") or "") if other and lineage and isinstance(lineage[0], dict) else ""


def set_reference(
    root: Path,
    *,
    scene_id: str,
    shot_id: str,
    actor: Actor,
    made_from: str = "",
    cast: list[str] | None = None,
    expected_revision: int | None = None,
    rationale: str | None = None,
) -> CommandResult:
    """Decide what a shot's picture is made from, and whose faces a derived picture takes (CT-0046).

    `made_from` is a shot of the scene (its number or id), a master, or a
    picture file; `cast` (for a derived picture only) replaces the cast
    lending faces. The breakdown is not rewritten (ADR 0006).
    """

    from .cast import cast_key

    root = root.expanduser().resolve()
    production, scene, shot = _locate(root, scene_id, shot_id)
    made_from = (made_from or "").strip()
    if not made_from and cast is None:
        raise ValidationError("Say what the shot is made from, or whose faces it takes")
    ref = _made_from(root, scene, shot, made_from) if made_from else ""
    if ref:
        _check_no_cycle(scene, shot, ref)
    names = None
    if cast is not None:
        if not shot.get("derive"):
            raise ValidationError(f"{shot_id} is not a derived picture (derive: {{from, with, request}}); "
                                  "only a derived picture takes faces from the cast")
        members = production.get("cast") or {}
        names = []
        for name in cast:
            name = str(name).strip()
            if not name:
                continue
            if not any(cast_key(name) in {cast_key(n) for n in [m["id"], m["label"], *m.get("names", [])]}
                       for m in members.values()):
                raise ValidationError(f"{name} has no cast sheet (cast/<id>/character.yaml)", allowed=sorted(members))
            names.append(name)
    rationale_text = _clean_rationale(rationale)
    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    state = load_scene_state(directory, scene_id)
    _check_revision(expected_revision, state.revision)

    command_id = _new_command_id()
    stamp = now()
    previous = state.references.get(shot_id) or {}
    decision = {"from": ref or previous.get("from", ""), "with": names if names is not None else previous.get("with"),
                "decided_at": stamp, "decided_by": actor.public_dict()}
    record = {"kind": "reference.set", "shot_id": shot_id, "from": decision["from"], "with": decision["with"],
              "previous": state.references.get(shot_id), "actor": actor.public_dict(), "rationale": rationale_text,
              "decided_at": stamp, "command_id": command_id}
    committed = state.with_decision(decision=record, references={**state.references, shot_id: decision})
    write_scene_state(directory, committed)
    event = append_event(root, Event.create("reference.set", production["id"], scene_id=scene_id, shot_id=shot_id,
                                            revision=committed.revision, actor=actor.public_dict(),
                                            rationale=rationale_text, command_id=command_id))
    return CommandResult(command_id=command_id, type="reference.set", project_id=production["id"], scene_id=scene_id,
                         shot_id=shot_id, take_id=None, previous_take_id=None, revision=committed.revision,
                         event=event.public_dict())


def clear_reference(
    root: Path,
    *,
    scene_id: str,
    shot_id: str,
    actor: Actor,
    expected_revision: int | None = None,
    rationale: str | None = None,
) -> CommandResult:
    """Return a shot's references to what the breakdown says, keeping the decision in the history."""

    root = root.expanduser().resolve()
    production, _scene, _shot = _locate(root, scene_id, shot_id)
    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    state = load_scene_state(directory, scene_id)
    _check_revision(expected_revision, state.revision)
    if shot_id not in state.references:
        raise ValidationError(f"{shot_id}'s references were not decided here; they are the breakdown's",
                              scene_id=scene_id, shot_id=shot_id)
    command_id = _new_command_id()
    stamp = now()
    record = {"kind": "reference.cleared", "shot_id": shot_id, "previous": state.references[shot_id],
              "actor": actor.public_dict(), "rationale": _clean_rationale(rationale), "decided_at": stamp,
              "command_id": command_id}
    committed = state.with_decision(decision=record,
                                    references={k: v for k, v in state.references.items() if k != shot_id})
    write_scene_state(directory, committed)
    event = append_event(root, Event.create("reference.cleared", production["id"], scene_id=scene_id, shot_id=shot_id,
                                            revision=committed.revision, actor=actor.public_dict(),
                                            command_id=command_id))
    return CommandResult(command_id=command_id, type="reference.cleared", project_id=production["id"],
                         scene_id=scene_id, shot_id=shot_id, take_id=None, previous_take_id=None,
                         revision=committed.revision, event=event.public_dict())


def set_voice(
    root: Path,
    *,
    scene_id: str,
    shot_id: str,
    actor: Actor,
    converted: bool = True,
    expected_revision: int | None = None,
    rationale: str | None = None,
) -> CommandResult:
    """Decide whether the cut hears this shot's speech in the cast's own voices (CT-0040).

    The conversion happens when the scene is assembled, on whichever take is
    chosen, so changing the take does not undo it. `converted=False` returns
    the shot to the take's own sound; the decision stays in the history.
    """

    from .voice import speakers_of

    root = root.expanduser().resolve()
    production, _scene, shot = _locate(root, scene_id, shot_id)
    if converted:
        speakers_of(root, production, shot)  # every speaker needs a sheet and a recording, said now
    rationale_text = _clean_rationale(rationale)
    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    state = load_scene_state(directory, scene_id)
    _check_revision(expected_revision, state.revision)
    if not converted and shot_id not in state.voices:
        raise ValidationError(f"{shot_id} already keeps its take's own sound", scene_id=scene_id, shot_id=shot_id)

    command_id = _new_command_id()
    stamp = now()
    kind = "voice.converted" if converted else "voice.original"
    voices = dict(state.voices)
    if converted:
        voices[shot_id] = {"converted": True, "decided_at": stamp, "decided_by": actor.public_dict()}
    else:
        voices.pop(shot_id)
    record = {"kind": kind, "shot_id": shot_id, "previous": state.voices.get(shot_id), "actor": actor.public_dict(),
              "rationale": rationale_text, "decided_at": stamp, "command_id": command_id}
    committed = state.with_decision(decision=record, voices=voices)
    write_scene_state(directory, committed)
    event = append_event(root, Event.create(kind, production["id"], scene_id=scene_id, shot_id=shot_id,
                                            revision=committed.revision, actor=actor.public_dict(),
                                            rationale=rationale_text, command_id=command_id))
    return CommandResult(command_id=command_id, type=kind, project_id=production["id"], scene_id=scene_id,
                         shot_id=shot_id, take_id=None, previous_take_id=None, revision=committed.revision,
                         event=event.public_dict())


def record_assembly(
    root: Path,
    *,
    scene_id: str,
    assembly_id: str,
    actor: Actor,
    media: str = "",
    summary: str = "",
    duration_seconds: float = 0.0,
    expected_revision: int | None = None,
    takes: dict[str, str] | None = None,
) -> CommandResult:
    """Register a rendered version of the scene, with the takes it contains.

    ``takes`` is the snapshot when the caller knows exactly which take of each
    shot the render used (an assembly job does); otherwise the scene's
    committed selections are taken.

    The snapshot is the point. Without it, "v10 was better" is a memory; with
    it, v10 is a set of selections that can be restored in one command.
    """

    root = root.expanduser().resolve()
    assembly_id = (assembly_id or "").strip()
    if not assembly_id:
        raise ValidationError("An assembly id is required")

    production = load_production(root)
    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        raise ResourceNotFoundError(f"Scene {scene_id!r} is not part of this production")

    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    state = load_scene_state(directory, scene_id)
    _check_revision(expected_revision, state.revision)

    if any(item.id == assembly_id for item in state.assemblies):
        raise ValidationError(
            f"Scene {scene_id!r} already has a version called {assembly_id!r}",
            scene_id=scene_id,
            assembly_id=assembly_id,
        )

    command_id = _new_command_id()
    created_at = now()
    assembly = Assembly(
        id=assembly_id,
        created_at=created_at,
        media=media.strip(),
        summary=summary.strip(),
        duration_seconds=float(duration_seconds or 0),
        revision=state.revision,
        takes=dict(takes) if takes is not None else {
            shot_id: selection.take_id for shot_id, selection in state.selections.items()
        },
    )
    record = {
        "kind": "assembly.recorded",
        "shot_id": "",
        "assembly_id": assembly_id,
        "actor": actor.public_dict(),
        "rationale": assembly.summary,
        "command_id": command_id,
        "decided_at": created_at,
    }
    committed = state.with_decision(
        decision=record, assemblies=[*state.assemblies, assembly]
    )
    write_scene_state(directory, committed)

    event = append_event(
        root,
        Event.create(
            "assembly.recorded",
            production["id"],
            scene_id=scene_id,
            assembly_id=assembly_id,
            revision=committed.revision,
            actor=actor.public_dict(),
            command_id=command_id,
        ),
    )
    return CommandResult(
        command_id=command_id,
        type="assembly.recorded",
        project_id=production["id"],
        scene_id=scene_id,
        shot_id="",
        take_id=None,
        previous_take_id=None,
        revision=committed.revision,
        event=event.public_dict(),
    )


def review_assembly(
    root: Path,
    *,
    scene_id: str,
    assembly_id: str,
    verdict: str,
    actor: Actor,
    note: str | None = None,
    expected_revision: int | None = None,
) -> CommandResult:
    """Record what a human thought of one rendered version.

    A verdict is stated, never inferred from which file is newest. A version
    that was never shown is as much a fact as one that was rejected.
    """

    root = root.expanduser().resolve()
    verdict = (verdict or "").strip()
    if verdict not in ASSEMBLY_VERDICTS:
        raise ValidationError(
            f"Unknown verdict {verdict!r}", allowed=sorted(ASSEMBLY_VERDICTS)
        )
    note_text = _clean_rationale(note)

    production = load_production(root)
    if not any(item["id"] == scene_id for item in production["scenes"]):
        raise ResourceNotFoundError(f"Scene {scene_id!r} is not part of this production")

    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    state = load_scene_state(directory, scene_id)
    _check_revision(expected_revision, state.revision)

    target = next((item for item in state.assemblies if item.id == assembly_id), None)
    if target is None:
        raise ResourceNotFoundError(
            f"Scene {scene_id!r} has no version called {assembly_id!r}",
            scene_id=scene_id,
            available=[item.id for item in state.assemblies],
        )

    command_id = _new_command_id()
    reviewed_at = now()
    assemblies: list[Assembly] = []
    for item in state.assemblies:
        if item.id == assembly_id:
            assemblies.append(
                replace(
                    item,
                    verdict=verdict,
                    note=note_text,
                    reviewed_at=reviewed_at,
                    reviewed_by=actor,
                )
            )
        elif verdict == "approved" and item.verdict == "approved":
            # Only one version is the current cut; the previous one is not
            # deleted, it is marked as superseded.
            assemblies.append(replace(item, verdict="superseded"))
        else:
            assemblies.append(item)

    record = {
        "kind": "assembly.reviewed",
        "shot_id": "",
        "assembly_id": assembly_id,
        "verdict": verdict,
        "actor": actor.public_dict(),
        "rationale": note_text,
        "command_id": command_id,
        "decided_at": reviewed_at,
    }
    committed = state.with_decision(decision=record, assemblies=assemblies)
    write_scene_state(directory, committed)

    event = append_event(
        root,
        Event.create(
            "assembly.reviewed",
            production["id"],
            scene_id=scene_id,
            assembly_id=assembly_id,
            verdict=verdict,
            revision=committed.revision,
            actor=actor.public_dict(),
            rationale=note_text,
            command_id=command_id,
        ),
    )
    return CommandResult(
        command_id=command_id,
        type="assembly.reviewed",
        project_id=production["id"],
        scene_id=scene_id,
        shot_id="",
        take_id=None,
        previous_take_id=None,
        revision=committed.revision,
        event=event.public_dict(),
    )


def restore_assembly(
    root: Path,
    *,
    scene_id: str,
    assembly_id: str,
    actor: Actor,
    rationale: str | None = None,
    expected_revision: int | None = None,
) -> CommandResult:
    """Roll the scene back to the takes a previous version was built from.

    Rollback is a new decision, not an undo: the selections change, the history
    keeps both, and the version being restored is left exactly as it was.
    """

    root = root.expanduser().resolve()
    rationale_text = _clean_rationale(rationale)

    production = load_production(root)
    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        raise ResourceNotFoundError(f"Scene {scene_id!r} is not part of this production")

    directory = scene_directory(root, scene_id)
    _check_writable(directory, scene_id)
    state = load_scene_state(directory, scene_id)
    _check_revision(expected_revision, state.revision)

    target = next((item for item in state.assemblies if item.id == assembly_id), None)
    if target is None:
        raise ResourceNotFoundError(
            f"Scene {scene_id!r} has no version called {assembly_id!r}",
            scene_id=scene_id,
            available=[item.id for item in state.assemblies],
        )

    if not target.takes:
        raise ValidationError(
            f"Version {assembly_id!r} carries no take snapshot, so there is nothing to "
            "restore. Versions imported from an older record keep their verdict and "
            "their render, but cannot be rolled back to.",
            scene_id=scene_id,
            assembly_id=assembly_id,
        )

    takes_by_shot = {
        shot["id"]: {take["id"]: take["media"] for take in shot["takes"]}
        for shot in scene["shots"]
    }
    missing = [
        f"{shot_id}/{take_id}"
        for shot_id, take_id in target.takes.items()
        if take_id not in takes_by_shot.get(shot_id, {})
    ]
    if missing:
        raise ValidationError(
            f"Version {assembly_id!r} refers to takes that no longer exist: "
            + ", ".join(sorted(missing)),
            scene_id=scene_id,
            assembly_id=assembly_id,
            missing=sorted(missing),
        )

    command_id = _new_command_id()
    decided_at = now()
    selections = {
        shot_id: Selection(
            take_id=take_id,
            actor=actor,
            decided_at=decided_at,
            rationale=rationale_text or f"Restored from version {assembly_id}",
            media=takes_by_shot[shot_id][take_id],
        )
        for shot_id, take_id in target.takes.items()
    }
    record = {
        "kind": "assembly.restored",
        "shot_id": "",
        "assembly_id": assembly_id,
        "actor": actor.public_dict(),
        "rationale": rationale_text,
        "command_id": command_id,
        "decided_at": decided_at,
    }
    committed = state.with_decision(decision=record, selections=selections)
    write_scene_state(directory, committed)

    event = append_event(
        root,
        Event.create(
            "assembly.restored",
            production["id"],
            scene_id=scene_id,
            assembly_id=assembly_id,
            revision=committed.revision,
            shots=len(selections),
            actor=actor.public_dict(),
            rationale=rationale_text,
            command_id=command_id,
        ),
    )
    return CommandResult(
        command_id=command_id,
        type="assembly.restored",
        project_id=production["id"],
        scene_id=scene_id,
        shot_id="",
        take_id=None,
        previous_take_id=None,
        revision=committed.revision,
        event=event.public_dict(),
    )


SEQUENCE_VERDICTS = ("approved", "rejected", "pending")


def record_sequence_version(
    root: Path,
    *,
    sequence_id: str,
    version_id: str,
    actor: Actor,
    media: str,
    scenes: dict[str, str],
    summary: str = "",
    duration_seconds: float = 0.0,
) -> dict[str, Any]:
    """Register an assembled cut of a sequence, with the scene versions it holds."""

    from . import sequence_state

    root = root.expanduser().resolve()
    production = load_production(root)
    if not any(item["id"] == sequence_id for item in production["sequences"]):
        raise ResourceNotFoundError(f"No sequence {sequence_id!r}")
    data = sequence_state.load(root)
    entry = data["sequences"].setdefault(sequence_id, {"versions": []})
    if any(item["id"] == version_id for item in entry["versions"]):
        raise ValidationError(f"Sequence {sequence_id!r} already has a version {version_id!r}")
    version = {
        "id": version_id, "created_at": now(), "media": media, "summary": summary.strip(),
        "duration_seconds": float(duration_seconds or 0), "scenes": dict(scenes),
        "verdict": "pending", "note": "", "reviewed_by": None,
    }
    entry["versions"].append(version)
    data["revision"] += 1
    sequence_state.write(root, data)
    event = append_event(root, Event.create(
        "sequence.version.recorded", production["id"], sequence_id=sequence_id,
        version_id=version_id, actor=actor.public_dict(), revision=data["revision"],
    ))
    return {"sequence_id": sequence_id, "version": version, "revision": data["revision"], "event": event.public_dict()}


def review_sequence_version(
    root: Path, *, sequence_id: str, version_id: str, verdict: str, actor: Actor, note: str = "",
) -> dict[str, Any]:
    """A person's verdict on one version of a sequence."""

    from . import sequence_state

    if verdict not in SEQUENCE_VERDICTS:
        raise ValidationError(f"Unknown verdict {verdict!r}", allowed=list(SEQUENCE_VERDICTS))
    root = root.expanduser().resolve()
    production = load_production(root)
    data = sequence_state.load(root)
    entry = data["sequences"].get(sequence_id) or {"versions": []}
    version = next((item for item in entry["versions"] if item["id"] == version_id), None)
    if version is None:
        raise ResourceNotFoundError(f"Sequence {sequence_id!r} has no version {version_id!r}")
    version.update(verdict=verdict, note=_clean_rationale(note), reviewed_by=actor.public_dict(), reviewed_at=now())
    data["revision"] += 1
    sequence_state.write(root, data)
    event = append_event(root, Event.create(
        "sequence.version.reviewed", production["id"], sequence_id=sequence_id,
        version_id=version_id, verdict=verdict, actor=actor.public_dict(), revision=data["revision"],
    ))
    return {"sequence_id": sequence_id, "version": version, "revision": data["revision"], "event": event.public_dict()}


COMMANDS = {
    "select_take": select_take,
    "clear_selection": clear_selection,
    "record_assembly": record_assembly,
    "review_assembly": review_assembly,
    "restore_assembly": restore_assembly,
    "set_cut": set_cut,
    "set_cuts": set_cuts,
    "clear_cut": clear_cut,
    "set_voice": set_voice,
    "set_reference": set_reference,
    "clear_reference": clear_reference,
}

# Commands act on a shot; these act on a whole scene version instead.
SCENE_LEVEL_COMMANDS = {"record_assembly", "review_assembly", "restore_assembly", "set_cuts"}

# SPEC-0009: workflow runs and the gates they open.
WORKFLOW_COMMANDS = {"start_workflow", "decide_gate", "cancel_workflow", "resume_workflow",
                     "approve_storyboard", "reopen_storyboard"}


def _dispatch_workflow(root: Path, command_type: str, payload: dict[str, Any]) -> CommandResult:
    from . import workflows

    actor_payload = payload.get("actor") or {}
    if isinstance(actor_payload, str):
        actor = Actor(id=actor_payload)
    else:
        actor = Actor(id=str(actor_payload.get("id", "")).strip() or "unknown",
                      kind=str(actor_payload.get("kind", "human")))
    scene_id = str(payload.get("scene_id", "")).strip()
    if not scene_id:
        raise ValidationError("scene_id is required")
    expected = payload.get("expected_revision")
    try:
        expected = int(expected) if expected is not None else None
    except (TypeError, ValueError) as error:
        raise ValidationError("expected_revision must be an integer") from error
    if command_type == "start_workflow":
        return workflows.start_workflow(root, scene_id=scene_id, block_id=str(payload.get("block", "")).strip(),
                                        actor=actor, template=str(payload.get("template") or "block"),
                                        expected_revision=expected, shot_id=str(payload.get("shot", "") or "").strip())
    if command_type == "decide_gate":
        return workflows.decide_gate(root, scene_id=scene_id, gate_id=str(payload.get("gate_id", "")).strip(),
                                     outcome=str(payload.get("outcome", "")).strip(), actor=actor,
                                     chosen=str(payload.get("chosen", "")).strip(),
                                     rationale=payload.get("rationale"), reasons=payload.get("reasons") or [],
                                     expected_revision=expected)
    if command_type in ("approve_storyboard", "reopen_storyboard"):
        return workflows.decide_storyboard(root, scene_id=scene_id, approved=command_type == "approve_storyboard",
                                           actor=actor, rationale=payload.get("rationale"),
                                           expected_revision=expected)
    workflow_id = str(payload.get("workflow_id", "")).strip()
    if command_type == "cancel_workflow":
        return workflows.cancel_workflow(root, scene_id=scene_id, workflow_id=workflow_id, actor=actor,
                                         rationale=payload.get("rationale"), expected_revision=expected)
    run = workflows.advance(root, scene_id, workflow_id)
    production = load_production(root)
    return CommandResult(command_id=_new_command_id(), type="workflow.resumed", project_id=production["id"],
                         scene_id=scene_id, shot_id="", take_id=None, previous_take_id=None,
                         revision=load_scene_state(scene_directory(root, scene_id), scene_id).revision,
                         event={"workflow": run["id"], "state": run["state"]})


def dispatch(root: Path, command_type: str, payload: dict[str, Any]) -> CommandResult:
    """Run one command by name, as an HTTP handler or agent tool would.

    Interfaces translate transport into this call. They never write project
    files themselves.
    """

    handler = COMMANDS.get(command_type)
    if handler is None and command_type in WORKFLOW_COMMANDS:
        return _dispatch_workflow(root, command_type, payload)
    if handler is None:
        raise ValidationError(
            f"Unknown command {command_type!r}",
            available=sorted({*COMMANDS, *WORKFLOW_COMMANDS}),
        )

    actor_payload = payload.get("actor") or {}
    if isinstance(actor_payload, str):
        actor = Actor(id=actor_payload)
    else:
        actor = Actor(
            id=str(actor_payload.get("id", "")).strip() or "unknown",
            kind=str(actor_payload.get("kind", "human")),
        )

    expected_revision = payload.get("expected_revision")
    if expected_revision is not None:
        try:
            expected_revision = int(expected_revision)
        except (TypeError, ValueError) as error:
            raise ValidationError("expected_revision must be an integer") from error

    scene_id = str(payload.get("scene_id", "")).strip()
    if not scene_id:
        raise ValidationError("scene_id is required")

    if command_type == "set_cuts":
        cuts = payload.get("cuts")
        return set_cuts(root, scene_id=scene_id, cuts=cuts if isinstance(cuts, list) else [], actor=actor,
                        expected_revision=expected_revision, rationale=payload.get("rationale"))
    if command_type in SCENE_LEVEL_COMMANDS:
        arguments: dict[str, Any] = {
            "scene_id": scene_id,
            "assembly_id": str(payload.get("assembly_id", "")).strip(),
            "actor": actor,
            "expected_revision": expected_revision,
        }
        if command_type == "record_assembly":
            arguments["media"] = str(payload.get("media", ""))
            arguments["summary"] = str(payload.get("summary", ""))
            arguments["duration_seconds"] = float(payload.get("duration_seconds", 0) or 0)
        elif command_type == "review_assembly":
            arguments["verdict"] = str(payload.get("verdict", "")).strip()
            arguments["note"] = payload.get("note")
        else:
            arguments["rationale"] = payload.get("rationale")
        return handler(root, **arguments)

    shot_id = str(payload.get("shot_id", "")).strip()
    if not shot_id:
        raise ValidationError("shot_id is required")
    arguments = {
        "scene_id": scene_id,
        "shot_id": shot_id,
        "actor": actor,
        "expected_revision": expected_revision,
        "rationale": payload.get("rationale"),
    }
    if command_type == "select_take":
        arguments["take_id"] = str(payload.get("take_id", "")).strip()
    elif command_type == "set_cut":
        arguments["cut"] = payload.get("cut") if isinstance(payload.get("cut"), dict) else {}
    elif command_type == "set_reference":
        arguments["made_from"] = str(payload.get("from") or "")
        cast = payload.get("with")
        arguments["cast"] = [str(item) for item in cast] if isinstance(cast, list) else None
    elif command_type == "set_voice":
        arguments["converted"] = payload.get("converted", True) not in (False, "false", "0", 0)

    return handler(root, **arguments)


__all__ = [
    "CommandResult",
    "clear_cut",
    "clear_reference",
    "clear_selection",
    "dispatch",
    "now",
    "record_assembly",
    "restore_assembly",
    "review_assembly",
    "select_take",
    "set_cut",
    "set_cuts",
    "set_reference",
    "set_voice",
]
