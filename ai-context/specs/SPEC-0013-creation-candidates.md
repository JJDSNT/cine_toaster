---
id: SPEC-0013
title: Creation candidates and explicit upstream inputs
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
---

# Contract

Creation / Inception precedes screenplay development without adding a mandatory
gate to imported films. It produces concept and screenplay candidates, not
canonical screenplay edits or storyboard approvals (ADR 0026, CT-0105).

`creation/state.json` belongs to the production. Schema 1 contains project ID,
monotonic revision and a candidate list. A save requires an expected journal
revision and records stable ID, kind, title, text, timestamp, actor, rationale,
same-kind predecessor and selected upstream inputs. Saves append full versions
under one root lock and atomic replace. Invalid, missing or conflicting inputs
refuse without changing the committed journal. A corrupt journal is not empty.

A screenplay candidate must consume a saved concept version. Its references
are inherited, with optional additional reference inputs. Inputs pin the saved
concept's full-record digest or a reference's metadata/files digest. A new
concept version or image does not replace an existing candidate's inputs.
Missing/changed input content produces findings; a changed inherited reference
must be reviewed in a new concept candidate before handoff. This records
declared creative direction, not evidence of past provider execution.

The journal also appends immutable exploration-round records: selected pinned
references, title, purpose/rationale, source of the statement, actor, timestamp,
predecessor round and explicit previous/current correction pairs. Both sides
must belong to the named rounds. Corrective intent is not proof of success,
approval, replacement or a provider image-input relationship. Reuse and cast
designations are derived separately from existing records; absent approvals
remain "not recorded", never an inferred pending/rejected/approved decision.

Round names, membership, order and count belong to the film. They are not
provider stages or built-in labels. A revised round retains stable `round_id`,
records `based_on` and appends a version; prior versions remain in `rounds`.
`active_rounds` selects current group versions in recorded follow-up order;
cyclical order is refused. The GUI groups images accordingly, keeps unassigned
references visible and collapses history/provenance by default. Demo-specific
group labels must not leak into generic grouping logic.

GUI, CLI and MCP invoke the same application operation. Browser state, chat,
events and SQLite jobs are not required to recover saved candidates or lineage.
Director clarification in CT-0106 makes the GUI a human situational view:
manual candidate/round/generation forms are removed; agents continue authoring
through these shared operations. The GUI inspects saved candidates, compares
results, traces known uses and displays actual reviewable job results. It is
not an agent-operated form surface, and missing creative gates are not faked.
No candidate operation edits `project.yaml`, scene manifests or the canonical
Fountain screenplay. Explicit promotion and candidate-specific scene/shot
coverage are outside this first slice.

# Exploratory images

## Inception assessment and human direction (CT-0107; ADR 0028)

Schema-1 journals additionally retain `assessments` and `assessment_decisions`;
missing lists in old journals mean empty, not inferred approvals. Agents author
readiness per destination (`screenplay`, `storyboard`, `masters`) as `ready`,
`needs_work` or `not_assessed`, with an explanation and actionable gaps naming
an agent/human owner. One proposal states its destination, question, scope,
rationale and next step. Image count does not determine creative sufficiency.

The assessment pins selected references, canonical screenplay hashes, retained
storyboard records/image hashes and relevant creative context. A later change
requires reassessment; earlier records stay readable. Only a human decides
`approved` or `changes_requested`, with non-empty guidance required for changes.
The decision names the exact latest assessment and expected journal revision;
superseded/already-decided/stale requests are refused. Shared root-lock/atomic
commit behavior applies. MCP authors but cannot decide; GUI/CLI/HTTP decisions
use the same human command.

Approval adopts a development direction, not a completed storyboard or master.
No authored film file, cast reference or scene gate is changed. The next agent
instruction is retained as `not_dispatched`; automatic execution/continuation
remains outside this first slice. The GUI shows the assessment and two decision
actions, with a direction field only when the person requests changes.

CT-0108 / SPEC-0015 add interactive continuation through the existing CoAgent
after a saved human direction. Its canonical ID and current material are
rechecked; no new production instruction is silently considered a running job.
Agent publications may supply `expected_source_digest`, which must match the
whole source set read in addition to the expected journal revision. This protects
against external screenplay/reference/storyboard changes during reasoning.

## Image generation lifecycle

Use the existing reference format and generation adapter behind jobs. Planning
shows the effective provider instruction, selected saved concept/references,
their digests, binary availability and subscription quota (USD unknown).
Generation requires explicit quota consent and rechecks pinned inputs before
submission and execution. Working reference copies, logs and images remain in
job staging until inspected and explicitly adopted. Cancellation terminates
the owned provider process group. Adoption adds a unique reference; overwrite
is forbidden for this job kind. No image constitutes a storyboard approval.

# Acceptance

- Save/reopen successive concepts without changing an earlier candidate.
- Consume an exact concept/reference set in a screenplay candidate and trace
  back through GUI, CLI and MCP; keep the canonical screenplay unchanged.
- Competing writers cannot both commit against the same expected revision.
- Failed journal replacement retains the previous readable version.
- Changed/missing input content is visible, never silently substituted.
- Inspect quota/prompt/inputs before generating; inspect a staged result before
  adoption; older reference files remain byte-identical.
- Saved artifacts and comparison remain available with the assistant disabled;
  agent-facing candidate commands remain independent of the GUI.
- Verify browser preservation/conflict behavior on a disposable film; inspect
  real Demo 01 references read-only. Fake generation tests establish the
  lifecycle, not provider authentication or artistic quality.
