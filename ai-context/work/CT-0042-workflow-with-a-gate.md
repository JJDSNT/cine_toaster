---
id: CT-0042
title: Plan step 10 — the built-in workflow with a human gate (SPEC-0009)
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - workflow
  - gates
  - generation
---

# What

The generation template (master picture → video → takes) runs as an
explicit state machine that stops at "approve the master picture". The gate
is a production record. Specification: SPEC-0009.

# Why

On SINGULAR 1-02A mA, the edge score passed a picture in which Claire's head
had moved from where the render put it. Only a person catches that, so the
video is made only from a picture a person approved.

# Done

- **State.** `SceneState` holds `gates` and `workflows` (schema v3; v2
  files still read).
  - `approved_pictures()` gives each shot's latest approved picture.
  - `with_progress` bumps the revision for machine steps without adding
    history entries. Only human acts are decisions.
- **Approved pictures are canonical.** Each shot carries `approved_picture`
  in the scene payload. `blocks.reference_picture` prefers it, for the shot
  and for the master it is made from. Generation plans, slicing and briefs
  follow.
- **`workflows.py`.** Template `block`:
  - one picture step and one gate per master the block uses (its own
    `derive`, or its `from` shot's);
  - then generate, then slice.
  - A picture step is skipped when a version exists. A gate is skipped when
    that picture is already approved.
  - `advance` is idempotent. `changes_requested` makes a new version with
    the next seed and asks again; `rejected` cancels the run.
  - Per-scene locks.
  - Stale decisions are refused (`expected_revision`).
- **Movement without polling.** `JobManager.listeners` are called when any
  job finishes. `workflows.attach(manager)` is used by the server, lazily
  for commands, and by the CLI.
- **Commands** through `dispatch`: `start_workflow`, `decide_gate`,
  `cancel_workflow` and `resume_workflow`.
- **Reasons on refusals** (the user's question, 2026-09-29). All three
  outcomes had accepted a rationale, but none required one, and the UI made
  it look like approval only. Now:
  - asking for another version or rejecting requires a rationale or a
    reason from a closed list (`subject_moved`, `identity`, `geometry`,
    `light`, `detail_lost`, `anatomy`, `other`);
  - approving takes an optional one.
  - This is the data CT-0041 (learning from gate decisions) needs.
- **CLI.** `toast workflow start|list|resume|cancel` and `toast gate decide
  --approve|--changes|--reject [--reason …] [--why …]`. The CLI stays alive
  while jobs run and prints the gate's candidates when the run waits.
- **Control room.** The scene room has a **Workflow** panel with start
  buttons, runs and their steps, the waiting gate (render plus candidates
  with "What was sent", reason checkboxes, the why field, and the three
  decisions), and cancel.
- **Canvas.** The latest run per block is a card under the scene header,
  linked to the block's first shot, highlighted while waiting. The details
  panel links to the scene room.
- **Canvas pictures.** Masters show their approved or own picture, and
  renders show their blockout file as a blocking frame (`production_graph`
  takes the project root).
- **Docs.** `docs/workflows.md` and SPEC-0009.

# Validation

- `tests/test_workflows.py` (3 tests, with fake editor and video endpoints)
  covers:
  - the full run: picture, ask again, stale and invalid decisions refused,
    approve, generate guided by the approved picture, slice, done, with a
    decision history of exactly start and two decisions;
  - rejection, which requires a reason;
  - an existing picture going straight to the gate, and one run per block.
- `tests/test_graph.py` covers run nodes. The frontend layout test covers
  run cards; the frontend has 11 tests.
- Full suite: 416 OK.
- **SINGULAR copy, through the running server and the GUI.** 1-02A block 2
  started, and mB's picture step was skipped (pmB exists). The gate showed
  the render and pmB. Approving through the GUI recorded the decision with
  its rationale, and the run moved on by itself to mA's gate, which offers
  pmA and pmA-1.
  - That mB approval was a technical test by the development agent,
    recorded in the copy with the actor `control-room`, choosing the
    picture SINGULAR's own `b2` used. The mA choice was left to the author.
    Nothing was spent.
- Canvas screenshots show the run card and the new master and render
  pictures.

# Remaining

- ~~The phase gate "storyboard approved"~~ done 2026-09-30:
  `approve_storyboard` / `reopen_storyboard` (a person only), the scene
  payload's `phase`, the scene room's phase line, `toast storyboard`, and
  the assistant's digest.
- ~~Feeding a refusal's reasons into the next attempt~~ done 2026-09-30
  (CT-0041 option 1).
- Templates for a single shot outside a block.
- Plan step 11: the same workflow on LangGraph behind `orchestration/`.
