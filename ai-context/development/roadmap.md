---
id: CTX-DEVELOPMENT-ROADMAP
title: Development roadmap
type: roadmap
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-10-15
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
7. **Blender MCP / DCC-MCP investigation** (`CT-0082`): compare an established
   Blender-specific MCP, DCC-MCP and the existing deterministic Blender/USD
   path. Run the inspect -> modify -> preview -> read-back -> deterministic
   regeneration spike before deciding adopt / narrow-adopt / wrap / defer /
   reject. This is an explicit next investigation, not a passive backlog note.

### Active investigation — integrated editing and production architecture (CT-0083)

- [ ] **Audit current editing capabilities** against code: implemented / partial / missing / unknown; identify canonical edit state, timebase, versioning, trim, preview and render contracts.
- [ ] **Select one representative fixture** with J/L cut, transition, sound stems and an alternative generated take.
- [ ] **Prototype an editable React timeline** using existing Core commands, with agent proposal/approval and undo; do not create competing edit state.
- [ ] **Run interoperability and engine spikes**: OpenTimelineIO round-trip/reconform (the export is done, CT-0096: `versions/vN.otio`; OpenRV, which reads OTIO, is the natural review player to try it with) and FFmpeg vs MLT vs GES comparison, with measurable acceptance criteria.
- [ ] **Evaluate production-wide finishing**: OpenColorIO/ACES, OpenEXR, OFX-host boundary, loudness, delivery profiles and dependency-aware regeneration.
- [ ] Record findings and decisions in [CT-0083](../work/CT-0083-integrated-editing-and-production-architecture.md); convert validated choices into ADRs and implementation tasks.

This is an active research track, **not** a decision to replace the existing media engine.

