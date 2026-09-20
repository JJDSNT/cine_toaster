# Milestone 02: Canonical take selection

Status: delivered. Implementation and validation are recorded in
[`CT-0002`](../ai-context/work/CT-0002-canonical-take-selection.md). One
acceptance criterion changed during delivery: the command writes a
runtime-owned `state.json` rather than the authored `scene.toml`, for the
reasons in [`ADR 0006`](architecture/0006-authored-and-runtime-files.md).

The second milestone introduces Cine Toaster's first production-state write. A
filmmaker compares registered alternatives for a shot and selects one take. The
same operation is available through Core, CLI, HTTP, and the existing review UI.

This milestone establishes how every future human or agent action changes a
filesystem-authoritative production.

## User outcome

From a scene awaiting review, a filmmaker can:

1. open a shot and see its concrete take candidates;
2. preview enough metadata or media to distinguish them;
3. select a take;
4. see the shot and review queue update;
5. reopen the project and find the same selection and decision history;
6. receive a clear conflict instead of silently overwriting a newer choice.

## Domain outcome

The implementation introduces one shared command:

```text
select_take(
  project_id,
  scene_id,
  shot_id,
  take_id,
  expected_revision,
  actor,
  rationale?
)
```

The exact language-level shape may evolve. Its semantics may not be redefined by
an interface adapter.

A successful selection atomically records:

- the selected take on the shot;
- a new revision;
- a durable creative decision with actor and timestamp;
- the prior selection when one is superseded;
- an event emitted after the filesystem commit.

## Small schema evolution

The current demo records only a take count. This milestone adds concrete take
identities and references with the smallest schema sufficient for comparison.
It does not design the complete future asset or generation schema.

Provider-specific provenance may be preserved in a namespaced envelope, but
selection behavior does not depend on ComfyUI or another generator.

## Delivery order

1. Add fixtures and parsing for concrete take candidates and revisions.
2. Implement typed command, result, and error contracts.
3. Implement domain validation and atomic persistence.
4. Record selection history and publish a post-commit event.
5. Add `toast take select` using the shared command.
6. Add an HTTP command endpoint using the shared command.
7. Add selection to the existing review UI.
8. Add parity and failure tests across interfaces.

## Acceptance criteria

- Project, scene, shot, and take relationships are validated.
- A stale expected revision returns a conflict and changes no file.
- A failed write leaves the previous canonical file readable and unchanged.
- An event is never emitted for a failed command.
- Repeating or superseding a selection has documented behavior.
- Unrelated scene data is preserved.
- The disposable SQLite index is not used as write authority.
- CLI and HTTP produce the same committed domain result.
- Reloading the control room reflects the committed selection.
- The complete repository test suite passes.

## Explicitly deferred

- React or Tauri migration;
- real generation through ComfyUI;
- frame-accurate synchronized playback;
- global background jobs;
- agent tool invocation;
- generalized TOML or project metadata editing;
- multi-user collaboration and distributed locks.

## Execution tracking

Live work, completed steps, remaining work, decisions, and validation are kept
in `ai-context/work/CT-0002-canonical-take-selection.md`.
