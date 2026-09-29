---
id: CT-0037
title: The generation unit — evidence from SINGULAR's pipeline (plan step 9)
type: work
status: doing
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

# Done: blocks and slicing, at no cost (2026-09-29)

- **Core fields.**
  - `block`: shots made in one generation.
  - `generated_seconds`: how long a generation is asked to be. This is
    distinct from `duration`, the edit length. In SINGULAR, `seg` is the
    generation length and `dur` is the edit length. An earlier mapping of
    `seg` to `duration` was wrong and has been corrected.
  - `trim`.
  - The scene payload lists its `blocks` (shots, generation lengths, clip,
    contiguity). `block_not_contiguous` (warning) has a practice.
- **`blocks.py`, reimplemented from the description above** (not copied):
  - detects the clip's real cuts, ignoring the first 0.35 s, where a
    generation eases out of its still frame;
  - assigns stretches to shots in order by 32×18 picture signatures against
    each shot's reference picture: its still, `p<n>.png`, or the image of the
    shot or master it is made from (`pmA.png`);
  - without pictures, trusts one detected cut per shot; otherwise it falls
    back to the requested cuts, and says so.
- **Job kind `slice_block`.** Each slice becomes a take
  `_takes/c<nn>-block-<id>.mp4`, and existing takes are never replaced. A
  `.provenance.json` beside it records the block, clip, frames, method and
  job. Take discovery now reads that provenance.
- **Interfaces.** `toast slice <project> <scene> <block> [--dry-run]`, and a
  Blocks panel in the scene room (clip and "Slice into takes").
- **SINGULAR** maps `bloco` to `block` and `seg` to `generated_seconds`
  (commits in its git).

**Validation on SINGULAR** (on a copy): all six blocks with clips slice
exactly where SINGULAR's own tool did.

| Block | Method | Slices (s) | SINGULAR's own takes |
| --- | --- | --- | --- |
| 1-03 b4 | detected | 4.917 / 6.125 | `c08` 4.917, `c09` 6.125 |
| 1-03 b5 | detected | 4.833 / 9.208 | `c10` 4.833, `c11` 9.208 |
| 1-03 b1 | detected | 10.833 / 6.208 | `c02` 10.833, `c03` 6.208 |
| 1-03 b2 | requested (no cut found) | 11.0 / 5.04 | `c04` 11.0 |
| 1-02A b1 | content (extra cut merged; P10 returns to P8's face) | 3.792 / 4.125 / 11.125 | `c08`, `c09`, `c10` identical |
| 1-02A b2 | content | 4.5 / 9.542 | `c11` 4.5, `c12` 9.542 |

Tests: `tests/test_blocks.py` (9 tests), including a synthetic clip with an
extra cut and a returning shot.

# Open questions

- ~~Whether `block` becomes a core shot field~~ decided: it is.
- Spending: every run costs money on RunPod. Test runs need the user's
  approval and a budget.
