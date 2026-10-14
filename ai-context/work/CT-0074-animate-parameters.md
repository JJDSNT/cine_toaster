---
id: CT-0074
title: C3 -- parameters over time; the beat's instant apart from the parameter's reaction
type: work
status: done
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - compositing
  - animation
  - music
---

# What

Step C3 of `development/compositing-roadmap.md`: control how a graph's
parameters change over time, rather than adding operations. Acceptance (the
roadmap, sharpened by the user on 2026-10-14): in a real music scene the
scale answers every beat with a Bézier envelope, with no unexpected jumps,
and the reference and GL agree in time. The example is the plume (shot 12 of
SC-010 Orbit in `~/cine-toaster-demos/music-piece`), whose pulse was written
in `c1facca`.

# The user's requirements

- **Bézier is a property of interpolation**, not of `curve.beats`: the same
  ease for position, rotation, opacity, effect strength, surface parameters.
- **When a beat happens and how a parameter reacts are separate**: changing
  the ease must not move the sync.
- A test with **close beats**, where pulses meet: they overlap or replace
  each other, and which must be decided.

# Done

- Started in `c1facca`: Bézier eases (`cubic_bezier`, `ease_of`), unknown
  eases refused, the plume's pulse.
- **One ease vocabulary** (`semantics.EASE_NAMES`, `ease_problem`): the
  reference's `ease_of`, the validator and every parameter of kind `ease`
  read it. `curve.map`'s `ease` and keys' eases are validated before
  anything renders, as `curve.beats`' are.
- **`curve.beats`'s envelope**: `attack_ease`, `decay_ease` (any ease,
  Bézier included), `overlap` (`max`, `add` capped at a full pulse); its
  defaults in `semantics.DEFAULTS` (they were literals in the reference).
- **A beat peaks on its own frame.** Found by the GL-against-reference test:
  frames read curves at their centre, so with a sharp envelope a beat at a
  frame's start peaked on the frame *before* -- the sync moved with the
  ease, which is what the user asked to rule out. Each beat's peak is now
  placed at the centre of the frame it falls in.
- The plume's pulse: `attack_ease: out` (a fast rise), `decay_ease: [0, 0,
  0.2, 1]` (a smooth return).
- SPEC-0012 §6 and the `curve.beats` row.

- **The plume, assembled (SC-010 v6)**, its composite drawn by GL:
  - the scale's peaks fall on the 9 beat frames of the shot, exactly;
  - the reference and GL drew the real shot (320x180, 116 frames) within
    1.7e-5 of each other (float precision);
  - in the assembled file, the change into each beat frame against its
    neighbours: 9 of 9 beats stand out (1.19x to 8.9x; the weakest where the
    footage itself moves most). v5, before the envelope's eases, showed 8 of
    9 (its last beat 0.84x);
  - its still (`stills/SC-010/P12.png`) was adopted with the version: the
    CT-0072 path, in a real production.

# Remaining (recorded, not C3's)

- The plume's attack (0.03 s) is shorter than a frame at 29.97 fps, so its
  rise is one frame and `attack_ease` is not visible there; the spec says
  so. A slower pulse would show it.
- "On every bar" needs bars (D1b), as the roadmap said.
- Curves driven by tracks are C7.

# Decisions

- **Overlap default `max`**: a pulse is "how much the beat is felt"; two
  beats close together are felt as much as the stronger, not twice. `add`
  is there for a deliberate build-up, capped so a parameter never passes its
  `high`. "Restart" (the later pulse replaces the earlier) was not given: it
  makes the value jump down when the next attack starts.
- **The peak at the frame's centre**: a hit lands on the frame it belongs to;
  the alternative (sampling a frame's curve at its start) would change every
  curve, not only beats.

# Validation

- `tests/test_animation.py`: eases reshape the pulse and never move its peak;
  the frame a beat falls in shows the full pulse for beats at the start,
  middle and end of a frame and three envelopes; a pulse with a Bézier decay
  has no step larger than its attack's slope; close beats under `max` and
  `add` (values checked, both capped at 1, both continuous); every other
  beat; unknown eases, Bézier handles outside 0..1 and an unknown overlap
  refused by the validator; a scale pulse drawn by the reference and GL
  peaks on the same frames (12 and 30) with covered areas within 3%.
- `tests/test_convergence.py`: the reference's eases are the validator's
  names; the beat curve has no defaults of its own.
- Full suite: 712 tests pass (2026-10-14).
