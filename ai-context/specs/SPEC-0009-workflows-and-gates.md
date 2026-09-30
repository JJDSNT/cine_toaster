---
id: SPEC-0009
title: Workflows and human gates — the built-in state machine that stops for a person
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - workflow
  - gates
  - decisions
  - generation
---

# Goal

Plan step 10: run the generation template (master picture → video → takes)
as an explicit state machine that **stops at a human gate**, "approve the
master picture". The gate is a production record. `project-model.md` §
Human gates defines what a gate holds; this specification says where it
lives and how a workflow moves.

The first template exists because of a measured failure. On SINGULAR 1-02A
mA, the edge score passed a picture in which Claire's head had moved away
from where the render put it (knowledge `qwen-image-edit`,
`edge-score-misses-a-moved-subject`). Only a person catches that, so a
picture is animated only after a person has approved it.

# Records

Both live in the scene's `state.json`, beside the authored files (ADR 0006),
with the scene's revision. They are production truth. The job store stays
disposable: a workflow run records the jobs it started, and it can be
understood without them.

**Gate**

- `id`, `kind` (`approve_picture`), `subject` (the shot whose picture it
  is), and `workflow` plus `step` (the run and step that opened it);
- `state`: `waiting`, then `approved`, `changes_requested` or `rejected`;
- `candidates`: the picture versions offered, as project-relative paths;
- `chosen`: the approved path;
- `requested_at` and `requested_by`; `decided_at`, `decided_by` (an actor:
  human, agent or system) and `rationale`;
- `reasons`, for a refusal: what is wrong, from a closed list
  (`subject_moved`, `identity`, `geometry`, `light`, `detail_lost`,
  `anatomy`, `other`).

A rationale is optional when approving. Asking for another version or
rejecting **requires** a rationale or at least one reason: that is what the
next version has to fix, and what later analysis learns from (CT-0041).

A decided gate is never rewritten. Asking again opens a new gate.

**Workflow run**

- `id`, `template`, `subject` (`{scene, block}`), `state` (`running`,
  `waiting`, `done`, `failed`, `cancelled`), and `created_at` /
  `updated_at`;
- `steps`, in order. Each step has an `id`, a `kind` (`picture`, `gate`,
  `generate`, `slice`), a `state` (`pending`, `running`, `waiting`, `done`,
  `skipped`, `failed`), its `job` or `gate`, its `outputs`, and a `note`.

**Approved pictures.** The approved gate for a shot is its canonical picture.
Nothing is copied or renamed. `reference_picture` prefers the approved
version of the shot, or of the master it is made from, over `p<n>.png`.
Everything downstream (generation plans, slicing, briefs) follows the
approval without being told.

# Template `block` (the first)

For one generation block of a scene:

1. For each master picture the block's shots are made from (their own
   `derive`, or the `from` shot that has one), in order:
   - a **picture** step. It is `skipped` when a version already exists;
     otherwise it runs `derive_picture` (paid, budget-checked).
   - a **gate** step, `approve_picture`, offering every version. It is
     `skipped` when an approved gate for that picture already exists.
2. A **generate** step: `generate_block` (paid, budget-checked). Its plan
   uses the approved pictures.
3. A **slice** step: `slice_block` on the version just generated.
4. `done`. The shots now have new takes; choosing one is the existing
   `select_take` decision.

# Movement

`advance(run)` is idempotent. It looks at the current step:

- If the step's job is not started, it submits it.
- If the job succeeded, it adopts the result, records the outputs and moves
  on.
- If the job failed or was cancelled, the step and the run fail.
- For a gate step, it opens the gate and the run waits.

Three things call it: `start_workflow`, the gate decision, and the Job
Manager's completion listener for jobs the run started. The runtime that
owns the jobs moves the workflow; nothing polls.

**Gate decisions** (`decide_gate`, a command like every other mutation):

- `approved` with `chosen` (one of the candidates): the run continues.
- `changes_requested`: a new picture version is made (the next seed), and a
  new gate offers all versions.
- `rejected`: the run is `cancelled`.

A decision carries `expected_revision`. A stale decision is refused, as
every scene command is.

# Interfaces

- **CLI.** `toast workflow start <project> <scene> <block>`,
  `toast workflow list`, and `toast gate decide … --approve <path> |
  --changes | --reject`.
- **Commands.** `start_workflow`, `decide_gate` and `cancel_workflow`,
  through `dispatch`, for the GUI, CLI and agents alike.
- **Control room.** The scene room shows each run's steps and states. A
  waiting gate shows its candidate pictures side by side, each with what it
  was made from, and Approve / Ask for another / Reject with a rationale.
- **Canvas.** Each run appears as step nodes beside its block, with the
  gate highlighted while it waits.

# Out of scope here

- Authoring templates in the project. Templates are built in until plan
  step 11 (LangGraph) decides the orchestrator.
- Gates other than `approve_picture` and `approve_storyboard`.
  - The phase gate (added 2026-09-30) is decided by a person in one act,
    `approve_storyboard` or `reopen_storyboard`, with the breakdown's
    digest.
  - The scene payload's `phase` says `fitting` or `production`, and
    whether the breakdown changed since the approval.
- Agents deciding gates. The record allows an agent actor, but granting that
  permission is SPEC-0001's concern.
