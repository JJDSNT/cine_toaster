---
id: SPEC-0012
title: The compositing graph — primitives, typed values, colour, identity and renderers
type: specification
status: draft
implementation: planned
owner: project
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - compositing
  - project-core
  - colour
  - renderers
---

# Goal

Specify ADR 0022 so it can be built: the primitives with their ports and
parameters, the values that flow between them, the colour contract, how a
composite is written in the breakdown, how a node is identified, and what a
renderer promises. Step C1 of `development/compositing-roadmap.md`.

This specification is done when the existing transitions, effects and titles
can be written as graphs of it (Appendix B shows they can, and says where
they cannot yet), and C2 can start building the reference renderer against
it without a decision left open.

# 1. Values

Every edge carries one typed value. A value is a function of time over its
node's extent, sampled at the composite's frame rate.

| Type | What it holds | Representation in the working space |
|---|---|---|
| `picture` | an image with alpha | RGBA, float, scene-linear, **premultiplied** |
| `matte` | how much is seen | one channel, float, 0 to 1 (may exceed for soft operations, clamped at merge) |
| `signal` | a named value per pixel | one or more channels, float; its `kind` says what (below) |
| `sound` | audio | samples at the composite's rate; carried, not mixed here (the mix stays the assembly's) |
| `track` | where something is per frame | a list of frames, each with points, a plane (four corners) or a camera (matrix, focal length) |
| `curve` | a number per frame | keyframes, or a driven value (§6) |
| `meta` | facts that ride along | provenance, licence, credit, source timecode |

Signal kinds: `luminance`, `luma`, `alpha`, `red`, `green`, `blue`, `hue`,
`saturation`, `depth` (distance from the camera, scene units; a direction
flag says near = small), `vectors` (two channels, pixels per frame),
`normals` (three), `segmentation` (an integer label per pixel, with a table of
labels). A signal declares its range; a `matte` is made from a signal by an
operation (§3), never by reinterpreting it.

A connection is valid when the port's type equals the value's, or when the
specification lists an implicit conversion. There are two:

- `picture` → `matte`: the picture's alpha;
- `matte` → `picture`: grey, with alpha 1.

Any other mismatch is an error before rendering (`composite_type_mismatch`).

# 2. The colour contract

- **Working space.** Scene-linear. The production may name it
  (`compositing: {working_space: ACEScg}` in `project.yaml`); the default is
  `Linear Rec.709 (sRGB)`, the space `color.py` already uses. Names are OCIO
  colour spaces.
- **Into the working space.** Every source declares or is given a colour
  space: a take's from its file's tags or the production's `picture_space`
  (default `sRGB Encoded Rec.709 (sRGB)`); a Blender EXR is scene-linear; a
  generated picture is made in the working space directly. The conversion is
  an OCIO transform, done once at the source node.
- **Alpha.** Inside the graph, pictures are premultiplied. A source declares
  `alpha: straight | premultiplied` (default: straight for PNG, ProRes 4444
  and WebM; premultiplied for EXR) and is converted at the source node.
- **Precision.** Float inside the graph (a renderer may use half floats; it
  says so). 8-bit or 10-bit only at the version's encode. Values above 1 are
  kept: HDR is not clipped until the output transform.
- **Out of the working space.** At the version's encode, through the output
  transform the production's frame and delivery give (today `sRGB - Display`
  with the `Un-tone-mapped` view, as `color.py`).
- **Luma and luminance.** `signal.luminance` is computed from linear values
  with explicit weights; the default weights are Rec.709's (0.2126, 0.7152,
  0.0722), and an operation may name others or a transform (for HDR or another
  working space). `signal.luma` is computed from values first encoded with a
  named transfer function (default sRGB); it is what video calls Y'. They are
  different quantities and an operation names which it reads. A luma wipe made
  before this specification used FFmpeg's Y' of display-encoded 4:2:0; under
  it, a recipe chooses, and the catalog's `luma` keeps Y' so its look does not
  change unless its sheet says so.

# 3. The primitives

Each operation is `<primitive>.<name>`. Ports are named; parameters may be
constants or curves (§6). The tables are the contract; C2 implements them in
FFmpeg first.

## signal

