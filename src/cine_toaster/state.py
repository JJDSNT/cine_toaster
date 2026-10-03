from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

try:  # POSIX: one lock across processes (the CLI beside `toast serve`)
    import fcntl
except ImportError:  # pragma: no cover - Windows keeps the in-process lock only
    fcntl = None

from .errors import PersistenceError, ValidationError


STATE_FILENAME = "state.json"
STATE_SCHEMA_VERSION = 5
MAX_DECISION_HISTORY = 200
MAX_ASSEMBLIES = 200

ASSEMBLY_VERDICTS = {"pending", "approved", "rejected", "not_sent", "superseded"}

ACTOR_KINDS = {"human", "agent", "system"}


@dataclass(frozen=True, slots=True)
class Actor:
    """Who is making a decision.

    Recording actor kind separately from identity lets a production show, later,
    which choices a person made and which an agent proposed.
    """

    id: str
    kind: str = "human"

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValidationError("Actor id must not be empty")
        if self.kind not in ACTOR_KINDS:
            raise ValidationError(
                f"Unknown actor kind {self.kind!r}",
                allowed=sorted(ACTOR_KINDS),
            )

    def public_dict(self) -> dict[str, str]:
        return {"id": self.id, "kind": self.kind}


@dataclass(frozen=True, slots=True)
class Selection:
    """The take currently adopted for one shot."""

    take_id: str
    actor: Actor
    decided_at: str
    rationale: str = ""
    # The chosen file, recorded with the choice so an assembly tool needs to
    # read nothing but this one file to honour it.
    media: str = ""

    def public_dict(self) -> dict[str, Any]:
        return {
            "take_id": self.take_id,
            "actor": self.actor.public_dict(),
            "decided_at": self.decided_at,
            "rationale": self.rationale,
            "media": self.media,
        }


@dataclass(frozen=True, slots=True)
class Assembly:
    """One rendered version of a scene, and what the author thought of it.

    An assembly is the artefact a human actually judges. Keeping the take
    snapshot with it is what makes a verdict reversible: "v10 was better" stops
    being a memory and becomes a set of selections that can be restored.
    """

    id: str
    created_at: str
    media: str = ""
    summary: str = ""
    duration_seconds: float = 0.0
    verdict: str = "pending"
    note: str = ""
    reviewed_at: str = ""
    reviewed_by: Actor | None = None
    revision: int = 0
    takes: dict[str, str] = field(default_factory=dict)
    #: The same cut delivered in other formats (CT-0049): rendition id -> media.
    renditions: dict[str, str] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "media": self.media,
            "renditions": dict(self.renditions),
            "summary": self.summary,
            "duration_seconds": self.duration_seconds,
            "verdict": self.verdict,
            "note": self.note,
            "reviewed_at": self.reviewed_at,
            "reviewed_by": self.reviewed_by.public_dict() if self.reviewed_by else None,
            "revision": self.revision,
            "takes": dict(sorted(self.takes.items())),
        }

    def differences_from(self, other: Assembly) -> list[dict[str, str]]:
        """Which shots changed take between two versions.

        This is the question a director asks about two cuts and currently
        answers by watching both and remembering.
        """

        changes: list[dict[str, str]] = []
        for shot_id in sorted(set(self.takes) | set(other.takes)):
            mine = self.takes.get(shot_id, "")
            theirs = other.takes.get(shot_id, "")
            if mine != theirs:
                changes.append({"shot_id": shot_id, "from": theirs, "to": mine})
        return changes


