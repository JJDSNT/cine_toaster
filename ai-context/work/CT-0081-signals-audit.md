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

## Step 4 -- alignment over a stretch, with its residuals (done 2026-10-15)

The user's requirements (two reviews): an explicit transformation; time
shared or regularized, not fitted free per frame; residuals beyond a
correlation (MAE, RMSE, percentiles, coverage); occlusions and missing
values excluded, never made 0; provenance kept, an aligned depth still an
estimate; `merge.depth` not taking it just because it has metres -- camera,
coordinates, Z convention, time and calibration checked; unknown not
background; coordinates beyond resolution (origin, orientation, crop, scale);
independent validation in space, alternate frames and a continuous stretch;
regularization by real time; inversions of order by object pair -- and the
decisive test, that a wrong occlusion is detected and signalled even when it
cannot be corrected. The user's caution kept: the measurements are on
synthetic scenes; they show the adapters and the alignment work there, not
that they generalize to real footage, hard occlusions or complex camera
moves.

- **`align.py`** (`align_depth`, `toast signal align`): 1/z = s e + t,
  least squares, trimmed (a spread floor so exact data is not trimmed at
  random); `regularized` by default -- the change of (s, t) penalized over
  the real interval between frames fitted -- or `shared`, or `per_frame`;
  the three always fitted and compared, beside a constant depth (what an
  alignment must beat). Excluded: reference +inf, non-finite or not
  positive; a band at the reference's depth jumps; an optional region.
  s <= 0 refused (it would turn near into far). Where s e + t <= 0 the
  pixel is **unknown** (`signals`' new `unknown` masks, kept apart from the
  data). Residuals in sample, on held-out 8-pixel blocks, on alternate
  interior frames (parameters interpolated in time) and on the last quarter
  held out (parameters held from the past), beyond a region where the
  reference has values; temporal agreement; the depth range calibrated.
  With `objects` (instances), every pair ordered **where the two meet**
  (each one's pixels within 3 of the other, medians compared) -- an
  extended surface's own median says nothing of what stands on it -- and
  occlusions inverted flagged; pairs apart reported apart.
- **The record**: a `depth` derived from the estimate, origin `estimated`,
  `align_depth` in its provenance (reference pinned, region and objects
  pinned, parameters, exclusions, every measure, the modes compared, the
  occlusions inverted), the camera stated by the caller and checked against
  the reference, the reference's window, `outside: refuse` (a calibration
  holds on its stretch only), `unknown` masks.
- **The compositor's side**: `signal.read` of an estimated depth requires
  `estimated: true`; a flagged one also `inversions: accept`; neither lifts
  stale, camera or stretch refusals. `merge.depth` checks, where records
  say, camera, quantity, unit, size, coordinates and the window of the
  camera's image (`signals`' new `window`), refusing rather than
  resampling; an unknown pixel where its picture shows is refused unless
  the merge says `unknown: behind` or `front`.

Measured on a rendered dolly (2.5 m in, 8 frames, 320x180) where a ball
crosses behind a pillar on a floor before a wall; AbsRel, the regularized
default:

| Estimate | Calibrated on | In sample | Alternate frames out | Last stretch out | Constant depth |
|---|---|---|---|---|---|
| Depth Anything V2 | everything | 0.124 | 0.110 | 0.276 | 0.365 |
| Video Depth Anything | everything | 0.084 | 0.077 | 0.188 | 0.365 |
| Depth Anything V2 | the floor | 0.020 | 0.057 | 0.051 | 0.180 |
| Video Depth Anything | the floor | 0.037 | 0.039 | 0.057 | 0.180 |

