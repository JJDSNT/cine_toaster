---
id: CTX-PRODUCTION-FLOW
title: The production flow — two phases
type: context
status: active
owner: project
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - product
  - flow
  - phases
---

# Two phases

Stated by the user on 2026-09-29. The flow is **screenplay → storyboard →
blockouts → master images → clips → sequences**, in two phases of different
character.

## Phase 1 — fitting the screenplay and the storyboard together

Iterative and cheap. The screenplay and the storyboard are adjusted against
each other until what will be shot is defined.

| Step | What exists | Where |
| --- | --- | --- |
| Screenplay | Fountain, FDX import/export, the editor (byte for byte, revision-checked) | ADR 0014, ADR 0016, `/app/script.html` |
| Screenplay ↔ shots | Each shot covers screenplay text; findings for lines no shot films and anchors that broke | SPEC-0006, `toast script link` |
| Storyboard | Shots and their cuts; the canvas; the brief | SPEC-0007, `/app/`, `toast brief` |
| Blockouts | Scene geometry and movement; blocking frame; light previs | SPEC-0005, CT-0025, CT-0029 |

Nothing in phase 1 costs money or waits on a model.

## Phase 2 — producing what was defined

Costly and versioned. Every result is kept, and the person chooses between
versions.

| Step | What exists | What is missing |
| --- | --- | --- |
| Cast | Cast sheets (SPEC-0003 amendment): master picture, variants, names, voice identity; the Cast room; checks for drift | Lineage of the references sent to generation |
| Master images | Discovered stills; the storyboard's best picture per shot | Generating them from blocking frame, cast and look (CT-0025 step 4, SPEC-0003) |
| Clips | Takes per shot, as versions (`c02.mp4`, `_takes/`, `_rejected/`); `select_take`; comparison; **blocks and content-based slicing into takes with lineage** (CT-0037) | The generation adapter itself (needs a budget) |
| Cuts and scene assembly | Cut records; **scene assembly from the chosen takes as kept versions** (`toast assemble`, versions panel); verdicts; restore | Transitions and J/L cuts in the assembly; speech-aware trims |
| Sequences | Sequences declared in the manifest; **sequence versions assembled from the scenes' approved versions, with verdicts** (`toast assemble-sequence`, Sequences room) | Transitions between scenes; an approved sequence feeding the film's final cut |

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