@dataclass(frozen=True, slots=True)
class SceneState:
    """Runtime-owned canonical state for one scene.

    Authored files (``scene.toml``, screenplays, shot descriptions) are never
    rewritten by Cine Toaster, so human comments and direction notes survive.
    Decisions the runtime commits live here instead. See ADR 0006.
    """

    scene_id: str
    revision: int = 0
    updated_at: str = ""
    selections: dict[str, Selection] = field(default_factory=dict)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    assemblies: list[Assembly] = field(default_factory=list)
    #: Human gates and the workflow runs that opened them (SPEC-0009), by id.
    gates: dict[str, dict[str, Any]] = field(default_factory=dict)
    workflows: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Cuts decided here (plan step 13), by incoming shot: they stand over the
    #: breakdown's `cut`/`transition` without rewriting it (ADR 0006).
    cuts: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Shots whose speech the cut hears in the cast's own recorded voices
    #: (CT-0040), by shot: converted when the scene is assembled, whatever take is chosen.
    voices: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: What a shot's picture is made from, and whose faces a derived picture
    #: takes, decided here over the breakdown (CT-0046), by shot.
    references: dict[str, dict[str, Any]] = field(default_factory=dict)

    def approved_pictures(self) -> dict[str, str]:
        """The picture each shot's latest approved gate chose (SPEC-0009)."""

        chosen: dict[str, tuple[str, str]] = {}
        for gate in self.gates.values():
            if gate.get("kind") == "approve_picture" and gate.get("state") == "approved" and gate.get("chosen"):
                subject, when = str(gate.get("subject", "")), str(gate.get("decided_at", ""))
                if subject not in chosen or when > chosen[subject][0]:
                    chosen[subject] = (when, str(gate["chosen"]))
        return {subject: path for subject, (_, path) in chosen.items()}

    def approved_assembly(self) -> Assembly | None:
        return next(
            (item for item in reversed(self.assemblies) if item.verdict == "approved"),
            None,
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "scene_id": self.scene_id,
            "revision": self.revision,
            "updated_at": self.updated_at,
            "selections": {
                shot_id: selection.public_dict()
                for shot_id, selection in sorted(self.selections.items())
            },
            "decisions": self.decisions,
            "assemblies": [assembly.public_dict() for assembly in self.assemblies],
            "gates": self.gates,
            "workflows": self.workflows,
            "cuts": self.cuts,
            "voices": self.voices,
            "references": self.references,
        }

    def with_decision(
        self,
        *,
        decision: dict[str, Any],
        selections: dict[str, Selection] | None = None,
        assemblies: list[Assembly] | None = None,
        gates: dict[str, dict[str, Any]] | None = None,
        workflows: dict[str, dict[str, Any]] | None = None,
        cuts: dict[str, dict[str, Any]] | None = None,
        voices: dict[str, dict[str, Any]] | None = None,
        references: dict[str, dict[str, Any]] | None = None,
    ) -> SceneState:
        history = [*self.decisions, decision][-MAX_DECISION_HISTORY:]
        return replace(
            self,
            revision=self.revision + 1,
            updated_at=decision["decided_at"],
            selections=self.selections if selections is None else selections,
            decisions=history,
            assemblies=self.assemblies if assemblies is None else assemblies[-MAX_ASSEMBLIES:],
            gates=self.gates if gates is None else gates,
            workflows=self.workflows if workflows is None else workflows,
            cuts=self.cuts if cuts is None else cuts,
            voices=self.voices if voices is None else voices,
            references=self.references if references is None else references,
        )


def with_progress(state: SceneState, *, gates: dict[str, dict[str, Any]],
                  workflows: dict[str, dict[str, Any]]) -> SceneState:
    """A workflow moving on by itself: a new revision, no entry in the decision history.

    Only what a person or agent decides is a decision (SPEC-0009); a step
    finishing is not.
    """

    return replace(state, revision=state.revision + 1, updated_at=now(), gates=gates, workflows=workflows)


_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}
_DEPTH: dict[str, int] = {}


@contextmanager
def scene_lock(scene_directory: Path) -> Iterator[None]:
    """Hold one scene's state for a read-decide-write, against every other writer.

    A mutation reads `state.json`, checks the revision, and writes the next
    one. Without this, two writers (the canvas and the CLI, an agent and a
    workflow step) could both read revision N and both write N+1: one
    decision silently lost. The lock is the scene directory itself, locked
    with `flock`, so no file is added to the project; within a process it is
    reentrant, so a command may call another on the same scene.
    """

    key = str(scene_directory.resolve())
    with _GUARD:
        lock = _LOCKS.setdefault(key, threading.RLock())
    with lock:
        depth = _DEPTH.get(key, 0)
        handle = None
        if depth == 0 and fcntl is not None and scene_directory.is_dir():
            handle = os.open(scene_directory, os.O_RDONLY)
            fcntl.flock(handle, fcntl.LOCK_EX)
        _DEPTH[key] = depth + 1
        try:
            yield
        finally:
            _DEPTH[key] = depth
            if handle is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)
                os.close(handle)


def state_path(scene_directory: Path) -> Path:
    return scene_directory / STATE_FILENAME


def _actor_from(value: Any) -> Actor:
    if isinstance(value, dict):
        return Actor(id=str(value.get("id", "unknown")), kind=str(value.get("kind", "human")))
    return Actor(id=str(value or "unknown"))