Reference for the track: [awesome-cg-vfx-pipeline](https://github.com/cgwire/awesome-cg-vfx-pipeline). Most of its creation-side entries are already in place or recorded (OpenColorIO, OpenUSD, Natron/OFX, COLMAP, splats: CT-0047). What it adds is production tracking: compare Kitsu's model (projects, sequences, shots, tasks, previews, statuses) with ours -- to learn from, and as a possible export of shots and versions for a studio already on it -- never as the authority over the filesystem project.

### Active UX investigation — three workspaces (CT-0084)

- [ ] Audit current React routes, canvas, screenplay editor and control-room journeys against the three-workspace concept.
- [ ] Define shared navigation and persistent project / sequence / scene / shot / take context.
- [ ] Prototype Screenplay & Storyboard, Production, and Editing & Post-production layouts, including shot view versus node view.
- [ ] Validate screenplay-to-cut, edit-to-regeneration, agent-approval and delivery journeys with existing Core data.
- [ ] Record usability, accessibility and layout findings and convert approved designs into implementation tasks and ADRs.

Track scope and acceptance criteria in [CT-0084](../work/CT-0084-three-workspace-ux-vision.md). This is a UX investigation, not a commitment to rebuild the existing interface.

### UX follow-up — wireframe validation and human information needs (CT-0085, CT-0086)

- [ ] Preserve the initial three-workspace wireframe as a **non-validated design study** ([CT-0085](../work/CT-0085-three-workspace-wireframe-study.md)); do not treat the three-column layout as approved.
- [ ] Research situation awareness, cognitive load, progressive disclosure, visual hierarchy and accessible interaction ([CT-0086](../work/CT-0086-human-centered-information-visibility.md)).
- [ ] Produce a task → decision → required information → Core source matrix, starting with Production.
- [ ] Compare focused, balanced and advanced-density layouts on laptop and large displays, with user tasks and workload measures.
- [ ] Update the wireframes, record accepted UX decisions and create implementation work only after validation.

### Research in progress — Production information priorities (CT-0087)

- [x] Create an initial Production task → information → display-priority matrix, with preliminary React code audit ([CT-0087](../work/CT-0087-production-information-priority-matrix.md)).
- [ ] Audit control-room server pages, status APIs, FinOps and actual take-comparison flows; verify cross-room context preservation.
- [ ] Compare Focus and Review/Expert layout variants using take selection, failed generation and agent approval tasks.
- [ ] Extend the matrix to Screenplay & Storyboard and Editing & Post-production, and record user-test findings before approving a layout.

### Research — Production Awareness and human situation awareness (CT-0088)

- [x] Map situation awareness, ecological interface design, distributed cognition, attention management and human–AI interaction to Cine Toaster's existing Producer, continuity, FinOps and assistant capabilities ([CT-0088](../work/CT-0088-production-awareness-research.md)).
- [ ] Verify primary research references and actual Core status, dependency and approval data contracts.
- [ ] Prototype explainable **state + consequence + action** awareness items using existing records, without a new source of truth.
- [ ] Compare status-only versus contextual-awareness layouts for stale-take, continuity, failed-job and agent-approval scenarios.
- [ ] Validate with users before introducing UI components, priority rules or architecture decisions.

### Cross-workspace cognitive UX study (CT-0089)

- [x] Map narrative, operational, temporal and cross-workspace cognitive demands to the existing screenplay, storyboard, Producer, editor commands and assistant ([CT-0089](../work/CT-0089-cross-workspace-cognitive-model.md)).
- [ ] Audit actual editing/timeline UI and persistent navigation state; inventory canonical script → board → take → assembly links.
- [ ] Complete information-priority matrices for Screenplay/Storyboard and Editing/Post.
- [ ] Test context-preserving cross-workspace navigation and focused versus detailed layouts with users before approving wireframes.

### Contextual creative decisions and navigation (CT-0090)

- [x] Audit existing sidebar, style cascading, location overrides, shot emotions and moodboard research; capture findings and navigation alternatives ([CT-0090](../work/CT-0090-contextual-creative-decisions-navigation.md)).
- [ ] Inventory cast/look/style/location/continuity resolver fields and existing UI deep links; document source, scope, overrides and provenance.
- [ ] Build decision → origin → scope → override → affected references matrix, distinguishing actual dependencies from unknown ones.
- [ ] Prototype current feature menu plus inspector against a compact workspace menu with contextual creative relations.
- [ ] Validate on film-wide style, local location override, character performance and editing trace-back tasks before changing the sidebar.

### Creative context Core inventory (CT-0091)

- [x] Audit Core resolvers for cast, looks, styles, locations, continuity and cuts, and document a proposed read-only contextual projection ([CT-0091](../work/CT-0091-creative-context-core-inventory.md)).
- [ ] Trace API/client payloads and exact scene/shot binding semantics; verify editing assembly references and cross-room selection persistence.
- [ ] Compare existing feature menu + inspector with hybrid workspace/context navigation in a focused prototype.
- [ ] Validate decisions, provenance and local exceptions with users before an implementation ADR.

### The demos line: the music piece, then the reel (opened 2026-10-13)

Its own line of work (the user, 2026-10-13): capabilities the demos need,
which become part of Cine Toaster. It has no specific relation to SINGULAR
and does not follow that line's priorities. The history and the evidence are
in `CT-0064`. The user's rule (2026-10-14): every gap found is attacked, one
point at a time, in this order. Each point gets its own work record when it
starts and is struck here when it is done.

Done: the reel on the assembly path, stills as takes, narration beside the
scene (`CT-0065`); footage declared and fetched (`CT-0066`); the music search
that hid Freesound's tracks; a first music piece and an organic trial, made
partly by hand, outside the repository.

**D1. ~~Beats are a record.~~** Done (`CT-0067`). Limitations left, each
solvable, to be closed later as **D1b**:
- **Bars.** librosa gives beats, not downbeats, so nothing knows which beat
  is the first of a bar. Solvable two ways, both wanted: a downbeat tracker
  (madmom's `DBNDownBeatTracker`, or a newer model such as beat_this; licences
  to check against ADR 0011) writing `downbeats` beside `beats`; and a
  person's correction in the record (`beats_per_bar`, `first_downbeat`), since
  any detector can be wrong by one beat. Then a shot may count `bars: 2`, and
  a check says when a join that should open a bar does not.
- **Music that starts later than the scene.** Beats are counted from the
  scene's start; music placed with `at` or `from` is refused. Solvable by
  counting from where the music starts on the timeline.
- **Tempo changes.** Lengths follow the detected beats, so a track that
  speeds up is followed; but a beat the detector misses or doubles moves the
  cut. Solvable with the same correction in the record (beats added or
  removed by hand) and a view of the beats over the waveform.
- What: `toast sound beats <project> <sound>` detects a track's tempo and
  beats (librosa, in the voice interpreter, as a worker) and keeps them
  beside the sound. A scene that has music may give a shot's length and a
  join's place in beats (`duration: 8 beats`, or a join `on: 16`).
- Check: a join that is not on a beat of the scene's music, when the scene
  says it is cut to the music.
- Done when: the music piece is assembled from beats written in its
  breakdown, with no script outside the tool, and comes out the same length.
- Closes: "beats are not in the tool"; "a shortened transition moves later
  joins off the beat" (placing joins by beat makes each independent).

**D2. ~~A production says its frame.~~** Done (`CT-0068`); a scene's own
frame is left in C10 of the compositing roadmap (`toast build` was removed
in CT-0072).
- What: size and rate declared once in `project.yaml`; every version is
  made in it, whatever its first take is. Footage is fetched to fit when no
  height is given.
- Done when: a scene opening on a 4K take and one opening on a card give
  versions of the same declared size.

**D3. A transition can take a matte and an overlay.** Done in its first
part (`CT-0069`, `SPEC-0011`). What it left, and everything that was D3b to
D7 -- the compositing primitives (ADR 0022), layers and the ADO move, the
warp wipe, the catalogs rebuilt on primitives, time and tracking, signals
from models and from 3D, real time and streams, and the loose ends -- is now
**`development/compositing-roadmap.md`, steps C1 to C10**, with what each is
done by and the limits known in advance.

**D8. The music piece, finished.** After C5 of the compositing roadmap: joins written in
beats, organic joins through mattes, a picture flown over another; better
pictures than the Mars square. In the repository as the fourth demo
(`docs/production-validation.md`), its footage fetched, not checked in.

**D9. The reel, written from scratch.** A short narrated first act (two
voices) and the music piece as its second. Nothing of the previous reel is
kept; `examples/amiga-demo-reel` is a placeholder until this replaces it. The
script goes to the user before it is built.

Order: D1b (bars) when a piece needs bars; the compositing roadmap C1-C10
in its own order; then D8 and D9.

**The demo set (the user, 2026-10-16).** No new demos: the ones planned,
each made by a **different approach**, so that together they show the tool
end to end. Each is produced through the production flow (an intention, a
screenplay, a storyboard, then production), and what the flow lacks for its
approach is recorded and built, not worked around. The reel comes last,
made from the others.

| Demo | Approach | What of Cine Toaster it exercises |
|---|---|---|
| The Last Signal | narrative, generated takes | the classic flow: screenplay, storyboard, cast, generation, verdicts, assembly |
| The music piece (D8) | an **advertisement** for a fictitious brand, driven by its music | a brief, cuts on the beats, packshot and legal card, several deliveries from one production (30/15/6 s; 16:9, 9:16, 1:1) |
| The animated short | a **cartoon** (2D drawn) | a character kept the same shot to shot (model sheet, style guide), lip sync to dialogue, limited animation on twos |
| The hybrid VFX micro-scene | footage and **ray-traced CG** (Cycles) | depth, a person cut out with soft mattes, a CG object behind and in front of her |
| The reel (D9), last | the four as its sources | the tool presenting itself, on NewTek's 1991 tape; it holds a short **ray-traced scene of its own** -- a homage to Eric Graham's *Juggler* (1986, the Amiga's ray-traced animation) -- whose final shots come from Blender's blockout rendered, not generated |

Ray tracing appears twice, in two roles: CG joining footage (the hybrid
scene) and a film made by it alone (the Juggler scene in the reel). Open
for the user: how the cartoon is made -- generated in a fixed style from a
model sheet (recommended: it tests what is hardest in AI animation and the
cast references not yet wired to generation), Blender's Grease Pencil, or
toon-shaded 3D -- and the budget for paid generation. Gaps already seen: an
intention/treatment record (only `logline`), a production using another's
version as a source (the reel), the screenplay of a music-driven piece, a
client brief and duration variants as records (the advertisement), a shot
whose final picture is a Blender render through the flow (cartoon or
Juggler), UI capture for the reel.

### From the review of FilmCraft and EffectCraft (2026-10-14, CT-0075)

Neither changes the direction; each is used at the edges (`references.md`).

- ~~**Do -- a version exported as OpenTimelineIO.**~~ Done (CT-0096,
  `toast assemble --otio`, `docs/otio.md`): the cut, its transitions, the
  drawn shots kept beside the version, the mix and the stems. Left, each with
  how: J- and L-cuts split across the tracks (the sound's own clips placed by
  the plan's `split`); a transition's look beyond a dissolve (OTIO's
  transition types, or the drawn join as a clip); a sequence's cut (its
  scene versions as clips, the scene joins as transitions).
- **Spike, when C6b or C8 need it -- EffectCraft as an opaque renderer.**
  `opaque.effectcraft`: a node whose picture is a render of a small JSON
  project by `effectcraft-cli render`, for what our graph does not hold
  (particles as a simulation, extruded 3D text, text animators). How: one
  node, its project file known by content (identity), a doctor capability;
  adopted only if it renders headless and repeatably. Not before: it is
  alpha and changes daily.
- **Research -- an integer time base** (in progress: `CT-0079`, measured -- see there). Our curves run on float seconds; C3
  had to anchor a beat to its frame's centre, and 29.97 frames are inexact.
  How: measure where float time drifts (long shots, 29.97, sample-accurate
  sound); if it does, ticks as FilmCraft's (254,016,000,000 a second) in the
  plan and the curves, seconds only at the edges. The user's reading of
  FilmCraft's and EffectCraft's architecture (section 2, "Time base" /
  "Time"; 2026-10-15), to compare our contract with before C7, since
  tracking, retiming and audio-visual sync depend on it: a shared base of
  254,016,000,000 ticks a second as `Tick(i64)` -- 10,584,000,000 a frame at
  24 fps, 8,475,667,200 at 30000/1001, 5,292,000 a sample at 48 kHz,
  5,760,000 at 44.1 kHz, all exact; intervals half-open (a start and a
  duration, the end never in doubt); in multicamera sync, video placed on
  frame boundaries and sound kept sample-accurate; the sound's clock the
  master in playback. Compare: the canonical form of instants and lengths,
  fps-to-sample-rate conversion, interval bounds, rounding where sound
  segments are aligned in the assembly, and 24000/1001 and 30000/1001. Not
  to adopt the ticks before showing that a seen problem comes from the time
  representation rather than from how segments are aligned and encoded.
- **Research -- spill suppression and text animators** from EffectCraft's
  code (permissive licence, attribution): spill for C4's keys (recorded in
  the compositing roadmap), per-character animators with range selectors
  for C6b.
- **Kept as it is -- particles and 3D letters.** They exist, rendered by
  Blender (CT-0047's elements, the `blender` title engine); in C6 they
  become layer sources with their alpha, in C8 the graph's
  `generate.render`. No particle primitive is planned.
- **Research in C6/C6b -- Lottie as an input** (the user, 2026-10-14;
  first recorded here as "not pursued", which thought only of exporting it).
  Lottie (`.json`, `.lottie`) is a large ecosystem of ready motion graphics
  -- titles, lower thirds, credits, icons, infographics. Step 1: a Lottie
  file as a layer source, rendered with its alpha, with its duration and
  time under our control (`time.remap`), behind an adapter -- candidates
  ThorVG (MIT engine; `thorvg-python`, LGPL binding), rlottie
  (`rlottie-python`, LGPL binding) and Skia's Skottie (BSD; whether
  `skia-python` exposes it to be checked); `python-lottie` is AGPL and not
  linked. Step 2, evaluated after: converting the part of a Lottie file our
  primitives express (shapes, transforms, keys and their Bézier eases,
  masks) into the graph, so it can be changed and combined -- never a second
  animation engine beside the graph. Export stays out of scope.
  **Step 1 done** (CT-0078 stage D): a Lottie file is a format every source
  reads, drawn by ThorVG. Left from it, each with how:
  - *Step 2*, as above: start with shape layers (paths, fills, strokes,
    transforms, keys with their eases) into `matte.shape`, `generate.solid`,
    `warp.transform` and `curve.keys`; whatever is not converted stays drawn
    by ThorVG as a source, so a file is never half lost.
  - *Looping*: an animation shorter than its layer holds or ends; a `loop`
    on the source (frames taken modulo its length in the adapter) would
    repeat it.
  - *Which engine is right where ThorVG and rlottie differ* (a mask sample,
    the confetti's opacity, a star's stroke): draw the same frames with
    lottie-web in headless Chromium (Playwright is already the splat
    extra) and compare, before trusting either on masks.
  - *Text layers' fonts*: ThorVG draws text layers whose glyphs the file
    carries; one naming a system font needs the font loaded into ThorVG
    (its font loader) -- not checked yet.

### An intermittent test (found 2026-10-15, CT-0078; again in CT-0079)

- Still open: passing alone does not resolve it (the user, 2026-10-15). A
  robustness test of its own -- the same check run many times, or on PCM
  stems -- should show it fixed, apart from C7's work.

- `tests/test_stems.py` compares a stretch's mean loudness of the summed stems
  with the version's within 0.5 dB, and once measured exactly 0.5. The mix
  passes through AAC twice and a limiter with lookahead, whose output need
  not be bit-identical run to run. How: compare the stems before encoding (a
  PCM render of the mix), or measure where the limiter is idle, so the test
  holds the claim -- the stems make the mix -- without a margin at its edge.

### Colour fonts not drawn yet (found 2026-10-15, CT-0078 stage C)

- **SVG glyphs** (OpenType SVG fonts) draw as plain fonts: FreeType draws
  them only through a renderer hook Pillow does not give. How: read the
  glyph's SVG document from the font's `SVG ` table (fontTools) and render it
  with resvg or CairoSVG into the same tile the colour path places, behind a
  doctor capability.
- **A colour font under the letter animator** draws in `colour`: the
  per-letter path draws coverage. How: give `_letters_coverage` an RGBA tile
  from `_colour_text`'s drawing for each glyph, the same placement kept.

### A listening review of retimed sound (CT-0080)

- The anchored WSOLA was chosen as `stretch`'s default on measurements
  (sync, level, pitch, transients); no one has judged it by ear on real
  material -- the blind files' tape excerpt was near silence. How: blind
  files of representative excerpts (speech, music with drums, ambience,
  Foley), checked for level before they are sent, judged by a person; and
  an objective perceptual score where one fits (ViSQOL, Apache 2.0) to
  compare stretchers on the same map.

### A scene's passes: what the Blender adapter does not do yet (CT-0081 step 2)

- **Only Cycles.** What EEVEE's (or another renderer's) Z measures has not
  been measured, so it is refused. How: render the wall square to the
  camera with it, as `tests/test_renders.py` does, and add its entry to
  `renders.Z_MEASURED` (z or distance).
