---
id: CT-0077
title: C6 -- the catalogs re-expressed on the primitives
type: work
status: doing
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - compositing
  - vfx
  - titles
  - looks
---

# What

Step C6 of `development/compositing-roadmap.md` (the user: "pode avançar").
Done when no operation exists twice across the catalogs and every item says
which primitives it uses. It closes the audit's P1 (VFX chains), P2/P3
(titles) and P6 (looks). In stages, each closed and tested:

- **A. The effects FFmpeg drew** (grain, vignette, light leak, aberration,
  glitch, shake, flash, defocus, old film, hologram, fog, mirror, crop,
  fade): fragments of the graph.
- **B. Elements** (fire, smoke, explosion, sparks over the picture): layers
  with a blend or a key.
- **C. Looks** (`lut3d`): `colour.lut` in the graph, on GL.
- **D. Titles** (`drawtext` and Blender letters): generators on layers, with
  C6b.

# Done

## Stage A

- `compositing/effects.py`: each of the fourteen as a fragment built from
  the item's parameters, with the meaning they had; a shot's effects chain in
  one graph (`graph_for`), drawn by `vfx.render_graph` -- GL when it holds
  every op, which it now does for all fourteen. Their FFmpeg formulas are
  removed from `vfx._chain`; only the look and the element remain there
  (stages B and C).
- Every graph-drawn item says its primitives (`[render] primitives`), checked
  against its own graph, and its engine is `graph`.
- Primitives added for them: `generate.gradient`'s `repeat` (stripes, rings);
  `filter.noise`'s `space` (grain in the display encoding, as video shows
  it); on GL, `generate.noise` and `filter.noise` from the reference's own
  random fields (`noise_field`, `grain_field`: drawn once, uploaded, the same
  in both renderers) and `merge.channels`.
- **A real defect found on the way**: the GL renderer was one context for the
  process; a preview drawn in a worker thread made it current in a second
  thread, GLX refused (BadAccess) and Xlib ended the process. Now one
  renderer per thread.
- Looked at on a real take (SC-010's station over the Earth): the first
  drawing had a light leak with hard edges, grain swamping the shadows (added
  in linear light) and a heavy fog; corrected and looked at again.

# Remaining

Stages B, C and D.

# Decisions

- **Effects keep their parameters' meaning**; their looks were matched by eye
  to the FFmpeg ones, in linear light: close, not identical.
- **Grain belongs to the display encoding** (`space: display`): a little
  grain in linear light becomes a lot in the shadows once encoded.
- **Random fields are drawn once**, by the reference's functions, and GL
  uploads them: the two renderers give the same grain.
- **One GL context per thread.**

# Validation

- `tests/test_effects.py`: every graph-drawn item's primitives are its graph's;
  no FFmpeg formula of theirs is left in `vfx._chain`; every effect is a valid
  graph; mirror, crop, fade, flash, defocus, vignette and aberration do what
  they say; every effect runs on GL as the reference draws it; GL draws in
  several threads at once.
- `tests/test_vfx.py` (unchanged) passes with the effects drawn by the graph.
- Full suite after stage A: 759 tests pass (2026-10-14).
