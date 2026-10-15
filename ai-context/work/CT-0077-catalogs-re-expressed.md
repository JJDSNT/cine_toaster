---
id: CT-0077
title: C6 -- the catalogs re-expressed on the primitives
type: work
status: done
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

## Stage C -- looks

- `colour.lut` gains a display `view` (OCIO, e.g. ACES 2.0's film response):
  seen through it and decoded back to light. One function holds its three
  forms (`reference.lut_colours`); GL bakes a 33-point 3D table from that same
  function over a lattice even in the encoded value of x / (1 + x) -- fine in
  the shadows, reaching about 80 times white -- within 0.0007 of the reference
  on average (worst 0.005). A light at 4 times white comes out at 0.79.
- `aces-film-look` is a graph effect; its FFmpeg `lut3d` formula is gone.
  `media/grading.py` (a palette turned into a .cube) applies nothing and stays
  as a LUT maker: `colour.lut` reads its files.

## Stage B -- elements

- The element is a fragment: its clip placed (fitted within `scale`, its centre
  at x, y), laid by its blend -- screen or add for one on black, over for one
  with alpha, a colour key with despill for one on green -- at its opacity.
- `vfx.prepare_element` turns whatever form the element comes in (a video, a
  sequence, EXR, a Blender render, a splat, with a separate matte) into one
  clip with alpha, kept by what it is, transparent until its `start` -- frame
  access, so the graph needs no time operation GL lacks.
- `vfx._chain` is gone: no effect is drawn by an FFmpeg filter chain. The
  element and Blender items name their primitives too.
- Found on the way: QuickTime RLE has no grey; FFmpeg fell back to a palette
  and a matte came out black. Mattes are prepared as RGB.

## On the order of B and C (the user asked)

There is no dependency between them; C was done first as the smaller piece.
The relation is in meaning: a look graded after an element grades the element
with the shot, before it does not -- decided by the order of the shot's
`effects:`, not by the order of building. And EXR elements still enter
display-encoded, so a look's roll-off cannot reach their highlights (in the
roadmap). The graph puts `colour.lut` anywhere -- on an element before its
merge or on the result (tested); the layer record and a shot's `effects:` do
not yet offer a look on one element (in the roadmap).

## Supported is not exposed (the user's rule)

The look per layer, the look per element and the layer with a graph as its
source were first written as things to do; the user pointed out they are
things the engine already does and only the records do not say -- written as
work, they invite a second mechanism. ADR 0022 now says so, and the
compositing roadmap keeps a table of its own: *supported by the graph, not yet
exposed to the filmmaker*, each with the nodes that already do it and the
record that would compile into them.

## Stage D -- titles

- `generate.text` brought to the titles' parity: alignment (left for a lower
  third), lines and line spacing (credits), an outline and hollow letters
  (the neon tube), a reveal by word as well as by letter. One drawing of a
  text (`reference.text_picture`), uploaded by GL.
- `compositing/title_graphs.py`: the nine animations -- fade, typewriter,
  word by word, slide, grow, roll, lower third, flicker, neon -- as fragments;
  the neon's halos are blurs added as light. The Blender titles are rendered
  once into a clip with alpha and laid by the graph. `titles.py` holds no
  `drawtext`, no FFmpeg graph.
- One way of laying a treatment over a shot: `compositing/drawing.over_picture`,
  used by the effects and the titles.
- Found on the way, and fixed:
  - a title whose fades do not fit its shot stayed invisible (its keys came
    out of order); the envelope is now FFmpeg's formula, sampled;
  - sampled curves were taken at each frame's start while frames read curves
    at their centre (the first frame of a title was half seen);
  - a preview's background written `0x1a1f22` was read as black;
  - **a shot with no take, a composite and a title was assembled as a title
    card**, its composite ignored -- the card branch came first. Now its
    composite is drawn and the title laid over it (tested).
- On a real production: SC-050 v4 -- the keyed presenter, the inset, a grain
  and a lower third -- all drawn by the graph.
- `media/grading.ffmpeg_filter` (a `lut3d` string nobody called) removed.

# Remaining (recorded in the roadmap)

- The frame-access range rule (SPEC-0012): float sources clipped at white --
  before C8.
- A shot drawn in one graph rather than three passes.
- The exposures in the roadmap's table "supported by the graph, not yet
  exposed".
- C6's listed new items, with C6b.

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
- `tests/test_vfx.py` passes with every effect drawn by the graph, elements in
  each form (on black, with alpha, on green, a sequence, EXR, a separate
  matte, a Blender render) included.
- `tests/test_effects.py` (B, C): the FFmpeg chains are gone; an element is laid
  on GL as the reference lays it, for each blend, with no green left after a
  key; a look has no fixed place in the graph -- before a merge it leaves the
  picture below untouched, after it grades it -- on GL as on the reference.
- `tests/test_title_graphs.py`: every title names its primitives truly; no
  `drawtext` or FFmpeg graph left in `titles.py`; every animation is a valid
  graph and runs on GL as on the reference; a title whose fades do not fit
  still rises; a typewriter only grows; word by word in whole words; a lower
  third on the left on its bar; credits climb; a neon lights around it; text
  aligned left, in lines, hollow.
- `tests/test_composite_shots.py`: a composite with a title is drawn as a
  composite.
- Full suite after stage A: 759 tests pass (2026-10-14); after B and C: 761;
  at the close: 776.
