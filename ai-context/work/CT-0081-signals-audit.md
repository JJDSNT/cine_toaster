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

## Step 2 -- a scene's passes, rendered apart (done 2026-10-15)

The user's cautions, each answered:

- **A camera contract**, not a name: `render.json` keeps, per frame, the
  projection, lens and sensor with its fit, shift, clipping, the matrix
  camera to world, and the intrinsics in pixels derived from them
  (`renders.intrinsics`), with the conventions (looks down -Z, +Y up; world
  Z up; rows down) and the unit (metres per scene unit). The signals name the
  camera `<render>/<camera>`; `generate.render` refuses another.
- **Independent passes sharing time and space**: the picture (Combined,
  premultiplied, scene-linear in the recorded working space) is a medium,
  not a signal; depth and object index are signals of it, with the
  render's clock, one size; the graph reads all three at one frame.
- **Z measured, not assumed**: Cycles' Z is **planar** -- on a wall square
  to the camera at 10 m it is 10.0000 at the centre and the corners, where a
  distance along the ray would be 11.5016. Declared `quantity: z`; the test
  unprojects every pixel through the recorded camera and finds the wall's
  plane, the ball's sphere and the box's faces, every frame of a dolly.
- **A stable object table**: meshes sorted by name, numbered from 1, 0 for
  nothing; renaming an object renumbers. Limits documented in `renders.py`:
  Z and index are not anti-aliased (one surface per pixel while the
  picture's edge is a filtered mix), and a transparent surface writes its
  own. Nothing hit is +inf.
- **Reproducibility and invalidation**: Blender's version, engine, samples,
  working space, pixel filter, the scene file and every file a .blend
  reaches (by hash, and refused when outside the production), the script's
  hash, each picture frame's hash. `renders.status` names every reason a
  render is stale (and its signals', through `record_signal`'s inputs); a
  stale render is refused until rendered again.
- **Rendering and reading apart**: `render_passes` runs Blender (a
  subprocess, `vfx_assets/_blender/passes.py`); `generate.render` with
  `render` reads the record through `RenderReader` and never runs anything;
  without it the reference refuses the op, naming the command.
- **No second store, no Blender in the Core**: depth and labels go through
  `record_signal`; the adapter is outside the Core.

Found and fixed: Blender 5 writes a multilayer EXR as **one part per pass**,
and `color.read_exr` read only the first -- a `signal.read` of such a file
got Combined's red, not depth. `color.exr_layers` reads every part;
`read_exr` takes a multilayer file's Combined as its picture.

The user's review of step 2 (2026-10-15), four checks before closing, each
now held by a test:

- **Multipart reading by name, never by guess.** `color.exr_layers` groups
  a file's channels into layers across every part (one part a pass, as
  Blender 5 writes; one part for all, as Blender 4 did; a plain file) and
  refuses two layers of one name (two view layers' Depth) instead of keeping
  one. `color.exr_layer` takes a layer by name, or a file's only one;
  `signal.read` of an EXR takes `layer`, refuses several layers unnamed
  (listing them) and a layer whose channels are not the kind's (an RGBA file
  is not a depth by its red).
- **Object identity across frames**: a post the dolly passes (seen, then
  less, then gone) and a drone flying in (absent, partial, whole) keep their
  numbers; every frame uses only the table's; each label's pixels lie on its
  own object's surface, the moving one at its keyed place; re-rendering
  gives the same table.
- **Invalidation of render and signals together**: a moved object, a
  changed camera (in a recipe), a texture a .blend reaches (pinned by hash;
  one outside the production refused), and the passes script each make the
  render and both its signals stale.
- **Compatibility and special values**: plain one-channel EXR, plain RGBA
  (refused as depth), single-part and multipart multilayer; +inf for
  nothing hit survives reading, resizing and `merge.depth` with no NaN;
  NaN and -inf are refused at recording (`signals._shape_problems`). Depths,
  like labels, are now resized to the nearest everywhere (a blend of 4 m and
  +inf is neither, or NaN).
- **The depth's meaning is per renderer, never assumed**: `renders.Z_MEASURED`
  holds what each engine's Z measures as measured here (Cycles: z); another
  engine is refused until measured. The meaning is written into
  `render.json` (`depth`, with how it was measured) and the signal's record
  (`depth.quantity`).

Limitations, recorded in the roadmap with how: perspective cameras and
square pixels only; edges and transparency (Cryptomatte, step 5); Blender's
version recorded, not checked at reading; no CLI or job yet; files outside
the production refused (a collect step); not on GL (step 6).

## Step 3 -- models as adapters (done 2026-10-15)

The user's direction: three contracts, `record_signal` for all, versions and
weights by hash, parameters, input media and environment recorded; the
model's declared confidence apart from measured quality; a test running the
same inference twice and changed weights invalidating; non-determinism
recorded, not promised; no inference in the Core, adapters replaceable, no
implicit downloads. Also taken: depth resized to the nearest stays for now;
an interpolation aware of discontinuities and invalid values is planned for
step 5 (roadmap).

- **`models.py`, the catalog**: each model's hub repository at a **pinned
  revision**, the files taken, weights by the hub's sha256, licence,
  kind, how it treats time. Only Apache-2.0: Depth Anything V2 **Small**
  (Base/Large/Giant named in `EXCLUDED` as CC-BY-NC-4.0), Video Depth
  Anything **Small** (its model code from the authors' repository at a
  pinned commit; Apache-2.0), SAM 2.1 hiera tiny. `fetch` is the only act
  that downloads (`toast models fetch`), checked by hash, nothing kept on a
  mismatch, into `~/.local/share/cine-toaster/models/<name>/<revision>/`
  with `model.json`; `require` refuses a model not fetched or whose files
  changed, naming the command.