| Op | In | Out | Parameters |
|---|---|---|---|
| `signal.luminance` | picture | signal | `weights` (3 numbers) or `transform` |
| `signal.luma` | picture | signal | `transfer` (default sRGB), `weights` |
| `signal.channel` | picture | signal | `channel`: red, green, blue, alpha, hue, saturation |
| `signal.read` | -- | signal | `file`, `kind` (depth, vectors, normals, segmentation), `range` |
| `signal.estimate` | picture | signal | `kind`, `model`, `seed`; not deterministic unless the model says so |

## matte

| Op | In | Out | Parameters |
|---|---|---|---|
| `matte.from_signal` | signal | matte | `low`, `high` (the range mapped to 0..1), `invert`, `gamma` |
| `matte.key` | picture | matte | `by`: luminance, luma, colour, difference; `colour`, `tolerance`, `softness`; a second picture for `difference` |
| `matte.label` | signal (segmentation) | matte | `labels` |
| `matte.shape` | -- | matte | `shape` (rectangle, ellipse, polygon, spline), points, `feather` |
| `matte.threshold` | matte, `progress` (curve) | matte | `softness` -- the wipe rule: a pixel is revealed when progress passes its value |
| `matte.combine` | matte, matte | matte | `how`: union, intersect, subtract, multiply |

Grow, shrink, feather and invert are `filter` and `colour` operations on a
matte (§3 filter, colour); they are not repeated here.

## merge

| Op | In | Out | Parameters |
|---|---|---|---|
| `merge.over` | `front` picture, `back` picture, optional `matte` | picture | `mix` (0..1) |
| `merge.porter_duff` | two pictures | picture | `op`: over, under, in, out, atop, xor |
| `merge.blend` | two pictures | picture | `mode`: screen, add, multiply, overlay, difference, lighten, darken; `mix` |
| `merge.mix` | two pictures, a `matte` or a `curve` | picture | -- (a dissolve is `merge.mix` with a curve) |
| `merge.channels` | up to four signals or mattes | picture | which input fills red, green, blue, alpha (found missing by Appendix B: chromatic aberration) |
| `merge.depth` | pictures, each with a `depth` signal | picture | `near_is_small`; each pixel takes the nearest opaque picture (occlusion; §8; found missing by Appendix B) |

A matte on `merge.over` multiplies the front's alpha before the merge.

## warp

| Op | In | Out | Parameters |
|---|---|---|---|
| `warp.transform` | picture (or matte) | same | `translate`, `scale`, `rotate` (three axes), `pivot`, `perspective` (field of view), `depth` (for 2.5D, §8) |
| `warp.corner_pin` | picture, optional track | same | four corners, or a plane track |
| `warp.displace` | picture, signal (vectors or one channel) | same | `strength`, `direction` |
| `warp.procedural` | picture | same | `kind`: ripple, swirl, bend, lens; its parameters |

Pixels outside the source after a warp are transparent.

## colour

| Op | In | Out | Parameters |
|---|---|---|---|
| `colour.lut` | picture | picture | `file` (a .cube) or an OCIO `look` |
| `colour.grade` | picture | picture | `lift`, `gamma`, `gain`, `saturation`, `hue` |
| `colour.curve` | picture or matte | same | points per channel |
| `colour.posterise` / `solarise` / `cycle` | picture | picture | levels / threshold / speed |
| `colour.invert` | picture or matte | same | -- |

## filter

| Op | In | Out | Parameters |
|---|---|---|---|
| `filter.blur` | picture or matte | same | `radius`, `kind` (gaussian, box, directional, defocus) |
| `filter.sharpen` | picture | picture | `amount` |
| `filter.glow` | picture | picture | `threshold`, `radius`, `intensity` |
| `filter.edges` | picture | picture or matte | `kind` |
| `filter.morphology` | matte | matte | `operation` (erode, dilate), `radius` |
| `filter.noise` | picture | picture | `amount`, `size`, `seed` (grain) |

## time

| Op | In | Out | Parameters |
|---|---|---|---|
| `time.remap` | any value over time | same | a curve from output time to input time (retime, ramp, reverse, freeze) |
| `time.offset` | any | same | `frames` |
| `time.blend` | picture | picture | frame blending for a remap |
| `time.echo` | picture | picture | `count`, `spacing`, `decay` (trails) |

## generate

