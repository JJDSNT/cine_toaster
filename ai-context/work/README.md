---
id: CTX-WORK-INDEX
title: Work records
type: index
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-29
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

The order of work is the ordered plan in
[`development/roadmap.md`](../development/roadmap.md).

- `CT-0052` — surround and spatial sound: research, playback chosen by the
  hardware present; awaiting the user's choice of deliverables (`ready`)
- `CT-0051` — joins between scenes in a sequence (`review`)
- `CT-0050` — transitions and J/L-cuts rendered in the assembly (`review`)
- `CT-0046` — plan step 13: the editable canvas (`done`)
- `CT-0045` — Claude Code acting through Cine Toaster (MCP first); noted for
  later at the user's request (`proposed`)
- `CT-0044` — plan step 12: the directing assistant; ADR 0018 (`done`)
- `CT-0043` — plan step 11: LangGraph spike with CoAgents and a CLI model;
  ADR 0017 (`done`)
- `CT-0042` — plan step 10: the built-in workflow with a human gate
  (SPEC-0009); picture → approval → block → takes (`done`)
- `CT-0041` — learning from gate decisions, up to reinforcement learning;
  noted for later at the user's request (`proposed`)
- `CT-0040` — voice direction: cast sheets, voice conversion (`toast
  revoice`) done; the author re-checks the ill/healthy voice later (`doing`)
- `CT-0039` — lessons between Cine Toaster and SINGULAR, with the working
  order: speech trims and loudness, job lineage, LTX rules, SINGULAR geometry,
  sequences, generation (`doing`)
- `CT-0037` — the generation unit: blocks, budgeted generation, master
  pictures by `derive`; plan step 9 done (`doing`)
- `CT-0035` — validation on SINGULAR: seven problems the demos missed,
  including the screenplay path, legacy fields, jump false positives,
  continuation, and canvas scale and speed (`ready`)

- `CT-0031` — VFX, motion graphics and titles through external tools
  (Natron, Friction, Blender + QuickTitling) (`ready`)
- `CT-0030` — backlot: locations as entities, shared sets that productions
  pin (`ready`)
- `CT-0029` — previs: light in-app previs done; Blender and motion
  references after step 9 (`doing`)
- `CT-0028` — separate project: Video Toaster-style transitions as
  gl-transitions shaders, recreated from observation (`ready`)
- `CT-0027` — camera-movement catalog, shaped like the transition catalog;
  after the blocking frame (`ready`)
- `CT-0025` — storyboard fidelity levels; blocking frame delivered
  (`doing`)
- `CT-0024` — spike: node canvases in the reference repositories and Arcads
  (`doing`; Arcads first-hand verification pending)
- `CT-0023` — two graphs: the production canvas and orchestration
  (LangGraph as a later adapter candidate) (`ready`)
- `CT-0022` — camera movement, cuts between clips, and an Arcads-style
  graph; SceneFlow spike done (`doing`)
- `CT-0021` — Fountain and Final Draft: scheduled as plan steps 3, 5, and 8
  (`ready`)
- `CT-0020` — evaluate Okay Wannabe's UI and a visual graph for transitions
  between clips (`ready`)
- `CT-0017` — SPEC-0004 slice and the Amiga reel (`doing`)
- `CT-0015` — the `cast` entity: sheet, executable reference, and
  generation lineage (`ready`, design accepted as `SPEC-0003`)

## Recently completed

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
