---
id: CT-0075
title: C4 -- layers, the ADO move, and the keyers
type: work
status: doing
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - compositing
  - layers
  - keying
---

# What

Step C4 of `development/compositing-roadmap.md`: a shot holds layers, each a
source with a warp, a matte and a merge mode, animated (C3); keyers as matte
generators (luma, colour, difference); borders, a drop shadow, a garbage
matte. Done when: a playing picture is flown into a corner over another, held
and flown out with eased keyframes; a person shot on a light background is
keyed over another picture; a window is replaced by a landscape with a matte
(fixed camera).

# Done

- **Layers as a record** (`compositing/layers.py`): `layers:` on a shot,
  compiled when the scene loads (`project._expand_layers`) into the shot's
  composite -- the same SPEC-0012 graph, checked, cached and drawn by the
  same renderers. Not a second path (CT-0072's rule). Findings
  `layers_invalid` and `layers_and_composite`, enforced by the practice
  `a-composite-is-a-checked-graph`. Any number is a value, `{keys: [...]}`
  or `{beats: {...}}` (C3).
- **Keyers**: `colour` (by chromaticity, brightness divided out) and
  `difference` (against a clean plate), in the reference and in GL; `luma`
  was there. Measured in the display encoding.
- **One unit for lengths**: pixels at 720 lines, scaled to the frame
  (`semantics.pixels`), for blur, glow, morphology, grain and text, in both
  renderers. Found because a layer's border needs a width that does not
  depend on resolution: before, a blur of 4 px was a different blur in a
  180-line still than in the 1080-line cut.
- **GL draws layered shots**: `matte.shape` (uploaded from the reference's
  own rasteriser -- one drawing of a shape) and `filter.morphology`; GL now
  has 28 ops and draws every layer graph of the tests and the demos.
- **On real footage** (`~/cine-toaster-demos/music-piece`):
  - **The ADO move** -- SC-030 v3: the launch flies into the top-right
    corner over the Earth, turning in perspective, holds with a border and a
    shadow, and flies out bottom left, eased; drawn by GL.
  - **A window replaced** -- SC-040 v1 (new): Orion's cabin during Artemis
    II (NASA, public domain, fetched from Wikimedia Commons), a fixed camera;
    its two forward windows show the Earth from orbit through polygon
    mattes; drawn by GL.
- **Footage from Wikimedia**: `toast footage fetch` now names itself in a
  User-Agent (`footage.user_agent`, with no personal detail); Wikimedia
  refused FFmpeg's anonymous requests. SC-040's footage came in that way.

# Remaining

- **A person on a light background, keyed, on real footage.** The keyers are
  tested on drawn pictures (a green screen with a shadow, a light backdrop),
  and GL agrees with the reference; no suitable openly licensed clip was
  found in NASA's library, Wikimedia Commons or archive.org in this session
  (candidates were already keyed, crowded, on stage backdrops, or showed
  children). Waiting for the user: a source and licence they accept (for
  example Pexels' licence), or a clip of their own.
- Recorded in the roadmap, with how to solve them: multiply, darken and
  overlay as layer modes (a `merge.blend` that blends only where the front
  covers); spill suppression for a green screen; a matte that follows a
  moving camera (C7, tracking).

# Decisions

- **Layers compile to the graph**; they hold no drawing of their own.
- **Where each step happens**: key and garbage in the source's frame; border,
  matte and shadow in the frame, after the layer is placed. A border drawn
  before placing fell outside a full-frame picture and never showed (found
  while writing it).
- **Colour key by chromaticity**, not Cb/Cr: Cb/Cr shrink with brightness,
  so a screen in shadow did not key (found by the test).
- **Lengths in pixels at 720 lines**, the convention `generate.text` already
  had.
- **Colours in layers are as seen** (hex or display-encoded); the graph's own
  colours stay linear.

# Validation

- `tests/test_layers.py`: layers compile to one valid graph; nine kinds of
  mistakes are said, not guessed; fly in, hold and fly out (the picture
  outside, held in the corner for a second, gone); a border and a shadow
  follow the placed picture; a person on a light backdrop keyed over another
  picture; a window replaced; GL draws a keyed, bordered, shadowed, animated
  layer as the reference does; layers in a scene become its composite and
  the two mistakes are findings.
- `tests/test_keyers.py`: a green screen and its shadow go while a grey
  shirt and a face stay; softness spreads the edge; a difference key against
  a clean plate; GL keys as the reference does by colour, difference and
  luma.
- `tests/test_convergence.py`: a blur looks the same at 128 and 512 pixels
  wide.
- `tests/test_footage.py`: a remote fetch sends the tool's User-Agent, with
  no personal detail; a local one sends none.
- Full suite: 726 tests pass (2026-10-14).