| Op | In | Out | Parameters |
|---|---|---|---|
| `generate.source` | -- | picture (+ sound, meta) | a take, a file or a stretch; its colour space and alpha (§2) |
| `generate.solid` / `gradient` / `noise` | -- | picture | colour(s), kind, seed |
| `generate.text` | -- | picture | text, font, size, colour, `reveal` (curve: letters shown, for typewriter-like titles) |
| `generate.render` | -- | picture (+ signals) | a renderer's own scene (Blender, a VFX recipe), its parameters, `seed`; it may also give depth or other passes |

## track and animate

| Op | In | Out | Parameters |
|---|---|---|---|
| `track.measure` | picture | track | `kind` (point, plane, camera), a starting region; deterministic per tracker version |
| `track.read` | -- | track | a file in the track format (§1) |
| `curve.keys` | -- | curve | keyframes `[{t, value, ease}]`; `ease`: linear, in, out, in-out, hold, bezier handles |
| `curve.beats` | -- | curve | the scene's music beats (CT-0067): a value per beat with an envelope (`attack`, `decay`) |
| `curve.from_track` | track | curve | a field of the track (x, y, rotation, scale) |
| `curve.progress` | -- | curve | 0 at a join's start to 1 at its end; only in recipes for joins |

## Opaque nodes

Some operations are programs Cine Toaster does not decompose: a
gl-transitions shader, an OFX plugin through Natron, a Blender simulation.
They are nodes of op `opaque.<renderer>` with typed ports declared by their
item (for a shader: `from`, `to`, `progress`, its textures), a parameter set,
and exactly one renderer. They are allowed, and say what they are: a recipe
built only of opaque nodes is not portable, and the catalog shows it.

# 4. A composite in the breakdown

A shot's picture is the take, unless the shot gives a `composite`:

```yaml
- n: 3
  composite:
    nodes:
      take:   {op: generate.source, take: CUT}
      sky:    {op: generate.source, file: plates/sunset.mov, colorspace: sRGB Encoded Rec.709 (sRGB)}
      window: {op: matte.shape, shape: polygon, points: [[0.31,0.2],[0.62,0.2],[0.62,0.71],[0.31,0.71]], feather: 0.01}
      inside: {op: merge.over, front: sky, back: take, matte: window}
    output: inside
    reason: The window looks onto the coast, not the car park it was shot against.
```

A node is `{op, <ports>: <node or node.port>, <parameters>}`. `output` names
the node whose picture is the shot's. A node may be given a `renderer` to
pin it; otherwise the planner (or, before C9, the single renderer running the
graph) chooses.

A join's recipe is a catalog item whose graph has the ports `from` and `to`
(pictures) and the curve `progress`; the join fills them:

```toml
id = "luma-wipe"
family = "wipe/luma"
[graph]
nodes.order   = {op = "signal.luma", picture = "matte_source"}
nodes.reveal  = {op = "matte.threshold", matte = "order", progress = "progress", softness = 0.05}
nodes.out     = {op = "merge.over", front = "to", back = "from", matte = "reveal"}
output = "out"
[inputs]
matte_source = "radial.png"
```

Parameters a recipe exposes are named in `[expose]`; a join may set those and
no others (this is CT-0050's per-cut override, done).

# 5. Identity and what is kept

- A source node's identity is the SHA-256 of its file (or of the take's), its
  stretch, and its declared colour space and alpha.
- Any other node's identity is the SHA-256 of a canonical JSON of: its op, its
  parameters (curves included), its inputs' identities in port order, the
  working space, and the renderer and version that computes it.
- A result is cached under its identity, outside the production
  (`~/.cache/cine-toaster/composite/`). Deleting the cache loses time only.
- A node whose op is not deterministic (`signal.estimate`, `generate.render`
  with a seed a renderer cannot honour exactly, `opaque.*` that say so) must
  have its result **recorded**: the first run writes it into the production as
  an asset with provenance (op, parameters, model, seed, inputs' identities),
  and later runs read that asset. Re-running is an explicit act, which makes a
  new asset.
- A result a person approved (a segmentation, a generated matte) is promoted
  the same way, whether or not its op is deterministic.

# 6. Curves and time

A parameter is a constant, or a curve: `{keys: [...]}`, `{beats: ..., attack,
decay}`, `{track: <node>, field}`, or `{progress: true}` in a join's recipe.
Times are seconds from the shot's start (or the join's, in a recipe). Curves
are evaluated per output frame. `time.*` nodes change the time at which their
input is evaluated; nothing else does.