- **`.venv-vision`** (`make install-vision`, `requirements-vision.txt`):
  torch 2.6 CPU, torchvision, transformers 5.2, OpenCV, einops. torch never
  enters Cine Toaster's environment. Video Depth Anything's code imports
  easydict (LGPL-3.0) for attribute access only: the worker gives it a
  stand-in, so it is not installed.
- **`vision_worker.py`** runs there, offline by construction
  (`HF_HUB_OFFLINE`): frames in (sRGB bytes), `result.npy` and `meta.json`
  out -- versions, device, threads, dtype, seed and deterministic
  algorithms, the model's input size, how the output was resized, the
  temporal windows, SAM 2's declared object scores.
- **`estimates.py`**: `estimate` reads a medium's stretch (FFmpeg rgb24),
  runs the worker, and records through `record_signal`: the model by name,
  repository, revision, licence, every file by hash, parameters, prompts,
  stretch, environment, determinism; every file of the model pinned as an
  `external` input, so changed weights make the signal stale. `repeat` runs
  twice and records identical or the largest difference. `compare`
  measures an estimate against a reference signal at the same media
  instants (IoU by object name; correlation with the reference's inverse
  z) and records it with `signals.record_measurement`.
- **The three contracts**: Depth Anything V2 Small gives `depth_relative`,
  `inverse_z`, scale `unknown: affine`, no camera, no unit -- refused by
  `merge.depth` until aligned (step 4). Video Depth Anything Small the
  same kind, its record keeping the windows (32, overlap 10, key frames),
  the alignment between them and the stretch estimated together. SAM 2 a
  `segmentation` of **instances**: label n is the n-th object prompted, the
  same object in every frame, its name a name; `labels_are` is now part of
  the signal contract (instances or classes), and the Blender object
  index says instances too.
- **CLI**: `toast models list|fetch`, `toast signal estimate|compare|status`
  (SAM 2's `--object NAME[@FRAME]:X,Y` and `--box`), and `toast render
  passes|status` (step 2's command, a limitation closed). Doctor: "Vision
  models", with the commands for what is missing.

Measured on the step-2 scene rendered at 320x180 (the dolly; a plate made
of the render over grey), against the render's own signals:

| Model | Against | Per frame |
|---|---|---|
| Depth Anything V2 Small | correlation with 1/z | 0.851, 0.972, 0.974 |
| Video Depth Anything Small (input 252) | correlation with 1/z | 0.784, 0.932, 0.952 |
| SAM 2.1 tiny, one point an object | IoU, ball / box | 0.994/0.992, 0.994/0.989, 0.994/0.999 |

Both depths order the ball, box and wall as the geometry does in every
frame. Two runs on the CPU with the same threads were bit-identical (Depth
Anything V2, SAM 2). Times on this CPU: Depth Anything V2 about 2 s a
frame; Video Depth Anything about 15 s for one window at input 252 (170 s at
518); SAM 2 about 6 s a frame. A box prompt drawn loosely by hand gave the
box an IoU of 0.56 -- the measured quality shows it, which is the point.

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
- Full suite after step 1: 934 tests pass; after step 2 and its review: 954; after step 3: 966.
- Step 3 (`tests/test_estimates.py`): without models, with a stand-in
  worker -- the catalog refuses CC-BY-NC models and unknown ones; nothing
  is fetched implicitly (the store stays absent); a fetch of the wrong
  bytes keeps nothing; a tampered file is refused by `require`; a relative
  depth is recorded estimated, `inverse_z`, with no camera or unit, its
  clock at the stretch's first frame, the model's revision, licence, files
  and stretch; changed or removed weights make it stale and refused; a
  second run is recorded identical, or with its difference; SAM 2 objects
  are instances with their prompts, declared scores kept apart from an IoU
  measured later against a person's matte; a medium outside the production
  is refused. With the models and Blender: the three models on the known
  scene, ordering and correlation, the video model's windows and code
  commit, objects followed through the dolly above 0.95 IoU, second runs on
  record.
- Step 2 (`tests/test_renders.py`, Blender 5.2.2): a recipe scene (wall at
  10 m, ball, box; the camera dollying 2 m over three frames) rendered at
  96x54; the record names Blender's version as installed, engine and
  samples; the object table; the wall's z is 10, 9, 8 to 1e-4 at every
  pixel; every pixel unprojected through its frame's recorded camera lands
  on its object's surface (sphere and box within 2 cm away from edges); the
  ball's projected centre carries its label; nothing hit is +inf and label
  0; in the graph, `merge.depth` of the render against a card at 7 m keeps
  what is nearer and lays the render over the card by its alpha at soft
  silhouettes; `r.alpha` is the picture's alpha; another camera is refused;
  a moved ball makes render and signals stale and refused until rendered
  again; a graph without a record refuses `generate.render`; a multipart
  EXR is read whole; without Blender, the command says what to install.
- After the user's review (`tests/test_renders.py`, 20 tests): `ExrFiles`
  (plain, RGBA refused, single-part multilayer by layer, two layers of one
  name refused, +inf through a resize, NaN and -inf refused), objects
  entering and leaving, render and signals stale on a camera, a texture, the
  script; an unmeasured engine refused.

- Nothing built; the audit's claims are from the code read above (the
  reference's `signal.read`, `signal.align_depth`, `merge.depth`; the
  schema's `merge.depth` camera check; `NOT_IN_REFERENCE`).
