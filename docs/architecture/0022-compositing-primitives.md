# ADR 0022: Composition is a typed graph of primitives, not a collection of effects

Status: accepted (2026-10-14, CT-0069; §5 amended the same day, before C2; §9 added during C2). Directed by the user, amended twice
the same day -- for the primitives the first list missed, and after an outside
review the user brought -- and accepted on the user's word with the review's
recommendation. This text consolidates the decision; "How it was reached"
keeps the history.

## Context

Cine Toaster grew three catalogs, each with its own renderer: transitions
(GLSL shaders, FFmpeg stand-ins), VFX (FFmpeg filters, Blender, Natron) and
titles. SPEC-0011 added a fourth way to draw: a join shaped by a matte.

Built that way, the same operation is written again in each place. A matte
existed three times before anyone named it: the VFX catalog keys a stock
element on green and lays it with its alpha; `mattes.py` turns brightness into
a mask for a wipe; the `luma` shader does the same on the GPU. A luma key, a
luma matte for a layer and a luma wipe are one piece of information used three
ways. The catalog filed `displacement` (which moves pixels) beside `luma`
(which reveals them) as if they were the same kind of thing.

Colour is treated two ways. Composition happens in display-encoded 8-bit
4:2:0 (`mattes.py` mixes in `yuv420p`; its luma is FFmpeg's Y, whatever matrix
the file declares), while `color.py` already handles scene-linear EXR and
premultiplied alpha from Blender. Two renderers can implement the same merge
and disagree for that reason alone.

## Decision

### 1. Primitives, defined once, independent of any renderer

Eight operations on pictures:

- **Signal**: a value per pixel taken from a picture -- luma, alpha, a colour
  channel, hue, saturation -- or produced beside it: depth (a Blender Z pass, a
  depth model), motion vectors, normals, a segmentation. Luma is the most used
  instance, not the primitive.
- **Matte**: how much of a layer is seen, pixel by pixel. From a file, a
  picture's alpha (an **alpha matte**: a Blender render placed on a generated
  picture), a signal (a **luma matte**, a depth matte), a key (luma, colour,
  difference), a shape, or a generated picture. A matte's own operations --
  invert, union, intersection, difference, grow, shrink, feather -- are filters
  and merges applied to a matte, not further primitives.
- **Merge**: how two layers combine -- over, under, in, out, atop
  (Porter-Duff) and blend modes (screen, add, multiply, overlay, difference).
- **Warp**: a spatial transformation -- move, scale, rotate in perspective,
  corner pin, displace along a map, ripple, bend -- with parameters that may
  change over time.