# 7. Renderers

A renderer publishes a manifest (`toast doctor` shows it):

```text
id, version
implements: [op, ...] with, per op, limits (precision, max size, needs GPU)
precision: float | half | 8-bit (the working precision it really uses)
handover: how it reads and writes intermediate results
deterministic: [op, ...]
```

- **One renderer, whole graph** (C2 onward): every node must be in its
  `implements`; otherwise the graph is refused with the missing ops named.
- **Split across renderers** (C9): a planner assigns nodes; a value crossing
  renderers is written in the working space as OpenEXR (half float, linear,
  premultiplied) for pictures and signals, WAV for sound, JSON for tracks and
  curves; each part runs as a job with its place and cost.
- **Conformance** (C2 onward): for each op a renderer claims, a reference
  scene is rendered by it and by the reference (FFmpeg) and compared within
  a tolerance stated per op, at 160x90 and 1920x1080, 24 and 29.97 fps, 8-bit
  and float input, straight and premultiplied alpha.

# 8. Room for 2.5D

`warp.transform` carries `depth` and a camera's `perspective`; a picture may
carry a `depth` signal. A later `merge.depth` (ordering pictures by depth, with
occlusion) and a composite-level `camera` (with its own curves) make layers
sit in a space with parallax without a Blender scene. Not specified further
here; nothing above prevents it.

# 9. Checks

| Code | Severity | When |
|---|---|---|
| `composite_type_mismatch` | error | an edge's value is not the port's type and no conversion applies |
| `composite_cycle` | error | the graph is not acyclic |
| `composite_unknown_op` | error | an op no primitive or opaque item declares |
| `composite_input_missing` | error | a port with no value, a file not there |
| `composite_unrenderable` | error (warning before C9) | no renderer implements a node |
| `composite_unrecorded` | warning | a non-deterministic node whose result is not recorded yet |
| `composite_colourspace_unknown` | error | a source's colour space OCIO does not know |

# 10. Acceptance (for C1)

- Every op above has its ports, types and parameters stated (done here).
- The examples in Appendix B are valid under §1-§9.
- Every existing transition, VFX item and title is placed in Appendix B as
  expressible, expressible with an opaque node, or not yet expressible with
  what is missing named.
- No open decision is left to C2 other than implementation.

# Appendix A: terms

- **Premultiplied**: colour already multiplied by alpha; merges are then a
  sum. **Straight**: colour independent of alpha.
- **Scene-linear**: values proportional to light; mixing two pictures 50/50
  gives the physically halfway light.
