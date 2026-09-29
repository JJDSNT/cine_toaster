---
id: CTX-DEVELOPMENT-ROADMAP
title: Development roadmap
type: roadmap
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-29
tags:
  - development
  - roadmap
  - milestones
---

# Development roadmap

This roadmap orders architectural risk. It is not a promise that every listed
technology will be adopted.

## Ordered plan from 2026-09-29

This is the working order agreed after the camera, cut, and canvas
investigation (`CT-0022` to `CT-0025`). It interleaves two tracks:

- **Film:** records and checks in the Core. This includes the screenplay,
  which is where scenes, dialogue, and action originate.
- **Stack:** React, LangGraph, and CopilotKit.

The rule behind the order: **records before interface, jobs before
orchestration, built-in workflow before an external orchestrator, and the
orchestrator before the agent UI that shares its state.** Each step names its
exit. "Decision" marks a step that ends in an ADR.

| # | Step | Track | Depends on | Exit |
| --- | --- | --- | --- | --- |
| 1 | ✅ **Screenplay coverage** (done 2026-09-29) ([`SPEC-0006`](../specs/SPEC-0006-screenplay-coverage.md), `CT-0021`). Parse Fountain with screenplay-tools (MIT; hands-on tested). Link each scene to its screenplay scene, and each shot to the elements it `covers` through text anchors. Every storyboard view then shows its dialogue and action. Checks cover uncovered dialogue, drift between authored lines and the screenplay, and missing or ambiguous anchors. `toast script link` proposes coverage for existing productions. The authored files are only read. | Film | none | SPEC-0006 acceptance met; the storyboard, Script room, and Dialogue room read coverage on the demo. |
| 2 | ✅ **Cut record** (done 2026-09-29) ([`SPEC-0007`](../specs/SPEC-0007-the-cut.md), `CT-0022` step 2). Specify and implement the cut between adjacent shots: cut type, frame chaining, exit versus entry state (SPEC-0005), and a catalog transition with a reason. Arcads' Clothing Brand Film shows the model: a shared storyboard frame *is* the cut. | Film | SPEC-0005 (done) | Spec accepted; cut findings in `toast check`; the Cut room shows the cut. |
| 3 | **Blocking frame** (`CT-0025` step 1). Render the camera's view from geometry, at a shot's start and end. | Film | SPEC-0005 | Frame shown beside the blockout; golden test on SC-030. |
| 4 | **Brief builder** (`CT-0022` step 3 follow-up). Derive a provider-neutral brief from records, in Auteur Script form, with every slot badged authored, derived, or missing. It also exports a SceneFlow project (JSON: brief text and take video), so SceneFlow's Timeline Anatomy can review Cine Toaster takes before we build our own. `[AUDIO]` and dialogue come from step 1. | Film | 2, 3, 1 | `toast brief <scene>`; brief preview in the scene room. |
| 5 | **Final Draft interchange spike** (`CT-0021`). Round-trip real `.fdx` files. Import produces a **new** authored `.fountain` file; export produces a derived `.fdx` that is never edited in place. Record what is lost: revisions, colours, tagging, page locks. **Decision:** the supported FDX subset and the role of FDX. | Film | 1 | Documented subset with loss report; decision recorded. |
| 6 | **Jobs runtime**: Phase 2 as written below. Operational store, an FFmpeg job with progress and cancellation, and job isolation across projects. | Film | none | The Phase 2 exit. Nothing generates or orchestrates before this. |
| 7 | **React stack spike and decision.** React 19 + TypeScript + Vite + `@xyflow/react` 12, in a separate `frontend/` package that talks only to the HTTP API. This is the choice four of six reference repositories made (`CT-0024`). The first room is the **canvas, read-only**: entity nodes (shots with the selected take, cast, looks), cut edges from step 2, and lineage focus. The vanilla UI stays until each room reaches parity. **Decision:** accept the Node/Vite toolchain (ADR). | Stack | 2, 6 | ADR accepted or rejected; canvas shows a real sequence. |
| 8 | **Screenplay editor** (`CT-0021`, writing). A React room that edits the **Fountain text itself**, with CodeMirror plus Fountain-aware behaviour. It never serializes the file from a parsed model, so comments, notes, and whitespace survive byte for byte. Every save runs through a `save_screenplay` command with a revision check and conflict reporting. Agents propose screenplay changes as diffs for a person to accept; they never write the file. **Decision:** amend ADR 0006, which today says authored screenplays are never rewritten. The amendment allows exactly this: a person editing text through a command that preserves every byte it was not asked to change. | Both | 1, 7 | ADR 0006 amendment accepted; an edit round-trips with a byte-exact diff test; the conflict test passes. |
| 9 | **Generation unit decision, then the first generation adapter and workflow template.** First decide whether one generation may hold several shots, with cut points inside the take (Vector Field; SPEC-0006 § Relation to SceneFlow). Then build one provider (ComfyUI or fal.ai) behind the provider adapter. One per-shot template: blocking frame → master image → image to video. Outputs become takes with lineage. | Film | 3, 4, 6 | A take generated from the project, with provenance. |
| 10 | **Built-in workflow with a human gate** (Phase 5 item). Run step 9's template as an explicit state machine that stops at "approve the master image". The gate is a production record. Show step nodes on the canvas, started through commands. | Both | 7, 9 | The Phase 5 workflow exit, visible on the canvas. |
| 11 | **LangGraph spike** (`CT-0023`). Run the *same* workflow and gate on LangGraph behind the `orchestration/` adapter. Compare persistence (checkpoints must be disposable operational state), gate interrupts written as records, cancellation, recovery, observability, and dependency cost as an optional extra. **Decision:** orchestrator (ADR). | Stack | 10 | ADR: adopt LangGraph as an adapter, or keep the built-in workflow. |
| 12 | **CopilotKit / CoAgents spike.** CoAgents connect a LangGraph agent's state to React UI through AG-UI: shared state, human-in-the-loop, and generative UI. In the step 7 stack, spike: an agent panel on the canvas scoped to the selected shot (SPEC-0001 threads); the step 10 gate rendered as an in-canvas approval; the agent proposing a graph (Arcads' "describe and it suggests the nodes") through commands; and screenplay suggestions as diffs in the step 8 editor. Compare with an MCP-only agent path (BeatDesign's model). If step 11 rejects LangGraph, spike CopilotKit over AG-UI against the built-in workflow instead. **Decision:** agent UI protocol (ADR). | Stack | 7, 10, 11 | ADR on CopilotKit/CoAgents versus MCP-only. |
| 13 | **Canvas becomes editable.** Edit cuts, references, and workflow steps through commands. Agent-proposed graphs are accepted or rejected as decisions. Decide where card positions live (`CT-0024` finding 5): auto-layout or disposable operational layout. | Both | 7, 12 | Every canvas edit is a command, with conflict tests across the GUI, CLI, and agent. |
| 14 | **Tauri shell** (Phase 3 remainder). | Stack | 7 | The Phase 3 exit. |

Why this order: screenplay coverage comes first because it depends on nothing
and everything downstream reads it: the storyboard, the brief, SceneFlow
review, and dialogue in generation. The cut record and the blocking frame
complete the per-shot records the canvas and generation consume. The stack
arrives when there is real data to show, and agents arrive when there is a
real workflow to join. Step 5 has no interface dependency and may be pulled
forward at any time.

Unchanged and not scheduled: the Okay Wannabe review (`CT-0020`),
frame-accurate playback, and MLT/Kdenlive. First-hand verification of Arcads
(`CT-0024`) is due whenever the web is available.

## Phase 0 — foundation

Status: in progress under `CT-0001`.

- Consolidate architecture, state authority, agent boundaries, and process
  topology.
- Establish `ai-context/` as the English-language project memory and tracker.
- Preserve and document the working read-only Python prototype.

Exit: contributors can identify current behavior, accepted decisions, active
work, and the next vertical slice without relying on chat history.

## Phase 1 — first canonical decision

Status: delivered under `CT-0002`. Scene geometry, continuity checks,
sequences, and the live board followed under `CT-0008`.

- Introduce concrete take candidates for a reviewable shot.
- Implement `select_take` through one application command.
- Add atomic persistence, revisions, typed errors, and a post-commit event.
- Expose the command through CLI, HTTP, and the existing review UI.
- Record selection as a durable creative decision.

Exit: met. GUI, CLI, and API commit through one command, with conflict and
failure tests across interfaces.

One deviation from the original plan: the command writes a runtime-owned
`state.json` rather than the authored `scene.toml`
([`ADR 0006`](../../docs/architecture/0006-authored-and-runtime-files.md)).

## Phase 2 — application runtime and jobs

- Use The Last Signal and Amiga Demo Reel as independent fixtures for Project
  Manager identity, active-project switching, and job isolation tests.
- Extend the initial local Project Manager with a durable operational registry,
  explicit relocation, and per-interface active-project selection.
- Add a durable operational store outside project directories.
- Implement a minimal FFmpeg job with progress, cancellation, reconciliation,
  and explicit result staging/adoption.
- Prove a Project A job continues while Project B is active.

Exit: background work survives navigation and renderer lifecycle according to
the documented job contract.

Foundation already delivered: local project locators, direct external-directory
materialization, simultaneous in-memory registration, idempotent reopen, stable
manifest identity after movement, and duplicate-ID conflict detection.

## Phase 3 — React and desktop shell

- Spike React/TypeScript/Vite against the versioned Application API.
- Migrate one production room at a time with behavior parity.
- Spike Tauri supervision of the headless runtime and constrained native
  capabilities.
- Keep browser-mode development and tests available.

Exit: the desktop shell can open a project, supervise the runtime, observe jobs,
and recover from renderer reload without owning domain logic.

## Phase 4 — preview and comparison

Partly delivered ahead of order, because take selection is meaningless without
something to look at. Side-by-side comparison with grouped play, pause, restart,
and mute, plus per-take preview on hover, works today against real media served
with range requests.

Remaining:

- a proxy strategy for large source media;
- measured linked playback: seek, frame stepping, synchronization error;
- choose the simplest playback stack that meets the measured requirement.

Nothing here is frame-accurate and it must not be described as such until a
spike measures it against known media and timecode.

Exit: met for comparison and selection; open for frame-accurate playback.

## Phase 5 — first production agent

- Define tool schemas over existing queries and commands.
- Spike AG-UI and CopilotKit without making either a Core dependency.
- Implement scoped Cine Toaster agent threads and provider session bindings
  according to
  [`SPEC-0001`](../specs/SPEC-0001-agent-session-binding.md).
- Add `Follow Agent` navigation preference.
- Implement a small built-in workflow ending at a real human gate.

Exit: an agent can analyze a scene, present alternatives, request a canonical
decision, and continue from the committed result without bypassing permissions.

## Later evaluation

- Okay Wannabe's production-stage UI (`CT-0020`). The node editor is now
  steps 5, 7, and 10 of the ordered plan;
- ComfyUI local and remote generation adapters;
- Fountain screenplay editing and Final Draft FDX interchange (`CT-0021`);
- ADK or orchestrators other than LangGraph (LangGraph is scheduled as step 8
  of the ordered plan);
- MLT/Kdenlive exchange and timeline integration;
- detached workers and execution across full application exit or machine
  restart;
- professional frame-accurate comparison if product requirements justify it.