Calibrated on the floor, the objects standing on it are an extrapolation:
AbsRel 0.17-0.21 there. Temporal agreement (mean error of the
frame-to-frame change, metres): `shared` was the worst in every case
(0.12-0.39) -- Depth Anything V2 renormalizes each frame, its own fitted
scale moving 4x (0.006-0.027), and a shared fit carries that into metres;
`per_frame` the best in three cases (0.055-0.076); `regularized` between
(0.095-0.146), and the best for the video model on the floor alone (0.100
against 0.103 and 0.121). Held-out 8-pixel blocks barely differ from the
sample (neighbouring blocks are alike); alternate frames are alike too --
a video model's above all -- so their gain is favourable evidence on this
scene, not a guarantee; the last stretch held out is the hardest measure
(AbsRel 0.19-0.28 with the whole reference). The three kinds of measure
stay apart -- metric error, stability in time, order of occlusion: here a
mode better on one was worse on another.

Found while closing, and fixed: outliers were judged against the
regularized compromise (a frame the smooth fit could not follow lost its
good pixels, and the fit drifted); they are now judged against each frame's
own fit. The edge band measured a jump against the frame's median inverse
depth (a floor near the camera read as edges); it is now relative to the
pixels' own. The regularization penalizes the change of the map itself,
(Δs e + Δt)² over the stretch's estimates, not s and t apart.

The decisive case: Depth Anything V2 sets the pillar behind the floor along
its silhouette (frames 0, 1, 2, 7) and the pillar behind the ball where they
are apart (an inversion of the estimate itself: the alignment, monotone,
cannot make or mend one) -- reported apart, not flagged: they do not meet
there. Its average error passes (0.12); the record
flags `floor/pillar`; a composite with it is refused until `inversions:
accept`. The video model's calibration flags nothing, and its composite
runs.

## Step 5 -- depth compositing at edges: the audit (2026-10-15)

The user's rule for it: the compositor keeps three states apart -- a depth
known, a geometric "nothing there" (+inf), a depth unknown -- and uses the
quality signals of step 4. The Depth Anything V2 scene of step 4 stays as a
permanent fixture (`tests/fixtures/c8/da2-occlusion.npz`, read by the fast
suite).

Measured with a truth: the step-4 dolly rendered flat (emission shaders, no
light or shadow, so layers composite exactly but for their edges), the ball,
the pillar and the room each alone, and the whole scene as the truth -- all
at 4x with a 1-pixel filter, brought to 320x180 by averaging; each layer's
depth one sample a pixel, as a renderer gives it. Mean error (RGB) in a band
of 2 pixels round the ball's silhouette, its 99th percentile, and where the
ball meets the pillar:

| Merge | Band | p99 | Ball/pillar |
|---|---|---|---|
| ball over an opaque room-with-pillar, per pixel (today) | 0.0106 | 0.145 | 0.0182 |
| the same, the occlusion filtered 3x3 (PCF) | 0.0304 | 0.116 | 0.0407 |
| the same, each layer's depth carried into its coverage | 0.0013 | 0.023 | 0.0161 |
| the same, supersampled 2x / 4x | 0.0062 / 0.0032 | 0.067 / 0.020 | 0.0168 / 0.0035 |
| ball, pillar and room as three layers, per pixel | 0.0100 | 0.145 | 0.0119 |
| three layers, each depth carried into its coverage | **0.0001** | **0.0012** | **0.0005** |
| three layers, supersampled 4x | 0.0032 | 0.021 | 0.0033 |

What it says:

- The halo is not aliasing: a layer's picture covers part of an edge pixel
  (its alpha) while its one depth sample missed it (+inf there), so the
  layer is ordered behind whatever is there and its soft edge is lost.
  Carrying each layer's depth into the pixels its picture covers (from its
  nearest covered neighbour) removes it -- better than supersampling 4x.
- Filtering the comparison (PCF) blurs where nothing was wrong: worse.
- Inside an **opaque** layer, a silhouette has no coverage of its own: the
  pillar's edge in the room picture is a mix of pillar and wall under one
  depth, and nothing in a merge can split it. The pillar as its own layer
  (its own alpha) makes the merge exact. For a render, objects that occlude
  others are layers -- or Cryptomatte gives each its coverage; for footage,
  a matte (segmentation, a key) cuts the occluder out as a layer.

The plan, in that order:

