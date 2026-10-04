---
id: CT-0056
title: Negative guidance -- what a generation must not do
type: work
status: done
owner: unassigned
created_at: 2026-10-04
updated_at: 2026-10-04
tags:
  - generation
  - providers
---

# What

Backlog "Now" item 2, specified by the user in `docs/generation.md` ("Negative
guidance / what must not happen"): a production concept, separate from the
positive instructions, visible in dry runs, preserved in provenance, carried by
each provider with the mechanism it really has, degrading honestly.

# Done

- `avoid` on the production (`project.yaml`), the scene and the shot (a core
  field); `generation.avoidance` combines them in that order, each once.
- Video (LTX): `negative_text` = the house negative (`NEGATIVE_PROMPT`, until
  now sent unseen) + the production's phrases, into the workflow's negative
  conditioning; `AVOID_MECHANISM` says so. `BlockPlan` keeps `avoid`,
  `negative`, `avoid_mechanism` (in the dry run, the API and provenance); the
  job passes them to the provider.
- Pictures (Qwen edit, no negative input): an explicit "Avoid: ..." sentence
  in the prompt; the plan says `in the prompt: the edit model has no negative
  input`.
- The brief's `AVOID` slot; the CLI's dry run prints the phrases, the
  mechanism and the negative text sent.
- `docs/generation.md` describes it.

# Validation

`tests/test_avoid.py`: the cascade; the video request carrying it natively
with the house text visible; a picture edit carrying it in the prompt and
saying so.
