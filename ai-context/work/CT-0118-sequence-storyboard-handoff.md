---
id: CT-0118
title: A storyboard request for a whole sequence, with one consent per batch
type: work
status: review
owner: claude
created_at: 2026-10-17
updated_at: 2026-10-17
tags:
  - demos
  - storyboard
  - sequence
  - agents
---

# What

ADR 0035 / SPEC-0018 amendment: handoff targets that are a canonical sequence;
Art Direction working it scene by scene; one consent for a batch of drawings;
a sequence-wide review request; superseded handoffs leave the work list.

# Why

Demo 01 (CT-0099): the director approved what turned out to be a SC-010 P1-P3
study and objected: "a minha unidade de trabalho é uma sequência, eu ter o
storyboard apenas da cena 1 não é suficiente para eu ver o contexto visual".
Validation criterion from the director: in Singular the sequence is Genebra
(scenes 1 to 4) -- membership must come from the film's declaration.

# Done

- `stage_handoff.py`: `sequence_target`, `target_members`, `target_scenes`;
  preview from `proposal.sequence`; validation of both target shapes;
  publication anywhere in the target; `coverage`, `missing`, `superseded`.
- `creation_review.py`: `proposal.sequence` validated; Inception proposes
  storyboard work for a sequence (prompt and schema; null fields stripped).
- `agents/art.py`: sequence outline + focused scene; `plan_batch`; batch
  consent in `generate`; every unkept job of a batch left to Generation
  Operations; `keep_reference` receipt names its planned shot; review request
  over the whole target with the union of current visual reviews.
- `roles.py`: kept `art_batch`, `art_handoff_decision`; scratch `art_focus_scene`.
- Inbox and GUI: sequence labels and coverage (`targetLabel`, `targetShotCount`).
- `tests/test_sequence_handoff.py` (10).

- Demo 01, first real sequence run: the director approved The Ascent (24
  shots); Art Direction saved a brief, then plan_batch failed four times with
  an empty error -- the model left out `brief`, the lookup raised a bare
  StopIteration. Fixed: the latest brief is used when none is named, an
  unknown one is named in the error, and no receipt is ever empty
  (`_brief`, `_error`; the same in Inception and Directing). A dry run with
  the real model then corrected its own parents from the error and reached
  the single consent: "Gerar 24 desenhos de storyboard de uma vez?".
- Intake questions can be withdrawn (agent or person, with a reason, kept as
  history; `withdraw_intake`, Inception `withdraw_question`, `toast intake
  --withdraw`). Demo 01's format question, asked under the removed rule, was
  withdrawn with that reason.

# To do

1. The director's real test on Demo 01: ask Inception (Creation room) for the
   storyboard request of The Ascent; approve once; consent once; review the
   sequence. Then read-only on Singular: `sequence_target(..., Genebra)`.
2. The batch and handoff live in the thread's memory: a server restart mid-batch
   loses them (records and waits survive). Persist if it happens in practice.

# Decisions

- The SC-010 approval stays as history; the new sequence request supersedes it.
- A batch is capped at 30 drawings, one consent, sent together (CT-0115's
  batch lesson: cold starts and worker scaling).

# Validation

- `test_sequence_handoff`, `test_stage_handoff`, agent modules: OK.