- **Colour**: a function of each pixel's colour -- a LUT, curves, levels, a hue
  shift, posterise, solarise, colour cycling (the Toaster's ChromaFX).
- **Filter**: a function of a pixel's neighbourhood -- blur, sharpen, glow,
  defocus, edges, erode, dilate.
- **Time**: a picture at another moment -- retime, speed ramp, freeze,
  reverse, frame blending, an offset between layers, feedback (trails and
  echoes, the ADO's Infinity).
- **Generate**: a picture made from parameters -- solid, gradient, noise,
  shapes, text, particles, a render.

Two that are data, not operations on pixels, and feed every operation:

- **Track**: where something is in each frame (a point, a plane, the camera),
  in a format of its own, whatever made it -- OpenCV, Blender, a person.
- **Animate**: any parameter changing over time -- keyframes with easing, or a
  value driven by data (a track, the music's beats, CT-0067).

### 2. Families and recipes are built from them

A **wipe** merges two pictures through a matte whose coverage is driven by
the join's progress: geometric (a formula), luma (a picture's signal as the
order), custom (a moving matte). A **warp wipe** is a wipe with a warp on each
picture driven by the same progress. A luma key is a layer whose matte is its
own luma, inverted; a matte painting a layer whose matte isolates a window.
Transitions, effects, keys and titles in the catalogs are **recipes**: they
name a combination and give it editorial guidance; they never reimplement an
operation. The catalogs are filed by family -- for transitions: dissolves,
wipes (geometric, luma, custom), warps, warp wipes, moves.

### 3. A composite is a typed graph, and a production record

Nodes are operations; edges carry typed values -- picture, matte, signal,
sound, track, curve, metadata -- and a connection of the wrong type is refused
before anything renders. A shot's composite and a join's recipe are data in
the breakdown; the filesystem stays authoritative. This is a third graph,
distinct from the two of CT-0023:

| Graph | What it is |
|---|---|
| Production (the canvas) | the film's work, organised visually |
| Orchestration | agents, tools and steps that run |
| Composition | how pictures, mattes, layers and operations make a result |

The canvas may show a composite and orchestration may run one; neither is it.

### 4. A colour contract

- A **working space**, scene-linear, with conversions in and out through OCIO.
- Each edge says whether its alpha is **premultiplied or straight**.
- Each value has a **precision** (8-bit, 16-bit, float); HDR is carried, not
  clipped, in the working space.
- **Luma is an operation with explicit weights.** It names its transform or
  coefficients; Rec.709 in linear light is the default, not the definition, so
  HDR and other spaces can give their own. **Luminance** (linear light) and
  **luma** (from encoded values) are different quantities, and an operation
  says which it uses.

### 5. Execution: a reference, renderers, and a planner for the whole

The **reference** is an evaluator in NumPy with OCIO: float, linear light,
premultiplied alpha, exactly as the colour contract says. It is the
definition of the right result, made executable; it is not meant to be fast.
The **renderers** do the work: FFmpeg (decoding, encoding, and the operations
it can do correctly, for production), GL (the interactive preview and
accelerated composition), Blender, model runners such as ComfyUI, OpenCV,
Natron (specialised operations). Each implements primitives and declares
which, under the same contract for what goes in and out, and each is
checked against the reference -- never the reverse. A fast renderer does not
become the definition of correct by being the one in use, and the colour
contract is never changed to suit a renderer's limits.

(Amended 2026-10-14, before C2, with the user: the first text made FFmpeg the
reference. Several of its compositing filters work only in 8 or 16 bits with
gamma, and `overlay` takes no float format, so as a reference it could meet
the contract only with workarounds.)

 A graph
may be run whole by one renderer that has all its nodes, or **split by a
planner** across several, results handed over as files in the working space;
the cost and place of each part (local, Runpod) are recorded as jobs already
are. The two are distinct: a renderer's conformance does not depend on the
planner.

### 6. Identity, cache and records

Each node's identity is a hash of its operation, parameters, renderer version
and inputs' identities; a result is found by it, and a change invalidates
exactly what depends on it. A cache is disposable (AGENTS.md). A result that is
expensive and wanted -- a generated matte, a segmentation the filmmaker
approved -- is **promoted to a production record** (a take or an asset, with
provenance), not kept only in a cache. A node that is not deterministic (a
model with a seed) says so; its result is recorded, not recomputed.

### 7. Conformance is continuous

That a recipe gives the same pictures on every renderer that claims it is
tested from the first renderer on, within a tolerance, across sizes, rates,
bit depths and alpha -- not saved for the end.

### 8. Room for 2.5D

The model must admit layers placed in a space with a virtual camera, depth,
parallax and occlusion, without requiring a full Blender scene: a warp in
perspective plus a depth signal per layer. Not required by the first
specification; not to be precluded by it.

### 9. The graph is separate from how it is executed

One declarative graph; several ways to run it (decided 2026-10-14, while C2's
memory was being fixed, with the user's direction for real time). Four
things are kept apart, and the primitives assume none of them:

- **the graph**: contracts, parameters, time and dependencies -- nothing about
  files, order, or where results live;
- **the execution plan**: in what order frames and nodes are made, which run
  together, what is fused or precomputed;
- **frame access**: how a picture reaches a node (decoded once to disk and
  mapped, streamed, from a GPU texture, from a stream) -- and its page policy;
- **memory policy**: for each result, its temporal dependency (which frames
  its consumers read), its **retention** (how long it must stay, computed
  by the executor from its consumers' declared reach, the largest of them,
  for that result only), where it is cached under what budget, and when it is
  **released** (after its last consumer).

Two strategies follow, from the same graph:

| | Offline (the reference, final renders) | Real time (preview, live; C9b) |
|---|---|---|
| Aim | quality, determinism, cache, incremental | latency, a deadline per frame (41.7 ms at 24 fps, 33.3 at 30, 16.7 at 60) |
| Reading | sequential first | with prefetch |
| Pages | dropped after use | kept for the playback window, behind and ahead |
| Cache | reuse within a memory budget | low latency, predictable |
| Buffers | bounded | preferably pre-allocated, from a pool |
| GPU | optional | often required |
| A late frame | waits | an explicit policy: lower resolution, a proxy, or the previous frame; the final render is never degraded |

The page and buffer policies belong to frame access and the executor, never to
an operation: a primitive is written once and runs under either strategy.

Not every operation has to run in real time, and the Video Toaster did not
ask that either: its switcher worked live while LightWave rendered scenes
ahead of time, and the two met in the production (the user, 2026-10-14). So
each node of a composite is run in one of four ways, chosen by the executor
from the node's dependencies and what is available:

- **live**, on the CPU within the deadline;
- **accelerated**, on the GPU;
- **precomputed**: a subgraph whose inputs do not change while playing is
  rendered ahead and read back by its identity (§6), like a pre-rendered clip;
- **offline**: a node no live executor can run (a fluid simulation, a model)
  is rendered beforehand and its result recorded in the production (§6), then
  used like any other picture.

One composite may combine them -- a pre-rendered LightWave-like element under
a matte and a warp driven live -- wherever its contracts and dependencies
allow. C9 establishes how results made by different mechanisms coexist in one
composite; C9b adds playing them within a deadline.

## Consequences

- The order of work is `ai-context/development/compositing-roadmap.md`
  (C1-C11); SPEC-0012 specifies this decision first.
- SPEC-0011's matte and luma become the first implementations of matte and
  signal; `mattes.py` is their FFmpeg form, the `luma` shader their GL form,
  already checked against each other. Their colour handling changes to the
  contract.
- The transition catalog's `category` becomes a family; VFX items that are a
  primitive with a parameter leave the VFX catalog; element effects become
  layers with a matte.
- Adding a renderer (ComfyUI, for example) is a bounded piece of work: the
  primitives it implements, tested for conformance.

## How it was reached

- The user named four ideas while SPEC-0011 was built: matte is a compositing
  resource, luma is information that feeds many effects, warp a family of
  spatial transformations, wipe a family of mask-based transitions -- and
  wanted the **warp wipe**.
- Asked whether a primitive was missing, the list was checked against what a
  compositing engine cannot do without: signal (luma is one), merge, colour,
  filter, time and generate were added, with track and animate as data; wipe
  and warp wipe were recognised as families.
- An outside review the user brought asked for a typed graph, a colour
  contract, execution across renderers, node identity and continuous
  conformance, all taken after being checked against the code; two of its
  points were corrected (a cache cannot hold what is wanted; the composition
  graph is not the canvas's nor orchestration's). Its second reading asked
  for luma's weights to be explicit rather than Rec.709 by definition, for
  luminance and luma to be told apart, for 2.5D to be left room, and for this
  text to be consolidated rather than amended: done here.
- ADO is the Ampex Digital Optics.
