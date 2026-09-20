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
) -> CommandResult:
    """Register a rendered version of the scene, with the takes it contains.

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
        takes={
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


COMMANDS = {
    "select_take": select_take,
    "clear_selection": clear_selection,
    "record_assembly": record_assembly,
    "review_assembly": review_assembly,
    "restore_assembly": restore_assembly,
}

# Commands act on a shot; these act on a whole scene version instead.
SCENE_LEVEL_COMMANDS = {"record_assembly", "review_assembly", "restore_assembly"}


def dispatch(root: Path, command_type: str, payload: dict[str, Any]) -> CommandResult:
    """Run one command by name, as an HTTP handler or agent tool would.

    Interfaces translate transport into this call. They never write project
    files themselves.
    """

    handler = COMMANDS.get(command_type)
    if handler is None:
        raise ValidationError(
            f"Unknown command {command_type!r}",
            available=sorted(COMMANDS),
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

    return handler(root, **arguments)


__all__ = [
    "CommandResult",
    "clear_selection",
    "dispatch",
    "now",
    "record_assembly",
    "restore_assembly",
    "review_assembly",
    "select_take",
]
