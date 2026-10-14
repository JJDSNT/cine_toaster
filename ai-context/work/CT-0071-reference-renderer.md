---
id: CT-0071
title: C2 -- the NumPy reference, the record, and FFmpeg checked against it
type: work
status: done
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
  opaque nodes: 53 of the 55 (counted wrongly as 61 at the time). New: noise and text generators; signals read from
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
- **A displace wipe** -- made first as the warp wipe the user asked for, and
  renamed when the user corrected it: a warp wipe maps the playing picture
  onto a 3D object, as the Toaster's warps did (the tape, 12:09-12:22). The
  recipe: the outgoing picture displaced along a map while the incoming one is revealed through a
  radial luma order. Used for real in the organic trial (Heat v3), replacing
  `undulating-burn-out`.
- **Edges of a warp**: a displacement or procedural warp may say `edge:
  extend` or `edge: mirror`; the first preview pulled black in from outside
  the picture, which a full-frame warp in a join never wants.
- **Tracking holds two frames**, not the clip; **beats inside a shot's
  composite**: the scene music's beats in the shot's own seconds.

# Done (the warp wipe, corrected)

The user corrected the first "warp wipe" (2026-10-14): a warp wipe is not a
2D deformation; the playing picture is mapped onto a 3D object -- the effect's
mesh -- that moves in perspective, as the Toaster's warps did (the tape,
12:09-12:22: two balls carrying the picture, a tube rolling up, a ball
shrinking to a wireframe). The gl-transitions shaders used earlier
(`inverted-page-curl`, `cube`, `doorway`) already did this inside closed
programs; now it is a primitive.

- **`warp.surface`** (SPEC-0012): the picture on a mesh of a plane, a ball, a
  tube or a page; `morph` bends the flat picture onto the shape (a radius that
  shrinks as it grows, so the ball forms rather than appears); turned about its
  own centre, moved, seen through a camera; rasterised with a depth buffer (a
  ball's far side hidden), lit from the lens, drawn at twice the size and
  reduced for its edge. A second output gives its depth for `merge.depth`.
- **`curve.keys` along another curve**: with `in`, keys are placed along that
  curve's value -- a recipe keys along its join's `progress`, whatever the
  join's length. The first recipes had keys in seconds, so the ball stopped
  halfway and stayed on screen.
- **Recipes**: `warp-ball` (wraps into a ball, spins, flies off), `warp-roll`
  (rolls into a tube, tilts, flies off), `page-turn` (turns from the right
  edge); each ends on the incoming picture alone, previews made by the
  reference. The mistaken recipe kept, renamed `displace-wipe`.

# Done (the GL renderer)

- **`compositing/gl.py`**: the same graphs drawn in float GL textures
  (RGBA32F, R32F), linear and premultiplied, with programs compiled once.
  Geometry (a transform's corners, a surface's mesh) and curves come from
  the very functions the reference uses (`transform_corners`,
  `surface_mesh`, `curve_factory`), so only the drawing differs. It draws
  sources, solids, gradients, luminance, luma, channels, mattes from signals,
  thresholds, combinations, luma keys, over, mix, blends, Porter-Duff, flat
  and perspective transforms, corner pins, surfaces (a mesh with a depth
  test, drawn twice the size and reduced), grade, invert, blur, and every
  curve except those from tracks. Anything else is refused by name and the
  reference draws.
- **Conformance** (`tests/test_compositing_gl.py`): six graphs and the three
  warp wipes agree with the reference -- within 0.001 mean for pixel
  operations, 0.01-0.02 for warps and meshes, where rasterisers differ at
  edges.
- **The assembly uses it** when GL runs here and draws every op of a
  composite or a recipe join (`gl.renderer_for`); the version's notes say
  which drew. Its cached results are kept apart from the reference's.
- **Measured** at 1080p, the ball warp wipe: 152 ms a frame in GL, 4.1 s in
  the reference. The Heat scene: 3 min 29 s, against 9 min 52 s.
- **This machine's GL** is Mesa's llvmpipe by default; with
  `GALLIUM_DRIVER=d3d12` it is the Intel UHD Graphics 620 through Windows. A
  1080p float pass: 1.5 ms on llvmpipe, 5.4 ms on the GPU; reading it back:
  8 and 18 ms. llvmpipe is the faster here.

# Done (one luma)

- **Matte joins and overlays are graphs**: `mattes.py` keeps only the checks a
  version reports (retimed, not starting black, not ending white; an overlay
  without transparency, one shorter than its join) and builds the graphs
  (`recipe`, `overlay_recipe`); the assembly draws them like any recipe, with
  GL when it covers them. The FFmpeg filters it used (`alphamerge`, `geq`,
  `overlay`) are gone: luma is computed in one place per renderer, the C2
  done-when.
- `reference.read` can fit a clip to a length (`stretch_to`, a matte to its
  join) and let it end transparent (`hold=False`, an overlay shorter than its
  join).
- The GL renderer claims its context for each frame: a shader join's own
  context had left another current ("cannot create texture").

# Decided

- **GL, not FFmpeg, is the fast renderer of the graph.** The roadmap foresaw
  FFmpeg as the first production renderer; measured, GL draws a graph about 27
  times faster than the reference even in software (llvmpipe), with the same
  geometry, and FFmpeg's compositing filters cannot meet the colour contract
  (8 or 16 bits with gamma, `overlay` without float). FFmpeg stays for reading,
  writing and the effects and titles not yet re-expressed.
- **Effects and titles move to the graph in C6**, where the catalogs are
  re-expressed as recipes; C2's own part -- joins and composites through the
  graph, luma in one place -- is done.

- `toast doctor` reports the compositing renderers: the reference's ops, GL's
  ops and the device GL runs on (llvmpipe here; a GPU through D3D12 is
  reachable and measured slower).

# To do

- `matte.key` by colour and by difference, `signal.channel` hue and
  saturation, and `warp.procedural` bend are still refused by the reference.
- Recording a non-deterministic result in the production (SPEC-0012 §5), for
  when `signal.estimate` and `generate.render` get renderers (C8, C9).
- `toast doctor` does not say which GL a machine has (llvmpipe, a GPU through
  D3D12, a native driver) nor which is faster; it should, for C9b.
- The GL renderer uploads its inputs and reads its output every frame (the
  bulk of its 152 ms); for real time, sources must stay on the GPU (C9b).
- GL lacks time operations, displacement, procedural warps, colour LUTs,
  keys by colour or difference, tracks, depth merges: those graphs fall to
  the reference.
- **Speed (before the GL renderer).** The reference is exact, not fast: the Heat scene took 6 min 23 s
  with one 2.9 s warp wipe at 1080p. A fast renderer of the graph (FFmpeg for
  what it can do correctly, GL for the rest) checked against the reference is
  the next piece of C2; real time is C9b.
- The other gl-transitions worth it re-expressed as recipes (C5, C6).
- The user (2026-10-14): the aim of the warp wipe work was to internalise the
  concept the closed shaders already had; the transitions of the music piece are
  not to be polished now. They are refined later.
- `page-turn` folds along a vertical line only; a diagonal fold (an angle),
  and the back of the page showing something else, are open.
- `warp.surface` has four shapes; tiles (the picture breaking into flying
  squares, also on the tape) and a cube need their own meshes.
- Mesh rasterisation in the reference is slow at 1080p (a Python loop over
  triangles, at twice the size): the GL renderer is where meshes belong.
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
  wipe; 697 after warp.surface and the warp wipes; 700 after the GL renderer
  and after one luma (the doctor tests pass with the new capability).
