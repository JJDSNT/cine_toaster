---
id: CT-0081
title: C8 -- signals from models and from 3D, the audit before building
type: work
status: doing
owner: unassigned
created_at: 2026-10-15
updated_at: 2026-10-15
tags:
  - compositing
  - depth
  - segmentation
  - blender
  - audit
---

# What

Step C8 of `development/compositing-roadmap.md`: depth and segmentation as
signals -- from a model run on a picture (depth estimation, a
segment-anything model) or from Blender's passes (Z, object index, alpha) --
and Blender renders laid into a generated picture with an alpha matte and a
depth matte; through the generation and Blender adapters, never in the
Project Core; licences against ADR 0011. Done when a Blender-rendered object
sits behind a person in a generated picture, ordered by depth.

The user asked for C8 with C7's discipline: shared contracts for depth,
segmentation, mattes and 3D passes, whatever made them; Blender integrated
but never required; provenance and invalidation of every result (model,
version, parameters, source media, transformations); GL conformance; closing
films of real material combining footage, AI signals and 3D. And one
distinction to keep in the contract: **a depth estimated by a model is not
the geometric depth of a 3D scene**. The C6b review stays in the backlog.

Audit first, nothing built.

# The contract as it is (SPEC-0012, schema)

- Types: `signal` with a `kind`; `depth` is metric -- a distance from a
  **named camera**, scene units, near small; `depth_relative` comes from a
  monocular model -- unknown scale and shift, possibly inverse, comparable
  with nothing until aligned; `segmentation` is an integer label per pixel
  with a table; also `vectors`, `normals`.
- Validation already holds the line: `merge.depth` takes `depth` only (a
  `depth_relative` is refused by kind) and every depth it compares must
  name the same camera; `signal.align_depth` turns `depth_relative` into
  `depth`, inheriting its reference's camera; `matte.label` takes a
  `segmentation`.
- What it does not say: an aligned depth is still an **estimate** -- its
  scale and shift were fitted, with a residual -- yet once aligned it is a
  `depth` like a Blender Z pass; nothing records how it was made or how good
  the fit was. A composite cannot tell geometric from estimated depth.

# The engine as it is (reference; GL)

| Op | Reference | GL | Notes |
|---|---|---|---|
| `signal.read` | reads **one frame**: an EXR file, a `.npy`, or the first frame of a picture | no | no sequence, no clock: a Blender pass per frame cannot be read; a multilayer EXR's layer cannot be chosen (`Depth.Z`, `IndexOB`) |
| `signal.estimate` | not computed ("a model's result is recorded") | no | **no adapter** runs a model, and nothing records a result |
| `signal.align_depth` | least squares scale and shift over a region, **per frame** | no | fitted anew each frame: an estimated depth flickers in scale through a shot; no residual kept |
| `matte.label` | labels in a set | no | fine; the label table is not carried |
| `merge.depth` | per pixel, the nearest picture over the others by their alpha | no | a hard choice per pixel: at a depth edge -- hair, a soft monocular silhouette -- it aliases or haloes |
| `generate.render` | not computed ("a renderer's own scene; its result is recorded") | no | **no path** from a Blender scene to `out`, `depth`, `alpha` |
| `warp.surface` | gives a `depth` of its surface | yes | the one metric depth the graph makes itself |

Blender today: `vfx_assets/_blender/element.py` renders elements as RGBA
EXR (transparent film) and `board.py` writes a `Depth.Z` pass (metres) in a
multilayer EXR for boards -- the pieces exist, not as a render the graph
reads with its camera. Blender is found here (`~/.local/bin/blender`).

Models today: none wired. The voice environment (`.venv-voice`) holds torch
2.6 (CPU), transformers and onnxruntime -- enough to run small models on the
CPU. Licences (ADR 0011): Depth Anything V2 **Small** is Apache-2.0 (Base,
Large and Giant are CC-BY-NC-4.0: excluded); Video Depth Anything Small is
Apache-2.0 (its temporal consistency is the point); SAM 2 is Apache-2.0.

Exposure: none -- no catalog or layer record makes or reads a signal; a
layer's `depth` key is reserved ("room for 2.5D", C4) and unused.

# What C8 needs, by the user's points