def load_scene_state(scene_directory: Path, scene_id: str) -> SceneState:
    """Read committed state, tolerating a scene that has never been decided on."""

    path = state_path(scene_directory)
    if not path.is_file():
        return SceneState(scene_id=scene_id)

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PersistenceError(f"Unreadable scene state: {path} ({error})") from error

    version = int(document.get("schema_version", STATE_SCHEMA_VERSION))
    if version > STATE_SCHEMA_VERSION:
        raise PersistenceError(
            f"{path} uses schema version {version}; this build understands "
            f"{STATE_SCHEMA_VERSION}. Upgrade Cine Toaster to open this project.",
        )

    selections: dict[str, Selection] = {}
    for shot_id, raw in (document.get("selections") or {}).items():
        if not isinstance(raw, dict) or not raw.get("take_id"):
            continue
        selections[str(shot_id)] = Selection(
            take_id=str(raw["take_id"]),
            actor=_actor_from(raw.get("actor")),
            decided_at=str(raw.get("decided_at", "")),
            rationale=str(raw.get("rationale", "")),
            media=str(raw.get("media", "")),
        )

    assemblies: list[Assembly] = []
    for raw in document.get("assemblies") or []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        reviewer = raw.get("reviewed_by")
        assemblies.append(
            Assembly(
                id=str(raw["id"]),
                created_at=str(raw.get("created_at", "")),
                media=str(raw.get("media", "")),
                summary=str(raw.get("summary", "")),
                duration_seconds=float(raw.get("duration_seconds", 0) or 0),
                verdict=str(raw.get("verdict", "pending")),
                note=str(raw.get("note", "")),
                reviewed_at=str(raw.get("reviewed_at", "")),
                reviewed_by=_actor_from(reviewer) if reviewer else None,
                revision=int(raw.get("revision", 0)),
                takes={str(key): str(value) for key, value in (raw.get("takes") or {}).items()},
                renditions={str(key): str(value) for key, value in (raw.get("renditions") or {}).items()},
            )
        )

    decisions = document.get("decisions")
    gates = document.get("gates")
    workflows = document.get("workflows")
    cuts = document.get("cuts")
    voices = document.get("voices")
    references = document.get("references")
    return SceneState(
        scene_id=str(document.get("scene_id", scene_id)),
        revision=int(document.get("revision", 0)),
        updated_at=str(document.get("updated_at", "")),
        selections=selections,
        decisions=list(decisions) if isinstance(decisions, list) else [],
        assemblies=assemblies,
        gates=dict(gates) if isinstance(gates, dict) else {},
        workflows=dict(workflows) if isinstance(workflows, dict) else {},
        cuts=dict(cuts) if isinstance(cuts, dict) else {},
        voices=dict(voices) if isinstance(voices, dict) else {},
        references=dict(references) if isinstance(references, dict) else {},
    )


def write_scene_state(scene_directory: Path, state: SceneState) -> None:
    """Commit scene state atomically.

    A crash or a full disk leaves the previous file intact: the new content is
    written to a sibling temporary file and renamed only once it is on disk.
    """

    path = state_path(scene_directory)
    payload = json.dumps(state.public_dict(), ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
    try:
        scene_directory.mkdir(parents=True, exist_ok=True)
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(scene_directory, os.O_RDONLY)
        try:
            os.fsync(directory)
        except OSError:
            # Directory fsync is unsupported on some filesystems; the rename
            # itself is still atomic.
            pass
        finally:
            os.close(directory)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise PersistenceError(f"Could not commit scene state to {path}: {error}") from error


def now() -> str:
    return datetime.now(UTC).isoformat()


def decision_record(
    *,
    kind: str,
    shot_id: str,
    take_id: str | None,
    previous_take_id: str | None,
    actor: Actor,
    rationale: str,
    command_id: str,
) -> dict[str, Any]:
    record = {
        "kind": kind,
        "shot_id": shot_id,
        "take_id": take_id,
        "previous_take_id": previous_take_id,
        "actor": actor.public_dict(),
        "rationale": rationale,
        "command_id": command_id,
        "decided_at": now(),
    }
    return {key: value for key, value in record.items() if value is not None or key == "take_id"}


__all__ = [
    "ASSEMBLY_VERDICTS",
    "Actor",
    "Assembly",
    "Selection",
    "SceneState",
    "STATE_FILENAME",
    "STATE_SCHEMA_VERSION",
    "decision_record",
    "load_scene_state",
    "now",
    "state_path",
    "write_scene_state",
]
