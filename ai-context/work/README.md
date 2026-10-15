---
id: CTX-WORK-INDEX
title: Work records
type: index
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-10-13
tags:
  - work
  - tracker
  - execution
---

# Work records

This directory is the operational memory of Cine Toaster development. A work
record lets a human or another agent resume without reconstructing intent from
chat or Git history.

## Required sections

Each non-trivial record states:

- **What** — concrete scope and expected outcome;
- **Why** — product or architectural reason;
- **Done** — completed changes, kept current during execution;
- **To do** — remaining work and ordering;
- **Decisions** — choices, assumptions, and deviations from the initial plan;
- **Validation** — commands, results, and known gaps.

Use the common frontmatter fields `id`, `title`, `type`, `status`, `owner`,
`created_at`, `updated_at`, and `tags`. Work records use `type: work`. Valid
work statuses are `ready`, `doing`, `review`, `blocked`, and `done`.

Keep records concise. Stable knowledge is promoted to the focused
`ai-context/` documents or `docs/architecture/`; the work record remains the
execution history and links to those destinations.

## Work queue

The ordered plan in [`development/roadmap.md`](../development/roadmap.md)
is complete; after the close-out of 2026-10-03, what remains is its
**Backlog** section. Five records stay open on purpose: CT-0020, CT-0028,
CT-0041, CT-0052, CT-0053. `CT-0064` was opened on 2026-10-13.

- `CT-0081` — C8: signals from models and from 3D, the audit -- the
  contract (geometric, estimated, aligned depth), records with provenance,
  the Blender and model adapters, a sequence; step 1 (signal records, ADR
  0024), step 2 (a Blender scene's passes as records, read by
  `generate.render`), step 3 (models as adapters) and step 4 (alignment
  with residuals, inverted occlusions flagged) and step 5 (depth compositing
  at edges) done (`doing`)
- `CT-0080` — C7: time and track -- the audit, the remap's meaning, source
  against timeline time, retimed sound, exposure, tracks as records, GL, and
  the three done-when films (`done`)
- `CT-0079` — the time base: three faults measured and fixed (cut points on
  the frame grid, rates as fractions, sound in samples, `timebase.py`); every
  click within half a sample over an hour at 30000/1001; ADR 0023 --
  fractions to compute, ticks to store, the media clock's contract (`done`)
- `CT-0078` — C6b: rich typography; stages A-D done (letters with their
  own time, styles, colour fonts, Lottie as a source); the user's review of
  B and C to return to (`doing`)
- `CT-0077` — C6: the catalogs re-expressed -- effects, looks, elements and
  titles drawn by the one engine, on GL; no FFmpeg compositing chain left
  (`done`)
- `CT-0076` — C5: the transition catalog as recipes -- nine shaders
  re-expressed, filed by family, all on GL, generated mattes (`done`)
- `CT-0075` — C4: layers compiled into the graph, colour (difference) and
  difference keys, despill, W3C blends, one rotation and camera for the
  warps; the ADO move, a window and a keyed person on real footage (`done`)
- `CT-0074` — C3: parameters over time; eases one vocabulary, a beat's
  instant apart from the reaction, the plume on every beat (`done`)
- `CT-0073` — surfaces from Blender: an external UV mesh for `warp.surface`,
  evaluated and its interface documented (`proposed`)
- `CT-0072` — the post-C2 convergence audit: one GL pipeline, one place for
  each decision, cards and stills drawn by the graph, `toast build` removed
  (`done`)
- `CT-0071` — C2: the NumPy reference (53 of 55 ops), composites and recipe
  joins in the assembly, a GL renderer checked against it, warp.surface and
  the warp wipes (`done`)
- `CT-0070` — C1: the compositing graph specified, SPEC-0012 drafted
  (`review`)
- `CT-0069` — joins shaped by a picture: mattes and overlays (SPEC-0011);
  the preview is left (`doing`)
- `CT-0068` — a production declares the frame its versions are made in
  (`done`)
- `CT-0067` — beats heard and kept beside a track; shots cut to music in
  beats (`done`)
- `CT-0066` — footage declared on a shot and fetched as its take, with
  source, licence and credit (`done`)
- `CT-0065` — the reel on the assembly path: stills as takes, narration
  beside the scene and in each line's voice; bringing material in is next
  (`doing`)
- `CT-0064` — the Amiga reel after the 1991 Video Toaster promo: the gap
  between the tape and what is rendered today, and the order to close it;
  nothing built yet (`ready`)
- `CT-0054` — migrating SINGULAR to ~/films/singular, the validation
  milestone; layout proposed, awaiting the user (`review`)
- `CT-0053` — upscaling to 4K: SeedVR2 on takes, 4K as a delivery
  target; awaiting the user's approval of a paid spike (`ready`)
- `CT-0052` — surround and spatial sound: researched; phase 1 (a 5.1 track
  beside the stereo) done; the rest paused by the user (`blocked`)
