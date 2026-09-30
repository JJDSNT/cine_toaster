---
id: CTX-PROJECT-STATUS
title: Project status
type: status
status: current
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - status
  - tracker
  - roadmap
---

# Project status

Last updated: 2026-09-29

## Current phase

The first canonical production write is delivered. Cine Toaster is no longer a
read-only prototype: a human or an agent can compare registered alternatives and
commit a decision through one shared command.

## Product state

Cine Toaster can currently:

- open an external filesystem project;
- parse the project and per-scene operational manifests;
- build a disposable external SQLite index;
- expose project, scene, library, search, media, and transition queries;
- present a read-only Production Control Room in the browser;
- preview built-in and project transition assets;
- operate through the `toast` CLI;
- register concrete take alternatives per shot, with status, media, note, cost,
  and preserved provider provenance;
- commit a take selection through one shared command from Core, CLI, HTTP, or
  the browser, with revisions, typed errors, atomic writes, and a durable
  decision history;
- compare alternatives side by side in the browser and record why one was
  chosen;
- read scene geometry and report continuity problems before anything is
  generated (`toast check`);
- draw a plan-view blockout of the set, the cameras, and the line of action;
- link each scene to its screenplay scene and each shot to the lines it
  covers, so every storyboard frame shows its dialogue and action, and report
  uncovered, drifted, and unscripted lines (SPEC-0006, `toast script`);
- declare movement within a shot, meaning characters sent to marks and camera
  moves between poses, and check it before generating: positions carry across
  the cut, the move kind is derived, and axis crossings and screen-side jumps
  are reported (SPEC-0005);
- group scenes into sequences and report progress at the level a production
  actually reviews;
- follow committed decisions live, including decisions made from another
  terminal;
- record every assembled version of a scene with the takes it was built from,
  the author's verdict, and the reason, then roll selections back to any of
  them and list what differs between two cuts;
- read a production's own YAML breakdown directly, with no import step, and
  discover a shot's alternatives — including rejected ones and why — by reading
  the work directory;
- record what a production learns as data with dates, evidence, and a link to
  the check that enforces it, and report how much of it software actually
  enforces (`toast knowledge`, `toast why`);
- carry measured provider capability claims that a future generation adapter
  will read;
- list and instantiate two independently identified demo productions: The Last
  Signal and Amiga Demo Reel;
- register multiple arbitrary external local projects simultaneously through an
  in-memory Project Manager;
- preserve manifest project identity across path changes and reject duplicate
  IDs opened from different locations;
- prevent `toast demo` from creating runtime productions inside the application
  source checkout unless an explicit fixture-development override is supplied;
- distinguish reusable Cine Toaster mechanisms from production-owned creative
  values and one-off tools, demonstrated by a working project-local transition
  in Amiga Demo Reel and the no-extension case in The Last Signal;
- preserve project files as the production authority.

Cine Toaster cannot yet:

- execute or recover background jobs;
- persist the multi-project registry or expose project switching in the UI;
- run project-scoped agents;

## Active work

- `CT-0017` is in `doing` for the production schema and Amiga reel.
- `CT-0015` is ready for cast entities and reference lineage.
- `CT-0021` is ready to evaluate Fountain editing components and Final Draft
  FDX interchange. Current screenplay support is read-only raw-text display.
- `CT-0020` records a future UI evaluation: Okay Wannabe as a production-stage
  reference and a node-based way to guide clip transitions. No interface or
  schema choice has been made.
- `CT-0022` is in `doing`: camera movement and cuts between clips are the main
  production pain. External references are screened and ranked in
  `references.md`, and the SceneFlow spike is done. Briefs can be derived from
  records, including screen sides from geometry. SPEC-0005 is implemented:
  movement within a shot, eight new checks, and blockout paths. SPEC-0007 is
  implemented: a cut record for every join in a scene, five checks, and join
  cards in the Cut room.
- `CT-0023` and `CT-0024` cover the node canvas. All six reference
  repositories use React Flow and none uses CopilotKit. Arcads is an
  executable graph of creative-level nodes. The corrected position is one
  canvas with entity nodes (records) and step nodes (workflow templates);
  steps run in the orchestration layer and results become takes with lineage.
- `CT-0025` is in `doing`: storyboard fidelity levels. The blocking frame is
  delivered: the camera's view computed from geometry, shown beside the
  blockout, and available through `toast frame`.

## Closed: scene import

There is no import step. Cine Toaster reads the production's own YAML where it
lies, and takes are discovered from the work directory rather than declared
(ADR 0010). The exporter, the generated scene files and the staleness check they
required are all deleted.

## Delivered

- `CT-0026` — gl-transitions submodule: 117 unreviewed shaders plus 6 reviewed;
  `toast build` runs GLSL transitions through ModernGL (`done`).
- `CT-0013` — production-specific tooling boundary and demo examples (`done`).
- `CT-0002` — canonical take selection (`done`).
- `CT-0008` — scene geometry, continuity checks, sequences, live board (`done`).
- `CT-0009` — knowledge layer and the eyeline direction check (`done`).
- `CT-0010` — closed decision loop, assembly versions, staleness (`done`).
- `CT-0011` — one native format, read the production's YAML directly (`done`).
- `CT-0012` — generation providers moved into the tool (`done`).

## Ready next

Follow the **ordered plan** in `development/roadmap.md` (2026-09-29):