1. **Contracts that say how a signal was made.** A signal record (as
   tracks are, CT-0080 step 5): `signals/<id>/` -- its kind, its camera (for
   `depth`), its **origin**: `geometric` (a renderer's pass, a surface) or
   `estimated` (a model) or `aligned` (estimated, then fitted -- with the
   method, the reference and the residual); its range and units; its clock
   (rate, origin on its media, ADR 0023); per-frame data (float EXR); the
   label table for a segmentation. The distinction the user asked for is
   then data, not a convention: an op may require `geometric`, warn on
   `aligned`, or weigh by the fit's quality.
2. **Provenance and invalidation**, as tracks have: the source media's hash,
   the model (name, version, weights hash) or renderer (Blender's version,
   the scene file's hash, the camera), the parameters; a result whose inputs
   changed is stale and refused, naming the command that makes it again.
   SPEC-0012 §5 already says non-deterministic results are recorded and
   re-running is explicit -- this makes it so.
3. **Adapters, never the Core, never required**: a model adapter (a
   subprocess in an environment that has torch; absent, the doctor says how
   to add it), and a Blender render adapter (a scene and a camera in;
   per-frame `Combined` RGBA, `Depth.Z`, `IndexOB` out; absent Blender, a
   graph with `generate.render` says what to install). Both write records;
   the graph only reads records (`signal.read` by id, `generate.render` by
   its record).
4. **Signals in time**: `signal.read` of a sequence, by its clock, as a
   source is read (reach, pre-roll, held frames) -- the C7 contract reused.
5. **Depth that does not flicker**: alignment fitted once over a stretch
   (or with a video model), not per frame; its residual kept.
6. **Edges**: depth ordering per pixel is wrong at soft edges; ordering by
   object (a segmentation or a key gives the person's matte; the depth
   orders whole objects or regions) and a soft transition where depths
   cross -- to be measured on the films before choosing.
7. **GL** for `signal.read`, `matte.label`, `merge.depth`, and the
   alignment (a fitted scale and shift is two numbers per frame: CPU, then
   a draw), with conformance tests.
8. **Exposure**: layers ordered by depth (a layer's `depth` from a record),
   a person's matte from segmentation in the records.

# Tests to write (each before its change)

A synthetic scene with known geometry (Blender: a plane and a sphere at
known distances) whose Z pass is the truth: an estimated depth aligned to it
is within its residual; a stale record is refused; a sequence is read by
its clock under a retime; `merge.depth` orders two pictures by a geometric
depth exactly and by an aligned one within its residual; soft edges do not
halo beyond a set width; GL equals the reference.

# A sequence, from the audit

1. **The signal record and its contract**: `signals/<id>/`, origin
   (geometric / estimated / aligned), provenance, staleness, clock, label
   tables; `signal.read` by id and of sequences in time.
2. **The Blender render adapter**: a scene and camera to RGBA, `Depth.Z`
   and `IndexOB` per frame, as a record; `generate.render` reads it.
3. **The model adapter**: Depth Anything V2 Small (and Video Depth Anything
   Small for shots) and SAM 2, as records, in an environment of their own,
   with a doctor capability.
4. **Alignment over a stretch**, with its residual; the record says
   `aligned`.
5. **Depth compositing at edges**: measured, then by object and with a soft
   crossing.
6. **GL** for the signal ops; conformance.
7. **Exposure** in layers.
8. **The done-when film**: a Blender object behind a person in a generated
   picture, ordered by depth -- plus the films the user asked for, real
   material with AI signals and 3D.

## Step 1 -- the signal record and its contract (done 2026-10-15)

The user's refinements, all taken: type, origin and transformation kept
apart (an alignment is a step of provenance, not an origin); the chain of
provenance rebuildable; explicit invalidation (media, files, parents,
transitively), corrections apart; time and coordinates in the contract
(clock, resolution, camera, unit, quantity, direction); quality declared or
measured, never invented; a signal a resource of the production. ADR 0024.

- `signals.py`: `record_signal` (the one command every maker will call:
  kind, origin -- or inherited from `derived_from` with a `transformation`
  -- medium, clock, camera, depth conventions, labels, maker, inputs pinned
  by hash or revision, declared and measured quality), `correct_signal`,
  `revert_signal_corrections`, `status` (stale reasons, quality or
  `unknown`, transformations), `SignalReader` (checked once; frames with
  corrections; `at` a media instant by the signal's clock). Frames as float
  EXR (OpenEXR) or .npy; labels as .npy integers.
- The contract checked at recording (`contract_problems`): a metric depth
  names its camera and unit; a relative depth has no unit; every depth says
  its quantity (distance, z, inverse); a segmentation carries its labels;
  frames are the kind's shape and one size.
- The graph: `signal.read` takes `signal` (and `of`); the walk to a medium's
  instant is now `TrackBook.media_instant`, shared by tracks and signals;
  `read_signal` is one reading for every renderer.

Limitations, recorded with how: signals are not yet on GL (`signal.read`
off GL sends a graph to the reference -- step 6); a correction replaces
values where a mask says, not a soft blend (a feathered patch when a use
needs it); a maker's own version check (is the model installed still the
one that made it?) belongs to its adapter (steps 2-3).

# Done

- Read SPEC-0012's signal types and ops, the schema's kind and camera
  checks, every signal and depth op in the reference, GL's coverage,
  Blender's scripts, the environments for models, and the licences.

# Validation

- Step 1 (`tests/test_signals.py`): depth, vectors and labels come back as
  recorded; the contract refuses a depth without camera, unit or quantity,
  a relative depth with a unit, labels without a table, unknown kinds or
  origins, frames of two sizes; an aligned estimate stays estimated, its
  history rebuildable (the model, the alignment, its reference pinned), and
  cannot be promoted to geometric, nor derived without saying how; quality
  is `unknown` when nothing was given, declared kept apart from measured;
  recording emits an event; a changed input file makes a signal stale and
  refused; staleness runs down the chain (a reference recorded again with
  other values; the medium under everything), identical values change
  nothing; data changed behind its commands is seen; corrections apply
  apart and revert, the data untouched; in the graph a signal is read frame
  by frame and at the instant its medium shows (cut later, retimed 2x); a
  node declaring another kind or camera is refused; a relative depth cannot
  reach `merge.depth`; labels are resized to the nearest; one signal serves
  two readers.
- Full suite after step 1: 934 tests pass.

- Nothing built; the audit's claims are from the code read above (the
  reference's `signal.read`, `signal.align_depth`, `merge.depth`; the
  schema's `merge.depth` camera check; `NOT_IN_REFERENCE`).
