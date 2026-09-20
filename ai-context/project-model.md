---
id: CTX-PROJECT-MODEL
title: Project model
type: architecture
status: accepted
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - project-core
  - filesystem
  - domain-model
---

# Project model

## Scope

The Project Core represents and changes one film production. The Application
Layer manages one or more open projects and the infrastructure around them.

```text
Application
  Project Manager | Jobs | Resources | Agent Runtime | Preferences
                         |
Project Core
  Project | Script | Scene | Shot | Take | Asset | Prompt
  Decision | Human Gate | Workflow | Render
```

Application state is not production truth. A project remains understandable and
portable without the Cine Toaster application database or caches.

## Identity

- `project.toml` declares a stable project ID and schema version.
- A project ID identifies the production after its directory is moved.
- File paths locate project content but are not project identity.
- Entity IDs are stable within a project and must not depend on display labels
  or array positions.
- Every application job, agent session, event, and resource reference carries
  explicit project identity.

## Current filesystem format

```text
project/
  project.toml
  story/screenplay.fountain
  world/characters/
  world/locations/
  scenes/<scene>/scene.toml
  assets/
  workflows/
  renders/
  edit/
```

The current implementation stores workflow, shot summaries, decisions,
blockers, and iteration summaries in one `scene.toml` per scene. This is a valid
small-project format and should evolve through schema versions rather than a
blind directory migration.

Large media remains in ordinary files. Canonical metadata records which media
belongs to the production and why it was selected.

## Canonical production state

Canonical state includes:

- screenplay and scene content;
- scene and shot structure;
- takes and registered assets;
- selected alternatives;
- creative decisions and their rationale;
- human-gate outcomes;
- workflow state that determines what may happen next;
- artifact provenance needed to understand or reproduce an output;
- final render and edit references.

The absence of an application cache must not make any of these unknowable.

## Operational state

Operational state includes indexes, thumbnails, recent-project lists, window
layout, logs, process handles, job recovery metadata, and agent session handles.
It normally lives in platform application data/cache locations keyed by project
ID, not in a shared production directory.

Agent continuity uses Cine Toaster-owned threads and replaceable provider session
bindings. Both remain operational state. Their isolation, context scope, and
resume behavior are defined in
[`SPEC-0001`](specs/SPEC-0001-agent-session-binding.md).

Deleting operational state may lose convenience, execution history, or the
ability to resume an interrupted operation. It must not delete selected takes,
approvals, decisions, or other production truth.

## Commands are the write boundary

No GUI component, HTTP handler, CLI parser, provider adapter, or agent tool may
write canonical TOML directly. They invoke application commands that delegate
to the Project Core.

A command contains:

- command type and unique command ID;
- target project and resource IDs;
- validated intent payload;
- actor identity and actor type;
- expected revision when updating existing state;
- correlation and causation IDs where applicable;
- timestamp supplied or normalized by the application boundary.

A successful command:

1. loads and validates current canonical state;
2. checks preconditions and expected revision;
3. computes the domain change;
4. writes atomically using a temporary sibling and replace operation;
5. reloads or verifies the committed representation;
6. emits the resulting event after commit;
7. returns the new revision and affected resource.

Failures must be typed enough to distinguish validation, missing resources,
revision conflicts, permissions, I/O failure, and provider failure.

## Revisions and concurrency

Filesystem authority does not eliminate concurrent writers. Project mutations
must use optimistic revisions or an equivalent explicit conflict mechanism.
Last-writer-wins is not acceptable for creative decisions.

The first implementation may serialize writes within one runtime and use a
manifest or scene revision. The persisted revision remains the final conflict
check so CLI or multiple application instances cannot silently overwrite newer
state.

Multi-user collaborative editing, distributed locks, and merge resolution are
not required for the first write milestone.

## Takes, alternatives, and selection

Generated outputs are candidates until explicitly adopted. A take selection is
a canonical creative decision, not an application preference.

`select_take` must validate:

- the project, scene, shot, and take exist;
- the take belongs to the target shot;
- the take is eligible for selection;
- the expected scene or shot revision still matches;
- the actor is allowed to make the decision.

The committed state records at least the selected take, decision identity,
actor, timestamp, previous selection if any, and optional rationale. Selecting
a different take creates a new decision or superseding record; it must not erase
the historical fact without an explicit retention policy.

The existing demo uses take counts rather than concrete take entities. The next
milestone must introduce the smallest concrete representation required for real
comparison and selection.

## Human gates

A human gate is durable workflow state with:

- stable gate and subject IDs;
- gate kind and required decision;
- state such as waiting, review-required, approved, rejected, or
  changes-requested;
- requester and decision actor;
- timestamps, rationale, and evidence/resource references;
- revision and relationship to the workflow step.

Chat messages may explain or request a gate decision, but they are not the gate
record. Security permission prompts for shell, filesystem, or network access are
also distinct from creative human gates.

## Provenance

Provider independence must not destroy reproducibility. Canonical artifacts may
store a provider-neutral provenance envelope plus namespaced provider data such
as model, seed, workflow digest, software version, and generation parameters.

The Core preserves this data and common fields but does not implement ComfyUI,
Claude, Codex, or FFmpeg semantics. The responsible adapter creates and
interprets its namespaced portion.

## Schema evolution

- Every canonical manifest has a schema version.
- Readers reject unsupported future versions clearly.
- Migrations are explicit, testable, and preserve a recoverable original.
- A migration never relies on a disposable index as input authority.
- New fields should be optional until fixtures and migration behavior exist.

Do not design the final schema for every filmmaking department up front. Add
concepts through real vertical slices and keep their invariants explicit.