- `CT-0051` — joins between scenes in a sequence (`done`)
- `CT-0050` — transitions and J/L-cuts rendered in the assembly (`done`)
- `CT-0046` — plan step 13: the editable canvas (`done`)
- `CT-0045` — Claude Code acting through Cine Toaster (MCP first); noted for
  later at the user's request (`done`)
- `CT-0044` — plan step 12: the directing assistant; ADR 0018 (`done`)
- `CT-0043` — plan step 11: LangGraph spike with CoAgents and a CLI model;
  ADR 0017 (`done`)
- `CT-0042` — plan step 10: the built-in workflow with a human gate
  (SPEC-0009); picture → approval → block → takes (`done`)
- `CT-0041` — learning from gate decisions, up to reinforcement learning;
  noted for later at the user's request (`proposed`)
- `CT-0040` — voice direction: cast sheets, voice conversion (`toast
  revoice`) done; the author re-checks the ill/healthy voice later (`done`)
- `CT-0039` — lessons between Cine Toaster and SINGULAR, with the working
  order: speech trims and loudness, job lineage, LTX rules, SINGULAR geometry,
  sequences, generation (`done`)
- `CT-0037` — the generation unit: blocks, budgeted generation, master
  pictures by `derive`; plan step 9 done (`done`)
- `CT-0035` — validation on SINGULAR: seven problems the demos missed,
  including the screenplay path, legacy fields, jump false positives,
  continuation, and canvas scale and speed (`done`)

- `CT-0031` — VFX, motion graphics and titles through external tools
  (Natron, Friction, Blender + QuickTitling) (`done`)
- `CT-0030` — backlot: locations as entities, shared sets that productions
  pin (`done`)
- `CT-0029` — previs: light in-app previs done; Blender and motion
  references after step 9 (`done`)
- `CT-0028` — separate project: Video Toaster-style transitions as
  gl-transitions shaders, recreated from observation (`ready`)
- `CT-0027` — camera-movement catalog, shaped like the transition catalog;
  after the blocking frame (`ready`)
- `CT-0025` — storyboard fidelity levels; blocking frame delivered
  (`done`)
- `CT-0024` — spike: node canvases in the reference repositories and Arcads
  (`doing`; Arcads first-hand verification pending) (`done`)
- `CT-0023` — two graphs: the production canvas and orchestration
  (LangGraph as a later adapter candidate) (`ready`)
- `CT-0022` — camera movement, cuts between clips, and an Arcads-style
  graph; SceneFlow spike done (`done`)
- `CT-0021` — Fountain and Final Draft: scheduled as plan steps 3, 5, and 8
  (`done`)
- `CT-0020` — evaluate Okay Wannabe's UI and a visual graph for transitions
  between clips (`ready`)
- `CT-0017` — SPEC-0004 slice and the Amiga reel (`done`)
- `CT-0015` — the `cast` entity: sheet, executable reference, and
  generation lineage (`ready`, design accepted as `SPEC-0003`)

## Recently completed (`done`)
- `CT-0038` — scene assembly from the chosen takes, as kept versions (`done`)
- `CT-0036` — screenplay editor, byte-exact and revision-checked (ADR 0016)
  (`done`)
- `CT-0034` — React stack (ADR 0015) and the read-only production canvas
  (`done`)
- `CT-0033` — spike: CopilotKit on React 19 + Vite + React Flow with the Python
  agent over AG-UI; the open path needs the Node Copilot Runtime (`done`)
- `CT-0032` — jobs runtime: durable store, previs and build jobs, cancel,
  reconcile, retry, adoption, jobs tray (`done`)
- `CT-0026` — gl-transitions as a submodule shader bank; builds run a
  transition's own shader (`done`)
- `CT-0019` — two halves of the interface, and an address for each room (`done`)
- `CT-0018` — install, doctor, offline narration, and a render (`done`)
- `CT-0016` — English schema; legacy names behind one translation point (`done`)
- `CT-0014` — evaluated OpenMontage; licence boundary recorded as ADR 0011 (`done`)
- `CT-0013` — documented production-specific tooling with demo examples (`done`)
- `CT-0012` — generation providers moved into the tool (`done`)
- `CT-0011` — one native format, read the production's YAML directly (`done`)
- `CT-0010` — closed decision loop, assembly versions, staleness (`done`)
- `CT-0009` — knowledge layer and the eyeline direction check (`done`)
- `CT-0008` — scene geometry, continuity checks, sequences, live board (`done`)
- `CT-0002` — implement canonical take selection (`done`)
- `CT-0007` — prevent runtime projects entering the source repository (`done`)
- `CT-0006` — add external project locators and the local Project Manager (`done`)
- `CT-0005` — add the Amiga Demo Reel multi-project fixture (`done`)
- `CT-0004` — specify scoped provider session bindings (`done`)
- `CT-0003` — standardize `ai-context/` frontmatter (`done`)
- `CT-0001` — consolidate the architecture and development context (`done`)

## Naming

Use `CT-NNNN-short-description.md`. Move old records to `history/` only when the
active directory becomes difficult to scan; moving a completed record is not
required.
