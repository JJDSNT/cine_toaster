"""Versioned creative candidates and explicit upstream inputs (ADR 0026)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .errors import PermissionDeniedError, PersistenceError, ResourceNotFoundError, RevisionConflictError, ValidationError
from .events import Event, append_event
from .project import load_production
from .references import IMAGE_SUFFIXES, digest, load_references
from .state import Actor, now, scene_lock

MAX_TEXT_BYTES = 1024 * 1024
KINDS = ("concept", "screenplay")


def content_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _root(root: Path) -> Path:
    return Path(root).expanduser().resolve()


def load_creation(root: Path, *, production: dict | None = None) -> dict[str, Any]:
    root = _root(root)
    project_id = (production if production is not None else load_production(root))["id"]
    path = root / "creation" / "state.json"
    if not path.resolve().is_relative_to(root):
        raise ValidationError("Creation journal must stay inside the production")
    if not path.exists():
        return {"schema_version": 1, "project_id": project_id, "revision": 0, "drafts": [], "rounds": []}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if (state.get("schema_version") != 1 or state.get("project_id") != project_id
                or type(state.get("revision")) is not int or not isinstance(state.get("drafts"), list)):
            raise ValueError("unsupported schema, project identity or journal shape")
        ids = set()
        for draft in state["drafts"]:
            if (not isinstance(draft, dict) or draft.get("kind") not in KINDS
                    or not isinstance(draft.get("text"), str) or not isinstance(draft.get("inputs"), list)
                    or not isinstance(draft.get("id"), str) or draft["id"] in ids):
                raise ValueError("invalid draft record")
            ids.add(draft["id"])
            for source in draft["inputs"]:
                if (not isinstance(source, dict) or source.get("kind") not in ("concept", "reference")
                        or not isinstance(source.get("id"), str) or not isinstance(source.get("sha256"), str)):
                    raise ValueError("invalid input record")
        if not isinstance(state.get("rounds", []), list):
            raise ValueError("invalid exploration round list")
        for round_ in state.get("rounds", []):
            if (not isinstance(round_, dict) or not isinstance(round_.get("id"), str)
                    or not isinstance(round_.get("references"), list) or not isinstance(round_.get("corrections"), list)
                    or not isinstance(round_.get("title"), str) or round_["id"] in ids
                    or any(not isinstance(round_.get(key), str) for key in ("follows", "rationale", "source", "created_at"))):
                raise ValueError("invalid exploration round record")
            ids.add(round_["id"])
            for source in round_["references"]:
                if (not isinstance(source, dict) or source.get("kind") != "reference"
                        or not isinstance(source.get("id"), str) or not isinstance(source.get("sha256"), str)):
                    raise ValueError("invalid round reference input")
            for pair in round_["corrections"]:
                if not isinstance(pair, dict) or any(not isinstance(pair.get(key), str) for key in ("previous", "current")):
                    raise ValueError("invalid correction relation")
        from .creation_review import validate_review_records
        validate_review_records(state)
        from .art_direction import validate_art_records
        validate_art_records(state)
        from .directing import validate_direction_records
        validate_direction_records(state)
        from .stage_handoff import validate_handoffs
        validate_handoffs(state)
        from .sequence_work import validate_sequence_work
        validate_sequence_work(state)
        from .intake import validate_intake
        validate_intake(state)
        return {**state, "rounds": state.get("rounds", []), "assessments": state.get("assessments", []),
                "assessment_decisions": state.get("assessment_decisions", [])}
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise PersistenceError(f"Cannot read creation/state.json: {error}") from error


def reference_snapshot(root: Path, ids: list[str]) -> list[dict[str, Any]]:
    """Pin reference metadata and files, rejecting missing, altered or escaping files."""
    return _reference_snapshot(root, ids, {item["id"]: item for item in load_references(root)})


def _reference_snapshot(root: Path, ids: list[str], known: dict[str, dict]) -> list[dict[str, Any]]:
    if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids) or len(set(ids)) != len(ids):
        raise ValidationError("references must be a list of distinct reference ids")
    root = _root(root)
    result = []
    for ref_id in ids:
        ref = known.get(ref_id)
        if ref is None:
            raise ResourceNotFoundError(f"No reference {ref_id!r}")
        if any(item["severity"] == "error" for item in ref["findings"]):
            raise ValidationError(f"Reference {ref_id!r} has errors; inspect it before using it")
        folder = (root / "references" / ref_id).resolve()
        if not folder.is_relative_to(root):
            raise ValidationError(f"Reference {ref_id!r} is outside this production")
        for name in ref.get("files", {}):
            if not (folder / name).resolve().is_relative_to(folder):
                raise ValidationError(f"Reference file {name!r} escapes its record")
        files = {name: digest(folder / name) for name in ref["files"]}
        record = {**{key: value for key, value in ref.items() if key not in ("path", "findings")}, "files": files}
        result.append({"kind": "reference", "id": ref_id, "sha256": content_digest(record),
                       "title": ref.get("title", ""), "files": files})
    return result


def reference_catalog(root: Path, records: list[dict] | None = None) -> list[dict[str, Any]]:
    root = _root(root)
    result = []
    for item in load_references(root) if records is None else records:
        public = {key: value for key, value in item.items() if key != "path"}
        public["images"] = []
        folder = root / "references" / item["id"]
        for name in item.get("files", {}):
            path = (folder / name).resolve()
            if path.is_relative_to(root) and path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                public["images"].append(path.relative_to(root).as_posix())
        result.append(public)
    return result


def creation_view(root: Path) -> dict[str, Any]:
    from .read_scope import read_scope

    with read_scope():  # a dozen sub-views read the same production once (read-only)
        return _creation_view(root)


def _creation_view(root: Path) -> dict[str, Any]:
    state = load_creation(root)
    drafts = {draft["id"]: draft for draft in state["drafts"]}
    reference_records = load_references(root)
    known = {item["id"]: item for item in reference_records}
    snapshots = {}
    findings = []
    records = [*state["drafts"], *({"id": item["id"], "inputs": item["references"]} for item in state["rounds"])]
    for draft in records:
        for source in draft["inputs"]:
            if source["kind"] == "concept":
                original = drafts.get(source["id"])
                if original is None or content_digest(original) != source["sha256"]:
                    findings.append({"draft": draft["id"], "input": source["id"], "message": "Saved concept input missing or changed"})
            else:
                try:
                    if source["id"] not in snapshots:
                        snapshots[source["id"]] = _reference_snapshot(root, [source["id"]], known)[0]
                    current = snapshots[source["id"]]
                    changed = current["sha256"] != source["sha256"]
                except (ValidationError, ResourceNotFoundError):
                    changed = True
                if changed:
                    findings.append({"draft": draft["id"], "input": source["id"], "message": "Reference input missing or changed; the recorded version was retained"})
    from .creation_history import reference_history
    from .storyboard import load_storyboard
    from .creation_review import inception_review_view, inception_source_digest
    production = load_production(root)
    references = reference_catalog(root, reference_records)
    active_rounds = current_rounds(state["rounds"])
    try:
        source_digest = inception_source_digest(root, state)
    except (ValidationError, ResourceNotFoundError, OSError):
        source_digest = None  # inspection remains available; agent publication is unavailable
    from .art_direction import art_view
    from .directing import directing_view
    from .stage_handoff import handoff_view
    from .sequence_work import sequence_work_view
    from .intake import intake_view
    boards = load_storyboard(root)["candidates"]
    return {**state, "handoffs": handoff_view(root, state), "directing": directing_view(root, state), "art_direction": art_view(root, state, source_digest), "title": production["title"], "references": references, "findings": findings,
            "source_digest": source_digest,
            "sequence_work": sequence_work_view(root, state, production, material_digest=source_digest),
            "intake": intake_view(root, state, production),
            "inception_review": inception_review_view(root, state),
            "active_rounds": active_rounds,
            "reference_history": reference_history(references, state["drafts"], production.get("cast") or {}, active_rounds,
                                                   boards),
            # Which references are storyboard drawings, and of which shot: the Inception gallery files
            # them apart instead of in "Unassigned" (the director, Demo 01).
            "storyboard_uses": _storyboard_uses(boards, production)}


def _storyboard_uses(boards: list[dict], production: dict) -> dict[str, list[dict]]:
    order = {scene["id"]: index for index, scene in enumerate(production.get("scenes") or [])}
    uses: dict[str, list[dict]] = {}
    for board in boards:
        reference = (board.get("provenance") or {}).get("reference")  # the picture published as this drawing
        if reference:
            uses.setdefault(reference, []).append({"scene": board["scene"], "shot": board["shot"], "board": board["id"],
                                                   "version": board.get("version"), "order": order.get(board["scene"], 999)})
    return uses


def current_rounds(rounds: list[dict]) -> list[dict]:
    """Latest version of each filmmaker-defined round, in recorded follow-up order."""
    known = {item["id"]: item for item in rounds}
    current = {item.get("round_id", item["id"]): item for item in rounds}
    ordered, visited, visiting = [], set(), set()
    def visit(item):
        identity = item.get("round_id", item["id"])
        if identity in visiting:
            raise ValidationError("Round follow-up order contains a cycle")
        if identity in visited:
            return
        visiting.add(identity)
        previous = known.get(item["follows"])
        if previous:
            visit(current[previous.get("round_id", previous["id"])])
        visiting.remove(identity); visited.add(identity)
        ordered.append(item)
    for item in current.values():
        visit(item)
    return ordered


def save_creation_draft(root: Path, *, kind: str, title: str, text: str,
                        expected_revision: int, actor: Actor, references: list[str] | None = None,
                        based_on: str = "", concept: str = "", rationale: str = "",
                        expected_source_digest: str | None = None) -> dict[str, Any]:
    """Append a candidate, never write or approve the canonical screenplay."""
    if kind not in KINDS:
        raise ValidationError(f"kind must be one of {', '.join(KINDS)}")
    if not isinstance(title, str) or not title.strip() or len(title) > 240:
        raise ValidationError("A draft needs a title of at most 240 characters")
    if not isinstance(text, str) or not text.strip() or len(text.encode()) > MAX_TEXT_BYTES:
        raise ValidationError("A draft needs non-empty text, at most 1 MiB")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError("expected_revision must be a non-negative integer")
    if not isinstance(rationale, str) or len(rationale) > 2000:
        raise ValidationError("rationale must be text of at most 2000 characters")
    if not isinstance(based_on, str) or not isinstance(concept, str):
        raise ValidationError("based_on and concept must be draft ids")
    root = _root(root)
    with scene_lock(root):
        state = load_creation(root)
        if state["revision"] != expected_revision:
            raise RevisionConflictError(expected_revision, state["revision"])
        if expected_source_digest is not None:
            from .creation_review import inception_source_digest
            if expected_source_digest != inception_source_digest(root, state):
                raise ValidationError("Inception source material changed; reread it before saving a candidate")
        known = {item["id"]: item for item in state["drafts"]}
        if based_on and (based_on not in known or known[based_on]["kind"] != kind):
            raise ValidationError("based_on must name an existing candidate of the same kind")
        inputs = reference_snapshot(root, [] if references is None else references)
        if kind == "screenplay":
            source = known.get(concept)
            if source is None or source["kind"] != "concept":
                raise ValidationError("A screenplay handoff must name a saved concept version")
            inputs.insert(0, {"kind": "concept", "id": concept, "sha256": content_digest(source), "title": source["title"]})
            # The concept's reference selection is part of this handoff too.
            inherited = [item for item in source["inputs"] if item["kind"] == "reference"]
            for item in inherited:
                if reference_snapshot(root, [item["id"]])[0]["sha256"] != item["sha256"]:
                    raise ValidationError("The concept's reference input changed; save a reviewed concept version first")
                if not any(value["id"] == item["id"] for value in inputs):
                    inputs.append(item)
        elif concept:
            raise ValidationError("Only a screenplay draft consumes a concept")
        draft = {"id": "draft_" + uuid.uuid4().hex[:16], "kind": kind, "title": title.strip(),
                 "text": text, "based_on": based_on, "inputs": inputs, "created_at": now(),
                 "actor": actor.public_dict(), "rationale": rationale}
        committed = {**state, "revision": state["revision"] + 1, "drafts": [*state["drafts"], draft]}
        _commit(root, committed)
        append_event(root, Event.create("creation.draft_saved", state["project_id"],
                                      draft_id=draft["id"], revision=committed["revision"], actor=actor.public_dict()))
        return {"revision": committed["revision"], "draft": draft}


def _commit(root: Path, committed: dict[str, Any]) -> None:
    """Called only while holding the root lock and after checking the journal revision."""
    target = root / "creation" / "state.json"
    if not os.access(root, os.W_OK):
        raise PermissionDeniedError("The production is read only")
    if not target.parent.resolve().is_relative_to(root) or not target.resolve().is_relative_to(root):
        raise ValidationError("Creation journal must stay inside the production")
    temporary = None
    try:
        target.parent.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=".saving-", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(committed, handle, ensure_ascii=False, indent=2)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target)
    except OSError as error:
        if temporary and temporary.exists():
            temporary.unlink()
        raise PersistenceError(f"Could not save the creation record: {error}") from error


def save_exploration_round(root: Path, *, title: str, references: list[str], expected_revision: int,
                           actor: Actor, rationale: str, source: str, follows: str = "",
                           corrections: list[dict[str, str]] | None = None, based_on: str = "") -> dict[str, Any]:
    """Record a creative pass, not provider image inputs or an approval.

    Corrections name earlier/current artifacts explicitly. Neither a shared
    cast/style nor generation order authorizes inferring these relationships.
    """
    if not isinstance(title, str) or not title.strip() or len(title) > 240:
        raise ValidationError("A round needs a title of at most 240 characters")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError("expected_revision must be a non-negative integer")
    if (not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 4000
            or not isinstance(source, str) or not source.strip() or len(source) > 2000):
        raise ValidationError("Record the round's purpose and the source of that statement")
    if not isinstance(follows, str) or not isinstance(based_on, str) or not isinstance([] if corrections is None else corrections, list):
        raise ValidationError("follows must be a round id and corrections a list")
    root = _root(root)
    with scene_lock(root):
        state = load_creation(root)
        if state["revision"] != expected_revision:
            raise RevisionConflictError(expected_revision, state["revision"])
        selected = reference_snapshot(root, references)
        if not selected:
            raise ValidationError("A round needs at least one reference")
        previous = next((item for item in state["rounds"] if item["id"] == follows), None)
        if follows and previous is None:
            raise ResourceNotFoundError("No saved predecessor round with that id")
        earlier_version = next((item for item in state["rounds"] if item["id"] == based_on), None)
        if based_on and earlier_version is None:
            raise ResourceNotFoundError("No round version to revise with that id")
        if previous and earlier_version and previous.get("round_id", previous["id"]) == earlier_version.get("round_id", earlier_version["id"]):
            raise ValidationError("A round cannot follow itself")
        earlier = {item["id"] for item in previous["references"]} if previous else set()
        current = {item["id"] for item in selected}
        pairs = []
        for item in corrections or []:
            if (not isinstance(item, dict) or not isinstance(item.get("previous"), str)
                    or not isinstance(item.get("current"), str) or item["previous"] not in earlier
                    or item["current"] not in current or item["previous"] == item["current"]):
                raise ValidationError("Each correction must name a reference in the predecessor and one in this round")
            pair = {"previous": item["previous"], "current": item["current"]}
            if pair in pairs:
                raise ValidationError("Do not repeat a correction relation")
            pairs.append(pair)
        identity = "round_" + uuid.uuid4().hex[:16]
        round_ = {"id": identity, "round_id": earlier_version.get("round_id", earlier_version["id"]) if earlier_version else identity,
                  "based_on": based_on, "version": earlier_version.get("version", 1) + 1 if earlier_version else 1,
                  "title": title.strip(), "references": selected,
                  "follows": follows, "corrections": pairs, "rationale": rationale, "source": source,
                  "created_at": now(), "actor": actor.public_dict()}
        committed = {**state, "revision": state["revision"] + 1, "rounds": [*state["rounds"], round_]}
        current_rounds(committed["rounds"])
        _commit(root, committed)
        append_event(root, Event.create("creation.round_saved", state["project_id"], round_id=round_["id"],
                                      revision=committed["revision"], actor=actor.public_dict()))
        return {"revision": committed["revision"], "round": round_}
