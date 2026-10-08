---
id: CTX-DEVELOPMENT-ROADMAP
title: Development roadmap
type: roadmap
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-10-07
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
| 3 | ✅ **Blocking frame** (done 2026-09-29) (`CT-0025` step 1). Render the camera's view from geometry, at a shot's start and end. | Film | SPEC-0005 | Frame shown beside the blockout; golden test on SC-030. |
| 4 | ✅ **Brief builder** (done 2026-09-29; review on local video, not YouTube) (`CT-0022` step 3 follow-up). Derive a provider-neutral brief from records, in Auteur Script form, with every slot badged authored, derived, or missing. It also exports a SceneFlow project (JSON: brief text and take video), so SceneFlow's Timeline Anatomy can review Cine Toaster takes before we build our own. `[AUDIO]` and dialogue come from step 1. | Film | 2, 3, 1 | `toast brief <scene>`; brief preview in the scene room. |
| 4b | ✅ **Light previs** (done 2026-09-29) (`CT-0029` stage 1). Animate the blocking frame over the shot: camera and subjects interpolated between declared positions, speed respected. | Film | 3 | Shot plays beside the blockout; interpolation tested on SC-030 P2. |
| 5 | ✅ **Final Draft interchange spike** (done 2026-09-29, ADR 0014) (`CT-0021`). Round-trip real `.fdx` files. Import produces a **new** authored `.fountain` file; export produces a derived `.fdx` that is never edited in place. Record what is lost: revisions, colours, tagging, page locks. **Decision:** the supported FDX subset and the role of FDX. | Film | 1 | Documented subset with loss report; decision recorded. |
| 6 | ✅ **Jobs runtime** (done 2026-09-29, SPEC-0008): Phase 2 as written below. Operational store, an FFmpeg job with progress and cancellation, and job isolation across projects. | Film | none | The Phase 2 exit. Nothing generates or orchestrates before this. |
| 7 | ✅ **React stack spike and decision.** (done 2026-09-29, ADR 0015) React 19 + TypeScript + Vite + `@xyflow/react` 12, in a separate `frontend/` package that talks only to the HTTP API. This is the choice four of six reference repositories made (`CT-0024`). The first room is the **canvas, read-only**: entity nodes (shots with the selected take, cast, looks), cut edges from step 2, and lineage focus. The vanilla UI stays until each room reaches parity. **Decision:** accept the Node/Vite toolchain (ADR). | Stack | 2, 6 | ADR accepted or rejected; canvas shows a real sequence. |
| 8 | ✅ **Screenplay editor** (done 2026-09-29, ADR 0016) (`CT-0021`, writing). A React room that edits the **Fountain text itself**, with CodeMirror plus Fountain-aware behaviour. It never serializes the file from a parsed model, so comments, notes, and whitespace survive byte for byte. Every save runs through a `save_screenplay` command with a revision check and conflict reporting. Agents propose screenplay changes as diffs for a person to accept; they never write the file. **Decision:** amend ADR 0006, which today says authored screenplays are never rewritten. The amendment allows exactly this: a person editing text through a command that preserves every byte it was not asked to change. | Both | 1, 7 | ADR 0006 amendment accepted; an edit round-trips with a byte-exact diff test; the conflict test passes. |
| 9 | ✅ **Generation unit decision, then the first generation adapter and workflow template.** (done 2026-09-29, CT-0037: blocks, `toast generate` within a budget, master pictures by `derive`, slicing into takes with lineage) First decide whether one generation may hold several shots, with cut points inside the take (Vector Field; SPEC-0006 § Relation to SceneFlow). Then build one provider (ComfyUI or fal.ai) behind the provider adapter. One per-shot template: blocking frame → master image → image to video. Outputs become takes with lineage. | Film | 3, 4, 6 | A take generated from the project, with provenance. |
| 10 | ✅ **Built-in workflow with a human gate** (done 2026-09-29, SPEC-0009, CT-0042) (Phase 5 item). Run step 9's template as an explicit state machine that stops at "approve the master image". The gate is a production record. Show step nodes on the canvas, started through commands. | Both | 7, 9 | The Phase 5 workflow exit, visible on the canvas. |
| 11 | ✅ **LangGraph spike** (done 2026-09-29, ADR 0017, CT-0043: production workflows stay built in; LangGraph runs agents; CoAgents path proven with a CLI model) (`CT-0023`). Run the *same* workflow and gate on LangGraph behind the `orchestration/` adapter. Compare persistence (checkpoints must be disposable operational state), gate interrupts written as records, cancellation, recovery, observability, and dependency cost as an optional extra. **Decision:** orchestrator (ADR). | Stack | 10 | ADR: adopt LangGraph as an adapter, or keep the built-in workflow. |
| 12 | ✅ **CopilotKit / CoAgents spike.** (done 2026-09-29, ADR 0018, CT-0044: the assistant beside the canvas, `toast serve --assistant`) CoAgents connect a LangGraph agent's state to React UI through AG-UI: shared state, human-in-the-loop, and generative UI. In the step 7 stack, spike: an agent panel on the canvas scoped to the selected shot (SPEC-0001 threads); the step 10 gate rendered as an in-canvas approval; the agent proposing a graph (Arcads' "describe and it suggests the nodes") through commands; and screenplay suggestions as diffs in the step 8 editor. Compare with an MCP-only agent path (BeatDesign's model). If step 11 rejects LangGraph, spike CopilotKit over AG-UI against the built-in workflow instead. **Decision:** agent UI protocol (ADR). | Stack | 7, 10, 11 | ADR on CopilotKit/CoAgents versus MCP-only. |

Pre-check for steps 7 and 12 (`CT-0033`, 2026-09-29): CopilotKit 1.75 (v2 API) works with React 19, Vite and React Flow 12 against a Python AG-UI agent. The direct browser-to-Python path is an enterprise-tier feature. The open path adds the self-hosted Node Copilot Runtime, whose telemetry is on by default.
| 13 | ✅ **Canvas becomes editable.** (done 2026-09-30, CT-0046: cuts and references decided over the breakdown, workflows started, positions computed) Edit cuts, references, and workflow steps through commands. Agent-proposed graphs are accepted or rejected as decisions. Decide where card positions live (`CT-0024` finding 5): auto-layout or disposable operational layout. | Both | 7, 12 | Every canvas edit is a command, with conflict tests across the GUI, CLI, and agent. |
| 14 | ~~**Tauri shell**~~ — cancelled 2026-09-30 by the user (ADR 0019): Cine Toaster runs in the browser, served by its local runtime. | Stack | — | — |
Inserted between steps 2 and 3 at the user's request (2026-09-29, done): gl-transitions as the catalog's shader bank, and builds that run a transition's own shader (`CT-0026`).

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
- (Cancelled, ADR 0019.) Spike Tauri supervision of the headless runtime and constrained native
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

## Backlog after the close-out (2026-10-03)

The ordered plan is complete (steps 1-13; 14 cancelled), and the work it
spawned was closed out on 2026-10-03: what each record delivered is in its
"Closed" section; what it left is gathered here, in priority order. Five
records stay open on purpose: `CT-0020`, `CT-0028`, `CT-0041` (future, not
started), `CT-0052` (paused by the user after phase 1), `CT-0053` (awaiting
the user's approval).

### The documents of 2026-10-04 and their priority

The user added `docs/production-validation.md`, `docs/ltx-production-finishing-roadmap.md`,
`docs/production-agents.md`, `docs/finops.md`, `docs/studio-analytics.md`,
`docs/deployment-topology.md` and a negative-guidance section in `docs/generation.md`.
Agreed order (2026-10-04):

1. **Now**, serving SINGULAR's first milestone, "Prologue to Title" (1-01 to 1-04,
   `production-validation.md`), no paid generation:
   1. ~~generation parity on 1-01...1-04~~ done as a reference (CT-0055): the user
      will remake the sequence from scratch in Cine Toaster, keeping only the
      screenplay -- so what matters next is the path from screenplay to finished
      shots inside Cine Toaster, not matching SINGULAR;
   2. ~~negative guidance as a production concept (`generation.md`)~~ done (CT-0056);
   3. ~~the first slice of the Producer role: a deterministic status per sequence~~
      done (CT-0057): `toast status`, `/api/status`, MCP `production_status`,
      the Sequences room;
   4. ~~FinOps steps 2-3~~ done (CT-0058): billing is per endpoint per hour, never
      per job, so costs are allocated; provenance carries the execution id.
      Steps 4-5 done (CT-0061): `toast finops` reads the billing and allocates
      each billed hour to its known jobs; the LTX estimate runs about 10% low.
2. **Next, when a real shot asks**: a finishing spike -- delivery resolution (SeedVR2
   against LTX TiledFusion, CT-0053 reframed as a capability), Refine Details --
   paid, with the user's approval of the estimate; ~~a minimal continuity ledger for
   SINGULAR~~ done (CT-0059); ~~stems for
   Ardour~~ done (CT-0063).
3. **Later**: Layout-to-Render (after the user revisits the rule that the 3D board
   never controls the model); the animated and the music-driven demos; the
   Workforce, FinOps and Analytics consoles -- never before the data behind them is
   reliable; Studio Engineering and the Meta-agent; HDR, Restore; deployment
   experiments.

### Waiting for the user

- Re-check Kael's converted voice (`CT-0040`).
- Approve the cost of the 4K upscaling spike (`CT-0053`).
- Say what feeds the 5.1 system: the TV's apps, a PC, Kodi, Jellyfin, a
  stick (`CT-0052`).
- SINGULAR's own decisions (`CT-0035`, `CT-0039`): screenplay links written
  by its generators, shot subjects where one camera covers several
  framings, `cut: {type: continuation, chain: frame}` on 3-01 P3b.

### Next, in order

1. **Validation on SINGULAR, end to end** with what was built since
   `CT-0035`: sound and music, joins, styles, emotions, formats and
   renditions, on a scratch copy. Every earlier pass on real data found
   what the demos missed.
2. **SINGULAR's remaining vocabulary** (`CT-0017`): its sound keys to the
   sound catalog, image operations, variation, screen text, one-off keys.
3. **Joins between scenes as decisions** (`CT-0051`): a command for a
   scene's `enter`; opening and closing a sequence from and to black.
4. **Formats in generation** (`CT-0049`): aspect and frame rate asked of
   the model; then 4K (`CT-0053`, after the spike).
5. **Review records** (`CT-0022`): re-timed cues and adherence verdicts
   through a command; a per-shot brief override.
6. **Cast lineage** (`CT-0015`): `cast_reference_unused` and
   `_superseded`; master references attached to video generation.
7. **Blender MCP / DCC-MCP investigation** (`CT-0064`): compare an established
   Blender-specific MCP, DCC-MCP and the existing deterministic Blender/USD
   path. Run the inspect -> modify -> preview -> read-back -> deterministic
   regeneration spike before deciding adopt / narrow-adopt / wrap / defer /
   reject. This is an explicit next investigation, not a passive backlog note.

### Active investigation — integrated editing and production architecture (CT-0065)

- [ ] **Audit current editing capabilities** against code: implemented / partial / missing / unknown; identify canonical edit state, timebase, versioning, trim, preview and render contracts.
- [ ] **Select one representative fixture** with J/L cut, transition, sound stems and an alternative generated take.
- [ ] **Prototype an editable React timeline** using existing Core commands, with agent proposal/approval and undo; do not create competing edit state.
- [ ] **Run interoperability and engine spikes**: OpenTimelineIO round-trip/reconform and FFmpeg vs MLT vs GES comparison, with measurable acceptance criteria.
- [ ] **Evaluate production-wide finishing**: OpenColorIO/ACES, OpenEXR, OFX-host boundary, loudness, delivery profiles and dependency-aware regeneration.
- [ ] Record findings and decisions in [CT-0065](../work/CT-0065-integrated-editing-and-production-architecture.md); convert validated choices into ADRs and implementation tasks.

This is an active research track, **not** a decision to replace the existing media engine.

### Active UX investigation — three workspaces (CT-0066)

- [ ] Audit current React routes, canvas, screenplay editor and control-room journeys against the three-workspace concept.
- [ ] Define shared navigation and persistent project / sequence / scene / shot / take context.
- [ ] Prototype Screenplay & Storyboard, Production, and Editing & Post-production layouts, including shot view versus node view.
- [ ] Validate screenplay-to-cut, edit-to-regeneration, agent-approval and delivery journeys with existing Core data.
- [ ] Record usability, accessibility and layout findings and convert approved designs into implementation tasks and ADRs.

Track scope and acceptance criteria in [CT-0066](../work/CT-0066-three-workspace-ux-vision.md). This is a UX investigation, not a commitment to rebuild the existing interface.

### UX follow-up — wireframe validation and human information needs (CT-0067, CT-0068)

- [ ] Preserve the initial three-workspace wireframe as a **non-validated design study** ([CT-0067](../work/CT-0067-three-workspace-wireframe-study.md)); do not treat the three-column layout as approved.
- [ ] Research situation awareness, cognitive load, progressive disclosure, visual hierarchy and accessible interaction ([CT-0068](../work/CT-0068-human-centered-information-visibility.md)).
- [ ] Produce a task → decision → required information → Core source matrix, starting with Production.
- [ ] Compare focused, balanced and advanced-density layouts on laptop and large displays, with user tasks and workload measures.
- [ ] Update the wireframes, record accepted UX decisions and create implementation work only after validation.

### Research in progress — Production information priorities (CT-0069)

- [x] Create an initial Production task → information → display-priority matrix, with preliminary React code audit ([CT-0069](../work/CT-0069-production-information-priority-matrix.md)).
- [ ] Audit control-room server pages, status APIs, FinOps and actual take-comparison flows; verify cross-room context preservation.
- [ ] Compare Focus and Review/Expert layout variants using take selection, failed generation and agent approval tasks.
- [ ] Extend the matrix to Screenplay & Storyboard and Editing & Post-production, and record user-test findings before approving a layout.

### Research — Production Awareness and human situation awareness (CT-0070)

- [x] Map situation awareness, ecological interface design, distributed cognition, attention management and human–AI interaction to Cine Toaster's existing Producer, continuity, FinOps and assistant capabilities ([CT-0070](../work/CT-0070-production-awareness-research.md)).
- [ ] Verify primary research references and actual Core status, dependency and approval data contracts.
- [ ] Prototype explainable **state + consequence + action** awareness items using existing records, without a new source of truth.
- [ ] Compare status-only versus contextual-awareness layouts for stale-take, continuity, failed-job and agent-approval scenarios.
- [ ] Validate with users before introducing UI components, priority rules or architecture decisions.

### Cross-workspace cognitive UX study (CT-0071)

- [x] Map narrative, operational, temporal and cross-workspace cognitive demands to the existing screenplay, storyboard, Producer, editor commands and assistant ([CT-0071](../work/CT-0071-cross-workspace-cognitive-model.md)).
- [ ] Audit actual editing/timeline UI and persistent navigation state; inventory canonical script → board → take → assembly links.
- [ ] Complete information-priority matrices for Screenplay/Storyboard and Editing/Post.
- [ ] Test context-preserving cross-workspace navigation and focused versus detailed layouts with users before approving wireframes.

### Contextual creative decisions and navigation (CT-0072)

- [x] Audit existing sidebar, style cascading, location overrides, shot emotions and moodboard research; capture findings and navigation alternatives ([CT-0072](../work/CT-0072-contextual-creative-decisions-navigation.md)).
- [ ] Inventory cast/look/style/location/continuity resolver fields and existing UI deep links; document source, scope, overrides and provenance.
- [ ] Build decision → origin → scope → override → affected references matrix, distinguishing actual dependencies from unknown ones.
- [ ] Prototype current feature menu plus inspector against a compact workspace menu with contextual creative relations.
- [ ] Validate on film-wide style, local location override, character performance and editing trace-back tasks before changing the sidebar.

### Creative context Core inventory (CT-0073)

- [x] Audit Core resolvers for cast, looks, styles, locations, continuity and cuts, and document a proposed read-only contextual projection ([CT-0073](../work/CT-0073-creative-context-core-inventory.md)).
- [ ] Trace API/client payloads and exact scene/shot binding semantics; verify editing assembly references and cross-room selection persistence.
- [ ] Compare existing feature menu + inspector with hybrid workspace/context navigation in a focused prototype.
- [ ] Validate decisions, provenance and local exceptions with users before an implementation ADR.

### Later

- Sound: generated sound and music, stems, spatial phases 2-4 (`CT-0048`,
  `CT-0052`); expressive TTS for voice-over (`CT-0040`).
- Faces and 3D: a rigged face for the 3D board, gesture data, detailed
  proxies from image-to-3D, drawn boards in several styles, Unreal/Unity
  render adapters, a window that moves within a shot, a sequence-level
  style (`CT-0048`, `CT-0049`).
- Previs and the blocking frame's recorded limits (`CT-0029`, `CT-0025`).
- Backlot: a location specification with pinning and versioning, a demo
  plate (`CT-0030`).
- Transitions: WebM compositing contracts, per-cut parameter overrides
  (`CT-0050`); the Video Toaster port (`CT-0028`).
- Agents: MCP options 2 and 3 (`CT-0045`); learning from gate decisions
  (`CT-0041`).
- Tools: an FDX export opened in Final Draft (`CT-0021`); Okay Wannabe's
  UI (`CT-0020`); Arcads first-hand (`CT-0024`); a finer liquid simulation
  and a running nerfstudio (`CT-0047`); MLT/Kdenlive exchange; detached
  workers; frame-accurate comparison.

### Compound location consumer audit (CT-0075)

- [x] Trace single-location scene resolution, location appearances, plate checks, `/api/locations`, and current set override semantics ([CT-0075](../work/CT-0075-location-consumer-and-continuity-audit.md)).
- [ ] Inspect storyboard/render consumer paths and cross-scene editing continuity for compound-place requirements.
- [ ] Compare optional place grouping versus explicit parent-child place/set model with a Singular hospital fixture.
- [ ] Validate contextual navigation and only then propose a backward-compatible schema/ADR.

### Model-dependent mood and master-image consistency (CT-0076)

- [x] Record qualitative Singular Codex-vs-Qwen master-image texture/mood observation and UX-first research questions ([CT-0076](../work/CT-0076-model-dependent-mood-and-visual-identity.md)).
- [ ] Audit current look/style, image-reference, provider-capability, provenance and human-approval contracts before schema changes.
- [ ] Run controlled multi-sample comparison on one hospital shot, logging conditioning differences, settings, output, mood and continuity review.
- [ ] Prototype UX comparison from visual intent to candidate masters to approved master and downstream shots, including aesthetic drift review.
- [ ] Research Blender and planned Unreal roles as alternative/complementary spatial inputs, without imposing one fixed tool chain.