- **Luma (Y')**: weighted sum of encoded (gamma) values. **Luminance (Y)**:
  weighted sum of linear values.

# Appendix B: what exists, written as graphs

The representative graphs, each as `node: op(inputs; parameters)`.

**Cross-dissolve** (`cross-dissolve`): `out: merge.mix(from, to; curve=progress)`.

**Luma wipe** (`luma`, with its texture): `order: signal.luma(texture)`,
`reveal: matte.threshold(order, progress; softness 0)`,
`out: merge.over(to over from; matte reveal)`.

**Custom wipe with a moving matte** (`matte-wipe`, SPEC-0011):
`m: generate.source(the join's matte)`, `a: signal.luma(m)`,
`reveal: matte.from_signal(a)` with the completion of SPEC-0011 as
`matte.combine(reveal, ramp; union)` where `ramp: matte.threshold(generate.solid(white), progress)` restricted to the last tenth;
`out: merge.over(to over from; matte)`.

**Geometric wipe** (`diamond-wipe`, `clock-wipe`): `shape: matte.shape` with
its size or angle a curve of progress; `out: merge.over(to over from; matte shape)`.

**Warp** (`displacement`): `wa: warp.displace(from, noise; strength = curve of progress)`,
`wb: warp.displace(to, noise; strength = curve of 1 - progress)`,
`out: merge.mix(wa, wb; progress)`.

**Warp wipe** (new, the user's): `wa: warp.displace(from, map; strength rising)`,
`reveal: matte.threshold(signal.luma(texture), progress)`,
`out: merge.over(to over wa; matte reveal)`.

**DVE moves** (`cube`, `doorway`, `switcher-flip`): expressible as
`warp.transform` of each picture with rotation and perspective curves and a
`merge.porter_duff` ordered by which face is in front; until 2.5D's
`merge.depth` exists, ordering is by a curve that switches at the half. The
gl-transitions shaders stay **opaque** nodes in the meantime.

**The rest of gl-transitions** (117 shaders): opaque `opaque.gl` nodes with
ports `from`, `to`, `progress`; portable only where a sheet re-expresses one.

**VFX, FFmpeg forms**:
- `film-grain`: `filter.noise(picture)`.
- `vignette`: `merge.blend(picture, generate.gradient(radial); multiply)`.
- `chromatic-aberration`: three `signal.channel` + three `warp.transform`
  (small scales) recombined by `merge.channels` (an op Appendix B found missing; now in §3).
- `glitch`, `camera-shake`: `warp.transform` with noise curves; `glitch` also
  `colour.*` per band -- band selection needs `matte.shape` with curves:
  expressible.
- `flash`, `fade-to-black`, `light-leak`: `merge.blend`/`merge.mix` with a
  `generate.*` and a curve.
- `focus-pull-in`: `filter.blur(kind defocus; radius curve)`.
- `crop`, `mirror`: `warp.transform` (mirror is a scale of -1).
- `old-film`: `filter.noise` + `colour.grade` + `warp.transform` (jitter
  curve) + scratches from `generate.noise`: expressible.
- `hologram`: `colour.*` + `generate` scanlines + `merge.blend`: expressible.
- `fog` (ffmpeg): `generate.noise` + `merge.blend(screen)`; its present form
  is a regular weave and should be replaced when it is re-expressed (CT-0064).
- `aces-film-look`: `colour.lut(look)`.
- Element effects (`fire-over`, `smoke-over`, `explosion-over`,
  `muzzle-flash`, `sparks-over`): `generate.source(element)` →
  `merge.blend(screen)` for black-backed elements, `merge.over` for alpha ones,
  `matte.key(colour)` for green ones.

**VFX, Blender forms** (`disintegrate`, `melt`, `shatter`, `liquid-splash`,
`lightning`, `rain`, `snow`, `sparks-burst`): `generate.render` (a Blender
scene, a seed, optionally depth and alpha passes) then `merge.over`. Not
deterministic across Blender versions: recorded (§5).

**VFX, OFX** (`ofx-bloom`, `ofx-glow`, `ofx-lens-distortion`): opaque
`opaque.natron` nodes; `ofx-glow` and `ofx-bloom` are also `filter.glow` and
can be re-expressed.

**Titles** (`card`, `film-title`, `caption`, `lower-third`, `slide-up`,
`grow`, `flicker`, `neon-sign`, `typewriter`, `word-by-word`,
`credits-roll`): `generate.text` with curves on its alpha, position, size or
`reveal`, `generate.solid` for bars, `merge.over` on the picture.
`letters-rise`, `letters-turn-in` (Blender, letters as objects):
`generate.render`. Expressible; the per-letter animation of the FFmpeg forms
is a `reveal` curve and per-word timing a `reveal` with holds.

**The music piece's joins** (CT-0064): each transition above, with its
length and placement from beats (CT-0067) -- a join's `progress` spans its
beats; a beat-pulsing parameter is `curve.beats`.

**A window replaced** (the user's example): the composite in §4.
**A luma key**: `k: matte.key(picture; by luminance, low, high)`,
`out: merge.over(picture over background; matte k)`.
**A Blender object behind a person** (C8): `person: generate.source(take)`,
`d: signal.estimate(person; kind depth)`, `obj: generate.render(blender; with depth pass)`,
then `merge.depth(person with d, obj with its depth)`.

What the appendix found missing, and §3 now has:

- `merge.channels` (a picture from separate channels) -- for chromatic
  aberration and channel effects;
- `merge.depth` -- occlusion by depth, also §8's first piece.

With them, every existing item is expressible, or expressible as an opaque
node (the gl-transitions shaders not yet re-expressed, the OFX plugins, the
Blender simulations as `generate.render`).
