---
id: CTX-PRODUCTION-FLOW
title: The production flow — two phases
type: context
status: active
owner: project
created_at: 2026-09-29
updated_at: 2026-10-16
tags:
  - product
  - flow
  - phases
---

# Two phases

Stated by the user on 2026-09-29 and extended on 2026-10-16 with a creative
entry before the screenplay. The flow is **Creation / Inception → screenplay
↔ storyboard → blockouts → master images → clips → sequences**, with the two
production phases below. Activities can be revisited; a film's scenes need not
all be at the same stage.

## Agent-led progress and the human's role

Director correction (CT-0112): the work/review unit is the **sequence**.
Scenes/shots can be internal subtasks or clearly labelled partial studies;
they do not replace a reviewable sequence delivery. Inception -> storyboard
needs an independent agent comparison against exact Inception intention and
reference versions, screenplay beats and the ordered storyboard, including
progression, continuity, deviations and gaps. The human must see that same
comparison and evidence before accepting the transition. Pixel review against
a creator-authored visual brief alone does not prove narrative adherence.
This sequence-level review package/validator is not implemented by CT-0112's
first existing-shot handoff. Demo 01's SC-010 opening direction request must
not be described as approval of sequence `the-ascent` or of this transition.

CT-0113 now supplies this work contract and the canonical ordered sequence
roster to the implemented runtime roles and fresh reviewers. Coordinator and
Inception can explicitly query `work_structure` by sequence/scene ID. This is
production context, not a runtime read of this development document; the full
sequence comparison/adherence validator remains in progress.

Director clarification (CT-0107): for active authorised work, the agent either
works toward a complete scoped deliverable or asks the human for a concrete
decision/direction it needs. Artifacts sitting in a gallery with no owned next
work and no actionable review request are a broken handoff, not a workflow.
The GUI situates the person: what the agent is doing, what is ready for review,
what decision is needed and what follows it. A review must identify exact
versions and scope; approval of an opening draft is not approval of the whole
film or its masters. Rejection with direction feeds a retained new version.

Completion, explicit pause/cancellation and genuine permission/capability
failures are visible stops. This is not permission for unbounded generation,
invented running states or treating every missing output as a human question.
CT-0107's first slice records destination-specific Inception assessments and
human direction decisions (ADR 0028), exposing enough-to-proceed judgments,
gaps and a scoped recommendation. Approval is not final storyboard/master
approval. Automatic next-task dispatch is not implemented; its instruction is
recorded as not dispatched, never as a fictitious running job. CT-0108 now adds
human-interaction-driven continuation through the existing CoAgent: after a
saved direction, the GUI can initiate another bounded Coordinator/Inception
turn, which rereads that exact decision. This is not durable background dispatch;
the retained instruction alone is not proof of a live run. Existing
block-generation workflows cover only part of the broader continuation loop.

## Creative entry — Creation / Inception

The director requested a preceding GUI module for brainstorming ideas and
generating rough references (CT-0105). It develops intention, alternatives,
visual explorations and chosen inputs for a screenplay. The first workspace is
implemented at `/app/creation.html`: versioned candidates, reference comparisons,
recorded exploration/correction rounds and explicit screenplay candidate inputs
(ADR 0026, SPEC-0013). Exploratory generation reuses existing reference records
and adapters through staged jobs (CT-0100/0101). Canonical screenplay promotion
remain outside that slice. CT-0106 adds retained storyboard drawings for the
canonical screenplay's existing shots, with explicit reference inputs and
two-way navigation; it does not invent shot coverage for an unpromoted draft.

Outputs from one activity can become specific inputs to a later one. Preserve
artifact versions and distinguish inspiration, declared direction and actual
provider inputs. Choosing an exploration for the screenplay does not approve
it as a cast master or storyboard frame. A newer upstream version never
silently replaces a downstream input.

CT-0110 adds Art Direction and independent Visual Prevalidation inside the same
CoAgent (ADR 0030): retained visual briefs and criteria, actual raster inspection,
advisory findings and quota-confirmed reference jobs. Failed alternatives remain;
human creative approval is separate. A current successful review can support
the existing direction gate; changed briefs/material invalidate it. Unsupported
visual transports stop honestly. Long jobs may outlast the bounded agent wait;
another interaction is needed for later reasoning, not a new dispatcher.

This creative entry may use model quota or paid generation, with cost visible;
it is distinct from producing the defined shots. The planning-only path stays
free. A film imported with an existing screenplay can begin there without
inventing inception records or passing another gate.