1. `merge.depth` carries each layer's depth into its coverage (`edges:
   coverage`, the default; `hard` kept, for what it was).
2. Three states in the graph: known (finite), nothing there (+inf), unknown
   -- a merge's own depth out (`name.depth`) keeps them: the front layer's
   depth where it is known, unknown where the deciding layer's is.
3. Layers from a picture and a matte: the done-when film's shape -- a
   plate's person cut by a segmentation as its own layer, a Blender object,
   the plate behind -- measured against a truth: an estimated, aligned depth
   ordered per pixel against per object (an object's robust depth carried
   over its matte), where a model's depth is soft at edges.
4. Every decision recorded (what the merge did at edges), GL later (step 6).

## Step 5 -- depth compositing at edges (done 2026-10-15)

- **`merge.depth`** (`reference.merge_by_depth`): `edges: coverage` by
  default -- each layer's depth carried into the pixels its picture covers
  where its one sample missed (+inf there), from its nearest covered
  neighbour, `reach` 2 pixels; `hard` as before. Three states: unknown
  depths (NaN, from a record's `unknown` mask through `signal.read`) are
  never filled, never far; where one decides what shows the merge refuses
  unless `unknown: behind|front`. Its own `depth` out keeps the three states,
  so merges chain (its camera passed on in validation).
- **No other op takes an unknown depth**: the reference refuses a NaN signal
  anywhere but `merge.depth` and `signal.object_depth`.
- **`signal.object_depth`**: one depth for an object over all of its matte
  -- the median (or `near`, the 10th percentile) of its depth inside the
  matte's solid interior, unknown pixels left out, unknown when too few are
  known, +inf outside the matte.
- Recipes may ask flat emission shaders and a pixel filter (`renders`,
  `passes.py`): the truth scenes of these measurements.
- **Tests split** (the user's ask): `@heavy("why")` marks 37 tests needing
  Blender, models or a voice engine; `make test-fast` (950 tests, about 10
  minutes here), `make test-heavy`, `make test` (all, the final authority);
  `tests/run.py --times` finds the slow classes. The time is mostly not in
  the heavy tests (retimed sound, deliveries, generation lead); the doctor's
  tests fell from 106 s to 15 s by probing the vision and voice environments
  once a process, again only when their packages change. The Depth Anything
  V2 scene of step 4 is a fixture the fast suite reads.

Measured, in addition to the audit's table -- the done-when film's shape: a
plate (the stage rendered flat, standing for footage) with Video Depth
Anything's depth aligned to its floor alone, the pillar cut out by a soft
matte as "the person", a CG ball crossing behind it, the whole scene
rendered at once as the truth; error where the ball meets the pillar:

| Merge | Band | Ball/pillar |
|---|---|---|
| ball over the plate, per pixel, hard | 0.0142 | 0.0639 |
| the same, coverage | 0.0050 | 0.0630 |
| ball, person (matte) and plate, the person's depth per pixel | 0.0050 | 0.0630 |
| the same, the person's depth one for the object | **0.0008** | **0.0093** |
| the same, the geometric depth per pixel | 0.0013 | 0.0161 |

An estimated depth is soft at a silhouette: per pixel, the person dissolves
into what is behind it exactly where it meets the ball. One depth for the
cut-out object keeps it whole -- better here than the true geometry per
pixel, whose remaining error is the matte's colour at its edge (the plate's
wall mixed into the person's fringe). With Depth Anything V2 instead, the
contact is wrong whatever the edges (0.157): it sets the pillar behind --
and the alignment flags `floor/pillar`. No edge method mends an order; the
flag is what saves the composite.

## Step 6 -- the signal ops on GL (done 2026-10-15)

The user's scope: `signal.read`, `merge.depth`, `signal.object_depth`, their
chains, transfers measured; the same results, no second interpretation of
the data; a hybrid where a reduction is better on the CPU; GL never a race to
put everything on the GPU.

Audit first: GL drew none of C8's ops, so any graph with a depth went to the
reference; a graph is drawn whole by GL or whole by the reference
(`renderer_for`), the one that drew in the result's identity; textures are
float, sampled with a linear filter -- and a linear filter at a texel's
centre still weighs its neighbour by 0, and 0 x +inf is NaN.

- **A depth in GL is two channels**: R its value (a number, or +inf: nothing
  there), G its state (1: unknown) -- never NaN in a shader (GLSL does not
  promise its meaning). Two-channel textures are never filtered (`NEAREST`,
  set where textures are made); the new shaders read texel by texel.
- **One reading for both renderers**: `read_signal`, `read_signal_file` and
  `read_render` (the last two drawn out of the reference's evaluation for
  it) read records and files on the CPU; GL uploads what they give.
- **`merge.depth`**: a program per number of layers (up to 8: two texture
  units a layer, 16 promised; more goes to the reference), the reference's
  `merge_by_depth` pixel by pixel -- coverage passes, ordering stable on
  ties, unknown placed by policy, the merged depth out (only when a node
  reads it), and the refusal of an unknown shown, word for word (a flag pass
  read back only when an input may hold unknown).
- **`signal.object_depth`, hybrid**: the median on the CPU (one sort; the
  depth from the CPU copy it was uploaded from, the matte read back once),
  the object's depth drawn over its matte here.
- **`matte.label`**: up to 32 labels in a shader.
- **The unknown refusal** for any other op reading a depth: the same rule
  and message (its input made first, then checked).
- **Still the reference's**: a surface's depth (GL draws the surface, not
  its depth); the graph `signal.align_depth`; merges of more than 8 layers
  -- `renderer_for` sends such graphs there, and the identity says so.

Measured (`scripts/research/gl_signal_bench.py`, 1920x1080, three layers
with coverage, an object's depth, unknown pixels, a label matte), ms a frame:

| | llvmpipe (CPU) | Intel UHD 620 (d3d12) |
|---|---|---|
| the reference | 835 | 871 |
| GL | 394 (2.1x) | 345 (2.5x) |
| reading the records (CPU) | 134 | 139 |
| uploads (7) | 46 | 67 |
| draws (13), submitted | 91 | 3 |
| downloads (3, waiting on the GPU) | 48 | 61 |
| largest difference | 3.9e-5 | 6.0e-8 |

On the GPU the drawing is nearly free; what costs is reading the records
(a 1080p signal frame is a ZIP-compressed float EXR, 36 ms to decode
against 2.6 ms as .npy) and the transfers -- the pictures up, the matte for
an object's depth and the output down.

## Step 7 -- signals in a shot's layers (done 2026-10-15)

The user's three results: layers ordered by depth, compiled into
`merge.depth`; a model's segmentation as a matte; Blender and models in one
composition under the colour, alpha and depth contract -- a declarative
extension of the records compiled into the existing graph, no second
compositor; a depth refused stays refused whether a layer, a person or an
agent asks.

Audit first: the layers (C4) compile bottom to top with `merge.over`; their
`depth` key only passed an unread parameter to `warp.transform` (room kept
for 2.5D). And a gap no layer could cross: a render's depth named its camera
`<render>/<camera>`, so a CG object could never be merged by depth with a
plate's depth -- `merge.depth` refuses two cameras. In production a CG
camera is matched to the plate's (a solve, by hand); that is a statement.

- **`render_passes(camera_id=...)`** (`toast render passes --camera-id`):
  the production's camera this render's camera is, recorded with who stated
  it; its depth and objects carry it.
- **Layer keys** (`compositing/layers.py`): `render: id` as a source (a
  render's record); `cut: {signal, labels}` -- a segmentation of the
  source's pixels, read where the source shows, as a matte with the key and
  garbage; `depth: {signal | render: true, camera, object, statistic,
  estimated, inversions, unknown}`.
- **Compiled**: layers with a depth wait in a group and are merged by it --
  one `merge.depth` (coverage, three states) -- at the place of the lowest of
  them; a layer without one flushes the group and goes over it, keeping its
  place (a title over everything). A depth read from its source's records
  `of` the source (its instant, through retimes and offsets); `object: true`
  is `signal.object_depth` over the layer's own alpha (after its cut);
  `estimated`, `inversions`, `unknown` go to the nodes that check them.
- **Said, not guessed**: a depth without a camera, with a move, a pin, an
  echo, a shadow or a border (its depth would have to follow), blending
  other than over, a render's depth on a source layer, a cut without labels,
  two policies for the unknown in one group -- each a problem at compile; two
  cameras a problem of validation.

Measured with sources meeting in declared layers (heavy test): the stage
rendered flat as the plate, Video Depth Anything's depth aligned to a floor
proxy, the pillar cut out by **SAM 2's** segmentation, a CG ball from its
own render with its camera stated to be the plate's; error where the ball
meets the pillar against the whole scene rendered at once: **0.0151** with
one depth for the cut-out person, 0.0524 per pixel; GL equal to the
reference. A segmentation's cut is hard (one label a pixel), so the
person's edge is not soft -- the soft-matte limitation of step 3.

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
- Full suite after step 1: 934 tests pass; after step 2 and its review: 954; after step 3: 966; after step 4: 984; after step 5: 997; after step 6: 1006; after step 7: 1016.
- Step 7 (`tests/test_layer_depth.py`, 10): the layers compile into one
  graph with one `merge.depth`, an object depth, a label matte, every read
  `of` its source; she covers the square inside her cut and the square
  covers the wall; one depth keeps her whole where per pixel she falls
  behind the square; GL draws the layers alike; a title without depth keeps
  its place; through the layers the records' refusals hold -- an estimated
  depth not said, an inverted occlusion not accepted, an unknown with no
  policy, a stale record; what cannot be written is said; in a scene's file
  (as a person or an agent writes it) the layers become the shot's composite
  and are refused alike. Heavy: Blender and the models in one composition
  (above).
- Step 6 (`tests/test_gl_signals.py`, 9, on llvmpipe and again on the Intel
  GPU with `GALLIUM_DRIVER=d3d12`): GL equal to the reference at partial
  alpha with coverage and without; the three states through a chain of
  merges, both policies; the same refusals word for word (an unknown shown,
  an unknown into a matte); a merged depth (known, +inf) into a matte; five
  layers with ties, near small and far small; an object's depth, known and
  unknown; labels; a render, its depth and its objects at its own size and
  resized (heavy); +inf and NaN surviving the way to the GPU and back; what
  GL cannot draw whole (the graph alignment, a surface's depth, nine
  layers) sent to the reference.
- Step 5 (`tests/test_depth_edges.py`, 13): a disc's soft edge kept exactly
  where its one depth sample missed (the halo measured, then gone); coverage
  never putting a layer before what is nearer; the merged depth's three
  states; an unknown depth never made known by coverage, refused unless a
  policy is said; one depth for a cut-out object exact where a soft
  estimated depth was not; an object's unknown depth unknown; merges
  chained; an unknown depth refused by any other op; `hard` still there. On
  renders (heavy): the halo gone over an opaque background (0.0170 ->
  0.0083) and the merge near exact with every occluder its own layer
  (0.0091 -> 0.0004); on an estimated plate, one depth for the person at least 3x
  better at the contact than per pixel (the test's bar; measured 7x).
- Step 4 (`tests/test_align.py`, 15): on synthetic fields of known scale
  and shift -- found exactly in every mode, an alignment beating a
  constant depth on frames it did not see; the record still estimated,
  its history and measures, stale when the reference changes; the sky
  unknown, never far or 0; a drifting scale carried into metres by a
  shared fit, regularized between; alternate frames catching a fit that
  holds only where it looked, the last stretch catching one that does not
  hold forward; regularization by real time; refusals (camera, kind,
  stretch, quantity, pixel grid, s <= 0); an inverted occlusion flagged and
  refused unless accepted, a correct estimate not flagged; the composite
  refusing an aligned depth unless `estimated: true`, an unknown pixel
  unless told, past its stretch, of another camera, quantity, size or
  window, or stale. On the rendered dolly with the models: alignment beats
  a constant by 2x on held-out frames; the default flickers less than a
  shared fit; no frame reordered; the floor does not vouch for the
  objects; Depth Anything V2's wrong occlusion caught and refused, the
  video model's composite run.
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
