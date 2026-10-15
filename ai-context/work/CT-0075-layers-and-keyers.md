---
id: CT-0075
title: C4 -- layers, the ADO move, and the keyers
type: work
status: done
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
- **Keyers**: `colour` (by colour difference, in linear light -- see
  Decisions) and `difference` (against a clean plate), in the reference and
  in GL; `luma` was there.
- **`colour.despill`** (new primitive, both renderers): with the key's
  matte, the screen's share of each edge pixel is subtracted (C - (1 - m) S);
  then the screen's channel is held to the others. A colour-keyed layer uses
  it by default (`despill: false` to keep the colours).
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

  - **A person keyed** -- SC-050 v1 (new): a picture against a green screen
    given by the user (2026-10-14) keyed by colour over the Earth, its hair
    without a fringe, and the launch flown in to rest above her hand, with a
    border and a shadow; drawn by GL.
  - The user saw the launch inside the layer as still: it played, but the
    clip was the slowest of the production (SC-020's plume, slowed: 0.13
    grey levels of change a frame). SC-050 v2 and SC-030 v4 use the night
    launch of SC-010 instead (twice the change a frame, three times over the
    shot).

# The closing checks (the user's, 2026-10-14)

Before closing C4 the user asked for five checks; two found defects, fixed:

1. **`warp.transform` and `warp.surface` distinct, no duplicated
   semantics** -- they were not: each built its own rotation and camera
   distance, and one number as `rotate` turned about z in one and about x in
   the other. Now `warp.rotation` and `warp.camera_distance` decide both; a
   flat surface and a transform put the corners in the same places
   (`WarpDecisionTests`).
2. **Layers do not prevent a graph as a source** -- each layer has one
   source node feeding its chain; a `source: {graph: ...}` would change only
   that node. Documented (SPEC-0012 §4, the compositing roadmap), not built.
3. **Blend modes and premultiplied alpha** -- they did not handle it:
   `merge.blend` blended values and took the larger alpha, so a multiply
   layer blackened everything around itself. Now W3C Compositing's rule for
   premultiplied pictures, in both renderers; multiply, darken and overlay
   are layer modes.
4. **`warp.surface` in the same merges** -- tested: a surface merged over
   and blended in both renderers, no special path.
5. **Reference and GL conformant** -- the full suite, with blend
   conformance for every mode on soft edges, keys, despill and layers.

# Remaining (recorded, not C4's)

- A layer whose source is a graph (above).
- A matte that follows a moving camera: C7, tracking.
- A colour key on a screen in deep shadow needs a clean plate (the
  difference key) or more tolerance; a screen-correction plate as in
  dedicated keyers is not built.

# Decisions

- **Layers compile to the graph**; they hold no drawing of their own.
- **Where each step happens**: key and garbage in the source's frame; border,
  matte and shadow in the frame, after the layer is placed. A border drawn
  before placing fell outside a full-frame picture and never showed (found
  while writing it).
- **Colour key by colour difference** (the Ultimatte and Keylight
  lineage), after two attempts: Cb/Cr shrank with brightness (a shadow did
  not key), and chromaticity made a half-hair, half-screen strand fully
  opaque, so a green fringe stayed on the hair (seen on the user's picture).
  Colour difference reads an edge as the mix it is -- exact for a subject
  with no excess of the screen's channel, close for others -- at the cost of
  deep shadows on the screen, which need a clean plate.
- **The screen is subtracted, not multiplied out**: an edge is subject and
  screen mixed in light; multiplying by the matte keeps the screen's share.
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
- `tests/test_layers.py` (after the checks): every blend mode leaves what is
  below where the layer is not; opaque blends are their plain formulas; a
  multiply layer no longer blackens around itself; GL blends as the reference
  on soft edges, for every mode; a surface merged over and blended in both
  renderers; a flat surface and a transform turn and see alike.
- `tests/test_keyers.py` (colour difference): the screen goes, a screen a
  fifth darker goes within its tolerance, the actor stays; an edge's share is
  exact for a grey strand and close for brown hair, with no green left; the
  light thrown on a shirt is held back and skin is untouched; GL keys and
  despills as the reference does.
- Full suite: 726 tests at the first commit; 734 at the close.