## Phase 1 — fitting the screenplay and the storyboard together

Iterative and cheap. The screenplay and the storyboard are adjusted against
each other until what will be shot is defined.

CT-0111 adds a bounded Directing/Continuity proposal-review slice to the existing
Coordinator/CoAgent (ADR 0031). Linked screenplay scenes can yield versioned
shot proposals; an independent textual reviewer reuses the existing canonical
continuity ledger and computed checks. The preproduction GUI shows scope,
evidence, versions and the existing human direction gate. Human changes can
produce another retained pass. Neither a proposal nor its approval rewrites
canonical shots or counts as storyboard approval. The proposal-to-canonical
shot/image handoff remains a capability gap, not an implicit transition.

CT-0112 implements the scoped existing-shot storyboard slice (ADR 0032):
**Approve & advance** adopts exact inputs for displayed scene/shot targets,
then the same CoAgent can develop/publish retained drawings through existing
reference jobs and storyboard commands. New generation requires separate quota
consent. Canonical shot-plan rewriting and final storyboard approval are still
separate. The cross-workspace **Awaiting you** inbox shows real saved gates,
origin links and retained outputs; unfinished work is not labelled running.

| Step | What exists | Where |
| --- | --- | --- |
| Screenplay | Fountain, FDX import/export, the editor (byte for byte, revision-checked) | ADR 0014, ADR 0016, `/app/script.html` |
| Screenplay ↔ shots | Each shot covers screenplay text; findings for lines no shot films and anchors that broke | SPEC-0006, `toast script link` |
| Storyboard | Shots and their cuts; the canvas; the brief | SPEC-0007, `/app/`, `toast brief` |
| Blockouts | Scene geometry and movement; blocking frame; light previs | SPEC-0005, CT-0025, CT-0029 |

Writing, planning and computed previews in phase 1 need no model call. Optional
generated story drawings may consume quota or money; disclose and authorise
that separately rather than implying all visual exploration is free.

A film starts with `toast new` (CT-0098): empty, or from a screenplay with
one breakdown per screenplay scene, linked and with no shots yet. The
product-facing statement of this flow, for people and production agents,
is `docs/making-a-film.md`, served over MCP as `how_to_make_a_film`; keep
the two in step.

## Phase 2 — producing what was defined

Costly and versioned. Every result is kept, and the person chooses between
versions.

| Step | What exists | What is missing |
| --- | --- | --- |
| Cast | Cast sheets (SPEC-0003 amendment): master picture, variants, names, voice identity; the Cast room; checks for drift | Lineage of the references sent to generation |
| Master images | Discovered stills; the storyboard's best picture per shot | Generating them from blocking frame, cast and look (CT-0025 step 4, SPEC-0003) |
| Clips | Takes per shot, as versions (`c02.mp4`, `_takes/`, `_rejected/`); `select_take`; comparison; **blocks and content-based slicing into takes with lineage** (CT-0037) | done since: generation through adapters (`toast generate`: LTX, ComfyUI, Qwen Edit on Runpod), its cost allocated from the billing (`toast finops`); left: 4K finishing (CT-0053) |
| Cuts and scene assembly | Cut records; **scene assembly from the chosen takes as kept versions** (`toast assemble`, versions panel); verdicts; restore | done since: transitions drawn by the compositing engine, J- and L-cuts, trims that follow the speech (`toast transcribe`) |
| Sequences | Sequences declared in the manifest; **sequence versions assembled from the scenes' approved versions, with verdicts** (`toast assemble-sequence`, Sequences room) | joins between scenes done (CT-0051); left: an approved sequence feeding the film's final cut |
| Compositing, VFX and titles | One graph per shot drawn by an exact reference and by GL (ADR 0022): layers, keys, mattes, transitions, titles, time operations, tracks; depth and segmentation from models and Blender as records (ADR 0024) | defocus by depth, grading a render to its plate, a solved camera; a compositing view for the filmmaker (C11) |

## The gate between them

Moving a scene from phase 1 to phase 2 is a decision: the storyboard is
approved as what will be produced. It belongs in the production record, as a
human gate (architecture invariant), not in chat. It is modelled
(2026-09-30, SPEC-0009): `approve_storyboard` / `reopen_storyboard`, from
the scene room ("Approve the storyboard") or `toast storyboard approve`.

- The gate records who approved, when and why, and the breakdown's digest
  at that moment. A later change to the breakdown shows as "changed since
  the approval".
- Only a person decides it.
- It blocks nothing. The scene shows its phase, and the assistant knows it.
