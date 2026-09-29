---
id: CT-0037
title: The generation unit — evidence from SINGULAR's pipeline (plan step 9)
type: work
status: ready
owner: development agent
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - generation
  - decision
  - ltx
  - real-production
---

# What

Plan step 9 opens with a decision: how many shots does one generation hold?
CT-0022 step 4 framed it as a measurement to make (1, 3 and 8 setups per
generation). SINGULAR's own pipeline has already answered it in practice
(`~/confyui/ferramentas/cena_ltx.py`, read 2026-09-29).

# Evidence

- **Blocks.** A shot's `bloco` groups consecutive shots into **one**
  generation with LTX 2.5 on a RunPod serverless endpoint (`ltx25-i2v`).
  - A block runs 1–20 s, in whole seconds.
  - The prompt joins each shot with "A hard cut transitions to a new
    shot…" and keeps setting, light and voices constant across the cuts.
- **Keyframe guides at the cuts.** Each shot's master image is a guide at
  its cut frame (a multiple of 8, for the VAE), including frame 0.
  - Measured on 1-03: without the frame-0 guide, the first frame drifted to
    another person.
- **Cuts are found, not imposed.** The model cuts at its own rhythm.
  - Measured on 2026-09-20 on 1-02A: cuts requested at 144 and 264 came out
    at 91, 190 and 283, one more than asked.
  - The clip is sliced back into shots **by content**. Each stretch is
    matched to the master image it most resembles, with a monotonic
    assignment that allows shot/reverse-shot to return to the same face.
  - It falls back to the requested cuts when the reading does not add up.
- **Single shots and continuations.** A shot outside any block is its own
  generation. A shot longer than one generation continues from the
  previous last frame: this is SPEC-0007's `continuation`.

# Proposal (for the user to confirm)

1. The generation unit is a **block**: one or more consecutive shots of a
   scene, declared per shot (`block: <id>`). A shot with no block is its own
   generation. A long shot spans generations through `continuation`.
2. A block is a record, not an adapter setting.
   - Checks: shots in one block are adjacent, share the scene, and respect
     the provider's declared limits (LTX 2.5: 1–20 s, whole seconds).
   - The brief renders one EXECUTION with several states for a block, which
     is SceneFlow's own multi-setup form (CT-0022).
3. **Cut finding** (content-based slicing of a block into shots) is a
   media-adapter step that yields per-shot takes with lineage back to the
   block's clip. It is reimplemented from the description above, not copied.
4. The first generation adapter wraps the existing endpoint through the
   jobs runtime (SPEC-0008), with cost shown before a run.

# Open questions

- Whether `block` becomes a core shot field. SINGULAR could map its `bloco`
  with `maps_to` (CT-0035).
- Spending: every run costs money on RunPod. Test runs need the user's
  approval and a budget.
