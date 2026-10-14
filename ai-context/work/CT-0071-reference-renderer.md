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

# Done (composite shots and memory)

- **A shot's composite in the assembly**: `composite:` in the breakdown is
  parsed, checked when the scene loads (the six `composite_*` codes, under the
  practice `a-composite-is-a-checked-graph`; a take or file it names must be
  there), and rendered through the reference, the take's sound kept under it;
  a composite with no take (files and generators only) is a shot too.
  A real trial: the launch flown in over the Earth, turning in perspective,
  `music-piece` SC-030.
- **Memory**, after the first real composite was killed by the kernel at
  11 GB (clips held whole as floats, every node's value for every frame):
  - clips are decoded once to a memory-mapped file and converted to floats
    only for the frames in use; results are written as they are made;
  - each node's value is kept for the frame being made and, for a node a
    time operation reads, as far back as its farthest reader reaches
    (`node_windows`), then released; an optional byte budget evicts the oldest
    first; hits, misses and recomputations are counted;
  - mapped pages behind every reader are let go (`madvise`), from the frame
    access layer, never from an operation.

  | 1080p composite (SC-030) | anonymous | file-backed | held | time |
  |---|---|---|---|---|
  | 30 frames | 553 MiB | 497 MiB | 94 MiB, 3 buffers | 37 s |
  | 120 frames | 563 MiB | 400 MiB | 94 MiB, 3 buffers | 151 s |
  | 120 frames with echoes, one window for all | 1819 MiB | 684 MiB | 1265 MiB, 40 buffers | 159 s |
  | the same, a window per node | 1059 MiB | 685 MiB | 474 MiB, 15 buffers | 164 s, no recomputation |

- **ADR 0022 §9**, with the user: the graph, the execution plan, frame access
  and memory policy are separate; offline and real time are two strategies of
  one graph, with the policies tabled there. The roadmap's C9b carries the
  real-time requirements (deadline, buffer pool, GPU, playback cache with
  prefetch, planning, degradation by policy).

# Done (recipes and the warp wipe)

- **Transitions as recipes**: a catalog item of kind `graph` holds a
  SPEC-0012 graph with ports `from`, `to`, `progress` and its own pictures,
  checked when the catalog loads; the assembly draws its join through the
  reference, both pictures playing (`_graph_join`); the quick build refuses
  it with a reason; the Transitions room plays its preview, a clip the
  reference made from the same graph.
- **The warp wipe** the user asked for, the first recipe: the outgoing
  picture displaced along a map while the incoming one is revealed through a
  radial luma order. Used for real in the organic trial (Heat v3), replacing
  `undulating-burn-out`.
- **Edges of a warp**: a displacement or procedural warp may say `edge:
  extend` or `edge: mirror`; the first preview pulled black in from outside
  the picture, which a full-frame warp in a join never wants.
- **Tracking holds two frames**, not the clip; **beats inside a shot's
  composite**: the scene music's beats in the shot's own seconds.

# To do

- `matte.key` by colour and by difference, `signal.channel` hue and
  saturation, and `warp.procedural` bend are still refused by the reference.
- Recording a non-deterministic result in the production (SPEC-0012 §5), for
  when `signal.estimate` and `generate.render` get renderers (C8, C9).
- **Speed.** The reference is exact, not fast: the Heat scene took 6 min 23 s
  with one 2.9 s warp wipe at 1080p. A fast renderer of the graph (FFmpeg for
  what it can do correctly, GL for the rest) checked against the reference is
  the next piece of C2; real time is C9b.
- The other gl-transitions worth it re-expressed as recipes (C5, C6).
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
  slice; 688 after composite shots and memory; 691 after recipes and the warp
  wipe.
