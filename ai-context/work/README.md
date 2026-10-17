---
id: CTX-WORK-INDEX
title: Work records
type: index
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-10-16
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

- `CT-0117` — Project Storage (captured as CT-0098 on `main`, renumbered on the merge of 2026-10-17): production disk footprint, free capacity, per-volume breakdown and render preflight (`ready`; [issue #1](https://github.com/JJDSNT/cine_toaster/issues/1)).


The ordered plan in [`development/roadmap.md`](../development/roadmap.md)
is complete; after the close-out of 2026-10-03, what remains is its
**Backlog** section. Five records stay open on purpose: CT-0020, CT-0028,
CT-0041, CT-0052, CT-0053. `CT-0064` was opened on 2026-10-13.

UX and creative-context research, made on `main` while the compositing
work ran on its branch; renumbered on the merge of 2026-10-15 from
CT-0064..CT-0077, which the branch had already used (each id keeps its
meaning in the commits and code that cite it). Their frontmatter was
normalised the same day: CT-0082..CT-0086 are `ready` (proposed, not
started); CT-0087..CT-0095 are `review` (first findings written, awaiting
the user's validation).

- `CT-0095` — Visual Lab: Core gap and UX research
- `CT-0094` — model-dependent mood and visual identity
- `CT-0093` — location consumers and spatial continuity (CT-0092's addendum)
- `CT-0092` — compound locations and situational context (Singular's hospital)
- `CT-0091` — creative context Core inventory and UX contract
- `CT-0090` — contextual creative decisions and navigation
- `CT-0089` — cognitive ergonomics across the three workspaces
- `CT-0088` — Production Awareness: situation awareness, explainable status
- `CT-0087` — the production workspace's task and information priorities
- `CT-0086` — human-centred information visibility, cognitive ergonomics
- `CT-0085` — the three-workspace wireframe, a first UX study
- `CT-0084` — the three-workspace UX vision and its validation
- `CT-0083` — integrated editing and production architecture
- `CT-0082` — Blender MCP and DCC-MCP as an agent-operated DCC interface

Compositing, the demos line and earlier:

- [CT-0118](CT-0118-sequence-storyboard-handoff.md) — a storyboard request for a
  whole canonical sequence, one consent per batch (ADR 0035; review)
- [CT-0116](CT-0116-format-intake.md) — format intake: the agent interviews
  before advancing, the person answers in the inbox or `toast intake` (review)
- [CT-0115](CT-0115-production-roles-and-model-catalogue.md) — agent review:
  declared roles, model capabilities and catalogue, role bindings; the RunPod/
  ComfyUI three layers and the format interviewer planned (doing)
- [CT-0114](CT-0114-explicit-sequence-review-work.md) — explicit agent-owned
  sequence review request in Creation, shared query/command, automatic agent
  visibility and separate GUI AI-work counts; validation in progress (doing)
- [CT-0113](CT-0113-sequence-inception-storyboard-review.md) — restore canonical
  sequence review scope, runtime work-structure context and original-source
  screenplay/storyboard comparison; context slice passed 1199 tests and is
  active on the existing LAN server; package /
  independent adherence review / sequence-first GUI still in progress (doing)
- [CT-0112](CT-0112-decision-inbox-and-stage-handoff.md) — cross-workspace
  canonical decision inbox, atomic approved stage inputs and existing-CoAgent
  storyboard publication; 1186-test regression passed; sequence acceptance
  correction tracked in CT-0113 (doing)
- [CT-0111](CT-0111-directing-and-continuity-agents.md) — reuse the existing
  Coordinator for retained shot planning and independent continuity reviews,
  existing ledger, scoped human gates and preproduction display; 1172-test full
  regression, public CoAgents/browser and read-only live LAN checks passed (review)
- [CT-0110](CT-0110-art-direction-and-visual-prevalidation.md) — Art Direction
  and actual-image prevalidation in the existing CoAgent, versioned briefs /
  findings, quota-confirmed jobs and situational GUI; 1149-test full regression,
  real CoAgents browser and visual-input smoke passed; active on LAN (review)
- [CT-0109](CT-0109-lan-gui-onboarding.md) — runtime-facing onboarding for a
  trusted-LAN/mobile GUI launch, real LAN URLs and honest WSL/security boundaries
  delivered; follow-up authorises LAN-scoped WSL NAT forwarding and automatic
  read-only startup diagnostics; Windows LAN HTTP checked and phone access
  confirmed by the director (review)
- [CT-0108](CT-0108-provider-independent-inception-runtime.md) — Inception /
  Coordinator implemented inside the existing public CoAgent, with bounded
  shared authoring tools, canonical human-direction handoff and tested GUI
  retained revisions. Provider selection remains host > environment > current
  CLI; full regression and final GUI/live checks passed (review)
- [CT-0107](CT-0107-agent-led-work-and-human-review-loop.md) — first slice:
  Inception readiness and human direction decisions delivered, with a real
  pending Demo 01 request and green regression/browser checks. Continuation
  must reuse existing CoAgents/built-in workflows, not a parallel executor;
  autonomous dispatch and specialist integration remain open (review)
- [CT-0106](CT-0106-storyboard-candidates-and-inception-inputs.md) — storyboard
  image candidates linked to shots and Inception inputs; opening-scene vertical
  slice delivered for review, three retained opening drawings, input/use links,
  form-free situational Inception and a green full regression; creative approvals and
  downstream master handoff remain separate (review)
- [CT-0105](CT-0105-creation-inception-and-stage-inputs.md) — Creation / Inception
  before the screenplay: brainstorming, rough references and explicit use of
  earlier artifact versions as later inputs; first GUI, shared candidate journal
  and staged reference jobs implemented; explicit creative correction rounds
  distinguish revision from image ancestry and approval. Latest director
  feedback recorded for follow-up: copilot-first interaction, secondary manual
  forms and a cross-module human-decision inbox; not implemented yet (review)
- [CT-0104](CT-0104-demo-driven-gui-flow.md) — rethink the GUI through Demo 01:
  first React pilot with screenplay beside proposed shots, contextual clay
  studies, assistant availability and real-data browser checks; visual-candidate
  authoring and human usability validation remain open (review)
- [CT-0103](CT-0103-demo-01-process-and-gui-incident.md) — Demo 01 incident:
  storyboard skipped, assistant omitted at launch, GUI/process and onboarding
  findings; repeatable acceptance scenario for the actual workflow (review)
- `CT-0102` — master pictures not bound to a model: the adapter by
  production, scene or shot; ADR 0025 (done)
- `CT-0101` — the `codex-image` adapter: `toast references generate`, MCP
  `generate_reference`, `toast doctor`; Gemini noted (done)
- `CT-0100` — a film's references: `references/<id>/reference.yaml`,
  `toast references`, MCP `list_references`; found by CT-0099 (done)
- `CT-0099` — Demo 01, the evolution of animation: the production and
  a trial of the tool; `~/films/demo-01` (doing)
- `CT-0098` — starting a film: `toast new`, the product guide
  (`docs/making-a-film.md`), the flow and practices over MCP (doing)
- `CT-0097` — Demo 1 (hybrid VFX): archive research before the screenplay --
  Chaplin's 1914-16 shorts, rights of the work and of each copy apart
  (blocked: paused for CT-0099)
- `CT-0096` — Foundations before the demos: the suite in parallel, a fresh
  clone checked end to end, a version's cut as OpenTimelineIO (done)
- `CT-0081` — C8: signals from models and from 3D, the audit -- the
  contract (geometric, estimated, aligned depth), records with provenance,
  the Blender and model adapters, a sequence; step 1 (signal records, ADR
  0024), step 2 (a Blender scene's passes as records, read by
  `generate.render`), step 3 (models as adapters) and step 4 (alignment
  with residuals, inverted occlusions flagged), step 5 (depth compositing
  at edges), step 6 (signal ops on GL), step 7 (signals in layers) and step
  8 (the done-when film) done; closed on the user's viewing (`done`)
- `CT-0080` — C7: time and track -- the audit, the remap's meaning, source
  against timeline time, retimed sound, exposure, tracks as records, GL, and
  the three done-when films (`done`)
- `CT-0079` — the time base: three faults measured and fixed (cut points on
  the frame grid, rates as fractions, sound in samples, `timebase.py`); every
  click within half a sample over an hour at 30000/1001; ADR 0023 --
  fractions to compute, ticks to store, the media clock's contract (`done`)
- `CT-0078` — C6b: rich typography; stages A-D done (letters with their
  own time, styles, colour fonts, Lottie as a source); the user's review of
  B and C to return to (`done`)
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
  evaluated and its interface documented (`ready`)
- `CT-0072` — the post-C2 convergence audit: one GL pipeline, one place for
  each decision, cards and stills drawn by the graph, `toast build` removed
  (`done`)
- `CT-0071` — C2: the NumPy reference (53 of 55 ops), composites and recipe
  joins in the assembly, a GL renderer checked against it, warp.surface and
  the warp wipes (`done`)
- `CT-0070` — C1: the compositing graph specified, SPEC-0012 drafted
  (`review`)
- `CT-0069` — joins shaped by a picture: mattes and overlays (SPEC-0011);
  the preview is left (`done`)
- `CT-0068` — a production declares the frame its versions are made in
  (`done`)
- `CT-0067` — beats heard and kept beside a track; shots cut to music in
  beats (`done`)
- `CT-0066` — footage declared on a shot and fetched as its take, with
  source, licence and credit (`done`)
- `CT-0065` — the reel on the assembly path: stills as takes, narration
  beside the scene and in each line's voice; bringing material in is next
  (`done`)
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
