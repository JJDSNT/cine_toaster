---
id: CT-0071
title: C2 -- the NumPy reference, the record, and FFmpeg checked against it
type: work
status: doing
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - compositing
  - renderers
  - colour
---

# What

Step C2 of `development/compositing-roadmap.md`: the reference evaluator of
SPEC-0012 in NumPy with OCIO, the composite record read from the breakdown,
FFmpeg as the first production renderer checked against the reference, and
the existing joins, keys and overlays moved onto them.

# Why

ADR 0022 §5 (amended 2026-10-14 with the user): the reference defines the
right result -- float, linear light, premultiplied alpha, as the colour
contract says -- and every renderer is checked against it, so that the
renderer in use never becomes the definition of correct.

# Done (first slice)

- The validator's three robustness gaps the second outside reading found:
  `merge.depth` needs one depth per picture, all from one named camera;
  opaque nodes are checked against their renderer's ports (`opaque.gl`,
  `opaque.natron`, `opaque.blender`); required parameters for every op that
  cannot run without them, not only `matte.key`.
- `compositing/reference.py`: reading files into the working space (sRGB to
  linear exactly, any other space through OCIO; straight alpha premultiplied
  once, at the source), writing out to the display encoding; curves (keys
  with eases, noise, map, combine, progress); and 25 ops: sources, solids,
  gradients, luminance, luma, channels, matte from a signal, threshold,
  combine, shapes with coverage, luma key, over, mix, blend modes,
  Porter-Duff, channels, 2D transform, grade, invert, blur. An op it does not
  have is refused by name.
- Writing it found one more parameter named `op` (Porter-Duff's), the same
  clash as `curve.map`'s: renamed `how`, and a test now forbids any op a
  parameter named `op`.
- **The first conformance test**: the `luma` join as the FFmpeg matte renderer
  draws it, against the reference evaluating the `luma-wipe` example graph.
  The share revealed agrees within 1 % at every point of the join; pixels
  more than 0.1 apart stay under 4 %, all at the edge (FFmpeg works in 8-bit
  4:2:0 with a harder threshold). A first measurement was wrong -- it trimmed
  frames without resetting time, so FFmpeg repeated them -- and was redone
  before anything was concluded.

# Done (second slice)

- The reference evaluates every op of SPEC-0012 except the two that are
  recorded, never computed by it (`signal.estimate`, `generate.render`), and
  opaque nodes: 61 ops. New: noise and text generators; signals read from
  EXR, NumPy or image files; depth aligned (least squares, or by hand) and
  merged by depth per pixel; labels; warps in perspective (a 3D turn as a
  homography), corner pins (by corners or a track), displacement, ripple,
  swirl, lens; colour curves, LUTs (`.cube` applied in the display encoding,
  OCIO looks), posterise, solarise, hue cycling; sharpen, glow, edges, erode,
  dilate, grain; time remap, offset, frame blend, echo; tracks read or
  measured by OpenCV (`tracking.py`: points and planes; a camera solve is C7);
  curves from tracks and from the music's beats.
- `identity.py`: a node's identity per SPEC-0012 §5 -- its op, parameters
  (files by content, curves by their own identity), inputs, the colour,
  time and size context, the OCIO config's own cache identity, the renderer
  and NumPy version. `reference.render` keeps results by that identity in a
  disposable cache (`~/.cache/cine-toaster/composite/`, half floats).
- Every example graph the reference can run, it runs (`ExamplesEvaluateTests`).
- SPEC-0012 §2 now says colours given as parameters are in the working space.

# To do

- `matte.key` by colour and by difference, `signal.channel` hue and
  saturation, and `warp.procedural` bend are still refused by the reference.
- Recording a non-deterministic result in the production (SPEC-0012 §5), for
  when `signal.estimate` and `generate.render` get renderers (C8, C9).
- The composite record read from a shot's breakdown (`composite:`) and a
  join's recipe from the catalog, rendered in an assembly.
- FFmpeg as a renderer of the graph for the ops it can do correctly, with a
  manifest; conformance cases for each, at more sizes, rates, bit depths and
  both alphas.
- `mattes.py`, the VFX keying and laying, and the overlay moved onto them.

# Validation

- `tests/test_compositing_reference.py` (10): sRGB round trip; a dissolve
  mixes light (0.5 linear is 0.735 encoded); straight alpha premultiplied once;
  the luma wipe example reveals the centre first and starts and ends right;
  shapes have edge coverage and follow a curve; a transform leaves
  transparency; curves hold and ease; refusals; a file read into linear.
- `tests/test_compositing_schema.py` (12), `tests/test_compositing_conformance.py` (1).
- `tests/test_compositing_reference_more.py` (14): perspective, corner pin,
  displacement, swirl; depth order and alignment; posterise, hue turn,
  dilation; offset and echo; a point tracked to within 1.5 pixels; a beat
  curve peaking on its beat; identities that move only with what changed and
  know files by content; the cache's hits and misses; every runnable example.
- Full suite: 665 tests pass (2026-10-14, at b87342d); 679 after the second
  slice.