1. screenplay coverage (SPEC-0006);
2. cut record;
3. blocking frame;
4. brief builder and SceneFlow export;
5. FDX interchange;
6. jobs runtime;
7. React stack decision and read-only canvas;
8. screenplay editor (ADR 0006 amendment);
9. generation unit decision and first generation adapter;
10. built-in workflow with a gate;
11. LangGraph spike;
12. CopilotKit/CoAgents spike;
13. editable canvas;
14. ~~Tauri~~ (cancelled, ADR 0019).

Steps 1–4 are **done**: screenplay coverage (SPEC-0006), the cut record
(SPEC-0007), the blocking frame (`CT-0025`), and the brief builder with a
local-video review (`docs/brief.md`). Step 4b, light previs (`CT-0029`), is
done too, and so is step 5, Final Draft interchange (ADR 0014: import to a new
Fountain file with a loss report, export a derived `.fdx`). The next action is
step 6, the jobs runtime, which is now done too (SPEC-0008: durable store,
previs and build as jobs, cancel, reconcile, retry, adopt, jobs tray). Step 7
is done: React 19 + Vite + React Flow (ADR 0015), with a read-only production
canvas at `/canvas/`. Step 8 is done: the screenplay editor (ADR 0016, amending ADR 0006) at
`/app/script.html`. SINGULAR was validated read-only (CT-0035), and several
fixes and a SPEC-0007 amendment (continuation) came from it. The flow is framed in two phases (`production-flow.md`): fitting the
screenplay and storyboard, then producing what was defined, with versions.
Scene assembly from the chosen takes now makes kept versions (CT-0038). Generation blocks and content-based slicing into takes are done (CT-0037);
they match SINGULAR's own slicing on all six blocks. The working order is in CT-0039. Speech-aware trims and loudness, job lineage
and cost, LTX rules as knowledge, and sequence versions are done. What
remains:

- SINGULAR's direction and production decisions are recorded in its own
  `docs/SINGULAR-CINE-TOASTER.md`, to take up when the user returns to it;
- the generation adapter is done, with a US$ 2 ceiling the user approved
  (`toast budget`, `toast generate`, versions `b<id>-<n>`; CT-0037). The control room
  starts one after showing the estimate. The voice spike is done too:
  `toast revoice` converts a take's speech to the cast member's recording, the
  room kept, as a new take, with each speaker of a multi-speaker take in their
  own voice (lines aligned to word timings, no diarization; CT-0040), or, as a
  decision on the shot, converted in the cut when the scene is assembled. Master pictures by
  `derive` (render + cast faces, `toast picture`) close step 9. Step 10 is done too:
  the built-in workflow stops at "approve the master picture" (SPEC-0009,
  CT-0042; `toast workflow`, the scene room's Workflow panel, a card on the
  canvas); refusals must say what is wrong. Step 11 is done (ADR 0017,
  CT-0043): production workflows stay built in; LangGraph runs the agents as an
  optional extra; a LangGraph CoAgent with CopilotKit knew what the page showed,
  shared state, and asked before starting a workflow; the model ran through the
  Claude Code CLI with no API key. Step 12 is done too (ADR 0018,
  CT-0044): `toast serve --assistant` puts a directing assistant beside the
  canvas (CopilotKit v2 → bundled Copilot Runtime sidecar → LangGraph agent over
  AG-UI → Claude Code CLI); it knows what is on screen, points at shots, and acts
  only through commands after a yes, never on a gate. Step 13 is done too
  (CT-0046): the canvas edits cuts (a decision over the breakdown, never a
  rewrite) and starts workflows, through the same commands. Step 14 (Tauri) was
  cancelled by the user (ADR 0019): the plan ends at 13. Next: the pending
  hardening items. The author
  will re-check later whether Kael's converted voice still sounds ill.

Earlier notes:

- Phase 2 — application runtime and jobs. The first job should be the one the
  external production already needs: assemble a sequence from its selected takes
  with FFmpeg, with progress and cancellation.
- A generation adapter reading `[[geometry.cameras]]` as camera intent, so a
  shot can be regenerated from the project rather than from a script.

The recommended next implementation is `select_take`, not a frontend rewrite or
agent integration. It establishes the mutation boundary that those interfaces
will later consume.

## Recently completed

- `CT-0007` — added Git ignore conventions and CLI protection against accidental
  in-repository runtime projects.
- `CT-0006` — added external local project locators, materialized workspaces, an
  in-memory Project Manager, identity conflicts, and the remote-source contract.
- `CT-0005` — added Amiga Demo Reel, selectable demo templates, stable indexed
  manifest identity, packaging coverage, and multi-project fixtures.
- `CT-0004` — accepted the scoped agent-thread and provider-session contract.
- `CT-0003` — standardized frontmatter across the development memory/tracker.
- `CT-0001` — architecture, tracker, decision records, and development guidance.
- Read-only Production Control Room.
- External filesystem projects and disposable search index.
- Transition library with GLSL and WebM preview support.
- Baseline architecture review against the proposed desktop and agent direction.

## Principal risks

- allowing GUI, CLI, and agents to develop separate write paths;
- moving long-lived runtime state into a renderer process;
- confusing project-scoped state with state stored inside the project folder;
- adopting CopilotKit, an orchestrator, or a media UI library before its boundary
  is proven by a spike;
- losing generation reproducibility by discarding provider provenance;
- hiding one film's creative values inside application defaults;
- claiming frame accuracy before measuring it.

## Validation baseline

On 2026-09-20, the repository test suite passed 141 tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The source distribution and wheel build successfully. The isolated installed
wheel can instantiate both demo templates and register both simultaneously in
the Project Manager. `git diff --check` also passed.
