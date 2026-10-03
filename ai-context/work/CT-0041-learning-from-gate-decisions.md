---
id: CT-0041
title: Learning from gate decisions — fewer wrong pictures and takes (reinforcement learning, later)
type: work
status: ready
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - learning
  - gates
  - generation
  - future
---

# What

The user asked (2026-09-29) to note, for later analysis, the possibility of
using reinforcement learning to reduce the number of errors: pictures and
takes that a person has to refuse.

# Why it is possible now

Every human gate (SPEC-0009) is a labelled example, kept as a production
record. Each one holds:

- the candidates offered, and which one was chosen;
- for a refusal, **what was wrong**: a closed list of reasons
  (`subject_moved`, `identity`, `geometry`, `light`, `detail_lost`,
  `anatomy`, `other`) plus free text. Both are required for a refusal since
  2026-09-29, because this is the useful half of the data.

Beside each candidate, the provenance records everything that was sent:
model, prompt (by shot), seed, reference pictures with digests, size, edge
score, and cost. The spend ledger adds what each attempt cost.

So the data for preference learning accumulates as a side effect of
directing, with no labelling effort.

# Options, cheapest first

1. **Feed the refusal into the next attempt.** (Done 2026-09-30: each reason
   becomes an English instruction (`pictures.CORRECTIONS`), and the
   director's text is added as "Correction from the director: …"; both are
   kept in the new version's provenance. Not yet measured: whether a
   correction written in Portuguese helps or confuses the editor.) A `changes_requested`
   decision's reasons and text amend the next request, for example "keep her
   head where image 1 has it". No learning, and immediate. Open question:
   the note is in the director's language, while the model prompts are in
   English.
2. **Count.** Refusal rate by reason × model × prompt clause × kind of
   shot, written as dated knowledge claims (ADR 0009). This tells which
   clause or model to change, and it is evidence rather than folklore.
3. **Automatic checks as reward signals.** Measure what people keep
   refusing, for example whether a subject moved from its position in the
   render (a detector or segmentation compared against the blockout). Use
   the measurement to discard or rank candidates before a person sees them.
   The edge score was the first such check, and it missed exactly that case
   (knowledge `qwen-image-edit`).
4. **A learned preference model.** Approved against refused candidates
   form pairwise preferences. Train a small reward model to rank best-of-n
   candidates, so the person sees the likeliest good ones first. This
   reduces wasted human attention and paid regenerations.
5. **Reinforcement learning proper.** Fine-tune a generation or prompt
   policy against that reward (RLHF, DPO or similar), for example as a LoRA
   on an open model. This needs far more decisions than one film produces,
   a licence check on the model (ADR 0011, and the LTX licence), and GPU
   budget.

# Constraints to keep

- The gate stays the person's decision. Learning may rank, filter or
  propose, never approve. An agent deciding a gate is SPEC-0001's permission
  question.
- Learned models are derived, disposable state, never production truth.
- Data stays per production unless the author chooses to pool it.

# When

After enough decisions exist to count, which means after SINGULAR's
production runs through the workflow. Start with options 1 and 2. They
need no model and would show whether 3 to 5 are worth doing.