- **Only perspective cameras, square pixels.** How: an orthographic camera's
  intrinsics are its `ortho_scale` over the sensor fit (no focal length);
  panoramic cameras need their own projection named in `render.json`; a
  pixel aspect other than 1 scales `fy` by it.
- **Edges and transparency**: Z and the object index are one surface per
  pixel, not anti-aliased, and a transparent surface writes its own. How:
  Cryptomatte (Blender writes it; a coverage per object per pixel) for soft
  object mattes, and depth compositing at edges as C8 step 5 plans.
- **Blender's version is recorded, not checked at reading.** How: `toast
  doctor` (or `renders.status(check_renderer=True)`) compares the installed
  `blender --version` with the record's and says so, without making the
  render stale by itself -- the scene, not the program, is its input.
- **Rendering is a Python command, not yet a CLI or job.** How: `toast
  render passes <id> --scene --camera --frames` and a job kind calling
  `render_passes`, so the GUI, CLI and agents use the one command.
- **A file the scene reaches outside the production is refused.** How: a
  "collect" step copying textures and libraries into the production and
  relinking them (Blender's `file.pack_all` or `make_paths_relative`).
- **Signals are not on GL yet** (`generate.render` by record sends a graph
  to the reference): C8 step 6.
- **Depth resized to the nearest** (safe with +inf, but stair-stepped on
  slanted surfaces). How, in C8 step 5: an interpolation that blends only
  among valid neighbours on the same side of a depth discontinuity (a
  threshold on the relative jump), +inf and labels never blended.

### Integration a composite still lacks (seen in CT-0081's film)

- **A CG object is sharp where the plate is soft.** How: a defocus by depth
  (`filter.blur` weighted by the merged depth's distance from a focus
  plane, a circle of confusion from the stated lens), recorded in the
  layer.
- **A CG object is lit as rendered, not as the plate.** How: a grade of the
  render to the plate (its exposure and white from the plate's region
  behind it), and the plate's light measured (a probe) for the render.
- **A camera is stated, not solved.** How: a camera solve of the take
  (C7's tracking, extended to a camera) recorded as the shot's camera, its
  lens measured instead of assumed.

### Depth in layers: what it does not do yet (CT-0081 step 7)

- **A layer with a depth cannot move, pin, trail, shadow or border.** How:
  the same warp applied to its depth (`warp.transform` and
  `warp.corner_pin` of a two-channel signal, nearest-sampled), a shadow cast
  by depth (a shadow layer at the depth of what it falls on).
- **A constant depth for a layer** (a card at 4 m) needs a signal record.
  How: `depth: {value: metres, camera}` compiled to an object depth of a
  constant over the layer's alpha.
- ~~**A cut is a hard segmentation.**~~ Done (CT-0096): `cut: {..., soft:
  true}` takes each object's soft matte.

### Signals on GL: what is not there yet (CT-0081 step 6)

- **Reading a signal costs more than drawing it**: a 1080p frame is a
  ZIP-compressed float EXR, 36 ms to decode. How: a disposable cache of
  decoded frames (.npy, keyed by the record's data hash) beside the
  composite cache -- 2.6 ms a frame; or a lighter EXR compression for
  records read often.
- **A surface's depth is drawn by the reference only.** How: the mesh pass
  writes its depth buffer as linear z into a second target.
- **An object's depth reads its matte back** (one transfer a frame). How: a
  GPU histogram of the interior's depths (a reduction in two passes), kept
  only if measured faster than the transfer.
- **A merge takes 8 layers on GL.** How: merge in groups of 8 by depth
  order, the partial result carried as a layer with its depth.
- **The graph's `signal.align_depth` is the reference's**: the recorded
  alignment (`toast signal align`) is the one to use; the graph op stays a
  sketch until it reads a calibration's parameters.

### Depth compositing: what it does not do yet (CT-0081 step 5)

- **A cut-out's fringe carries the plate's background** (the person layer
  is the plate times its matte, so its edge pixels hold the wall too). How:
  estimate the foreground colour at the edge (closed-form matting's
  foreground, or the plate's colour pulled from inside the matte), recorded
  as the layer's.
- **Inside an opaque layer a silhouette has no coverage.** How: Cryptomatte
  from Blender for renders; for footage, cut every occluder out as a layer.
- **One depth per object is a constant**: an object long in depth (a
  table, a person reaching out) is not one number. How: `statistic: plane`
  -- a plane fitted to the object's interior depth, carried over its matte.
- ~~**SAM 2's mattes are hard labels.**~~ Done (CT-0096): each object's
  probability kept as an `alpha` signal (`<id>-alpha-<label>`); at a
  rendered pillar's edge the coverage error halves (0.355 to 0.184). Left:
  the probability is not a coverage -- SAM 2's mask is upsampled from 256
  px, so a fine edge (hair) is still soft guesswork. How: a matting model
  (e.g. ViTMatte) refining the alpha in its band, as another estimate.
- **Coverage reaches 2 pixels**, a fixed choice from one measurement. How:
  the reach from the picture's own filter width (a render records it).

### Aligned depth: what it does not do yet (CT-0081 step 4)

- **Proven on synthetic scenes only.** How: the done-when films of step 8
  on real footage -- a person, hard occlusions, a handheld move -- with a
  reference from a scanned or modelled set, the same measures recorded.
- **An inverted occlusion is flagged, not mended.** How: a person's
  correction of the order (a patch, `correct_signal`), or ordering by
  object (step 5): a segmentation decides who is in front, the depth only
  where it agrees.
- **Calibration only against a metric depth of the same pixels.** How: a
  depth from another camera brought into these pixels by a known warp in
  the graph (`warp.*`), its window recorded; sparse references (tracked
  points with depth, a measured distance) as a reference of a few pixels.
- **Unknown pixels take `behind` or `front` only.** How: a fill from
  neighbours of the same object (a segmentation), recorded as such.
- **A steep surface reads as an edge.** The band left out of a calibration
  is where the inverse depth jumps by more than 5% between neighbours; at a
  low resolution a floor at a grazing angle does that on every row and is
  left out whole. How: tell a discontinuity from a slope by the second
  difference (a slope's steps are alike, an edge's is alone), or by the
  segmentation's boundaries when one is given.
- **Held-out 8-pixel blocks barely differ from the sample.** How: blocks
  scaled to the frame (an eighth of its height), or held-out objects.

### Estimated signals: what the model adapters do not do yet (CT-0081 step 3)

- **CPU only, small models.** Video Depth Anything takes about 15 s a
  32-frame window at input 252 and 170 s at 518 here. How: a device option
  (CUDA when present) recorded in the environment, and the Runpod path for
  long shots (C9), the record unchanged.
- **One window's memory on a long shot**: Video Depth Anything holds every
  frame of the stretch. How: its streaming mode (`run_streaming.py` in the
  pinned code) as a parameter, recorded as a different temporal contract.
- ~~**SAM 2 keeps hard labels.**~~ Done (CT-0096): soft mattes beside them.
- **Prompts are points and boxes on the command line.** How: prompts drawn on
  a frame in the control room, kept with the record; a person's correction
  re-prompting a frame.
- **Frames are FFmpeg's rgb24** of the medium (its default matrix for YUV).
  How: read through the colour pipeline to sRGB when a medium declares its
  colour space, recorded in `pixels`.
- **`compare` gives a correlation, not a residual**; the fitted alignment
  and its residual are step 4's.

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

### Compound location consumer audit (CT-0093)

- [x] Trace single-location scene resolution, location appearances, plate checks, `/api/locations`, and current set override semantics ([CT-0093](../work/CT-0093-location-consumer-and-continuity-audit.md)).
- [ ] Inspect storyboard/render consumer paths and cross-scene editing continuity for compound-place requirements.
- [ ] Compare optional place grouping versus explicit parent-child place/set model with a Singular hospital fixture.
- [ ] Validate contextual navigation and only then propose a backward-compatible schema/ADR.

### Model-dependent mood and master-image consistency (CT-0094)

- [x] Record qualitative Singular Codex-vs-Qwen master-image texture/mood observation and UX-first research questions ([CT-0094](../work/CT-0094-model-dependent-mood-and-visual-identity.md)).
- [ ] Audit current look/style, image-reference, provider-capability, provenance and human-approval contracts before schema changes.
- [ ] Run controlled multi-sample comparison on one hospital shot, logging conditioning differences, settings, output, mood and continuity review.
- [ ] Prototype UX comparison from visual intent to candidate masters to approved master and downstream shots, including aesthetic drift review.
- [ ] Research Blender and planned Unreal roles as alternative/complementary spatial inputs, without imposing one fixed tool chain.

### Visual Lab UX and Core fit (CT-0095)

- [x] Inspect look/style resolution, per-shot picture approval, decision journal and image derivation tests; record UX-first gaps ([CT-0095](../work/CT-0095-visual-lab-core-gap-and-ux-research.md)).
- [ ] Prototype representative-location visual experiments and model comparison with complete provenance.
- [ ] Determine how a film-wide visual baseline, exceptions and revisions fit existing Core contracts without a parallel truth model.
- [ ] Validate Visual Lab placement in navigation and downstream change-impact visibility before a UI or schema ADR.

- [ ] Visual Lab: prototype separate quality / shot suitability / visual-identity fit assessments and human decisions (approve, regenerate, retain as exploration, scoped exception, fork candidate identity).
- [ ] Visual Lab: test candidate identity across representative locations before promotion; version approved baselines and assess known/unknown downstream impact.
