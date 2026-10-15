---
id: CT-0080
title: C7 -- time and track, the audit before building
type: work
status: doing
owner: unassigned
created_at: 2026-10-15
updated_at: 2026-10-15
tags:
  - compositing
  - time
  - tracking
  - audit
---

# What

Step C7 of `development/compositing-roadmap.md` -- retime, speed ramp,
freeze, reverse, frame blending, offsets between layers, trails and echoes,
point and planar tracking driving a warp or a matte. Done when a speed ramp
lands on a beat, trails follow a moving layer, and a replaced window follows
a moving camera.

The user asked for the audit first (ADR 0022: supported is not exposed), and
nothing built before the diagnosis: for each capability, whether the graph
supports it, whether a filmmaker can use it, whether it needs integration
only or new work; the real semantics of the time nodes, not their names;
how **source time** and **timeline time** are told apart, above all when
tracking and retiming are combined; the contracts against ADR 0023; the
tracking adapter, its data and what can be reused. C7 as a coherent time
dimension of the whole graph, not a set of effects.

# The engine as it is (read and probed, 2026-10-15)

| Node | SPEC-0012 says | It does (reference) | GL |
|---|---|---|---|
| `time.remap` | a curve from output time to input time: retime, ramp, reverse, freeze | reads its input at frame `round(map * fps - 0.5)`, clipped to the **output's** frames | refuses (the graph falls back to the reference) |
| `time.offset` | `frames` | input at `frame - frames`, clipped | refuses |
| `time.blend` | "frame blending for a remap" | a box average of `frames` neighbouring **output** frames, centred | refuses |
| `time.echo` | `count`, `spacing`, `decay` (trails) | earlier frames laid under the present, each by `decay^n`, by their alpha | refuses |
| `track.measure` | point, plane, camera | OpenCV: good features in a region, pyramidal Lucas-Kanade; a point is their mean, a plane a RANSAC homography of the region's corners; camera refused | -- (data) |
| `track.read` | a file in the track format | reads a JSON `{kind, frames: [...]}` | -- |
| `curve.from_track` | x, y, rotation, scale | from the frame `int(t * fps)`; rotation and scale from the first two points | -- |
| `warp.corner_pin` | four corners, or a plane track | a plane track's corners per frame; a point track moves the given corners | yes |

Probed with a ten-frame clip whose frames carry their own number:

- 2x speed (`map = 2t`) gives 1, 3, 4, 6, 8, **9, 9, 9, 9, 9**: the source is
  read only as long as the output, so a speed-up freezes half way; and the
  cadence stutters (1, 3, 4...) -- the frame is picked by Python's `round`,
  which rounds halves to even, at frame centres.
- Half speed gives 0, 0, 1, 1, 2, 2...: frames repeated, never blended.
- Half speed then `time.blend` (2) gives 0, 0.5, 1, 1.5...: it happens to
  look like interpolation at exactly half speed because it averages
  neighbouring **output** frames; at full speed it blurs. It is a temporal
  average (a shutter), not frame blending between source frames.
- Reverse (`map` from 1 to 0) is right.
- `time.echo` and `time.offset` behave as named (`tests/
  test_compositing_reference_more.py`).

# Source time and timeline time

How the engine tells them apart today:

- A graph is evaluated in the **shot's frames** (0 at the cut's first frame).
  A take enters as a clip read from the cut point (`segment.start`, now on
  the take's frame grid), so the shot's frame `i` is the take's instant
  `start + i / fps` -- **implicitly**: nothing in the graph or its data
  carries that origin.
- `time.remap` maps the shot's output time to its input's time, both in the
  shot's local seconds; its input subgraph is evaluated at the remapped
  frame -- so curves and tracks **upstream** of a remap live in source time,
  as SPEC-0012 §6 says.
- A track is a list indexed by the frames of the graph it was measured in,
  with **no rate and no origin**. Consequences:
  - measured upstream of a remap, it follows the source: a corner pin
    upstream of the remap, then the whole retimed -- **correct**;
  - a corner pin **downstream** of a remap, fed by a track measured on the
    plate before the remap, reads track frame `i` at output frame `i` --
    **wrong** as soon as the speed is not 1;
  - a track read from a file made on the whole take (Blender, a person, a
    previous run) is read from index 0 at the cut point -- **misaligned by the
    trim**, silently;
  - measured at the render's size, so a preview and the final render track
    different pictures; measured anew on every render, never kept for a
    person to review.
- **Sound does not follow a retime**: the assembly lays the take's sound from
  the cut point at speed 1, whatever the picture does; a retimed shot's
  speech drifts from its lips. And a shot's span in the take and its length
  in the cut are one number (`end - start`), which a retime makes two.

What it needs (the user's model: timeline time -> remap -> source time ->
the source's frame -> its track -> composed in the output frame):

1. **Every time record says its clock**: a track, a retime curve, keys made
   by a tool carry their rate and their origin as ticks of the source (ADR
   0023: `{"rate": "30000/1001", "origin": {"ticks": ...}, ...}`); the graph
   converts once, at reading, into its own frames.
2. **A track is looked up by source time**, not by list index: a node that
   reads a track under a remap reads it at the remapped instant. The simple
   rule that makes every placement right: a track is data of its source, so
   its lookup goes through the same time the source's picture does.
3. **The shot has two lengths** when retimed: its source range (take ticks,
   half-open) and its duration in the cut. The assembly reads the source
   range the remap needs, and decides the sound by a stated policy (below).

# The capabilities, by ADR 0022

| Capability | Graph supports | Exposed to the filmmaker | Needs |
|---|---|---|---|
| Reverse | yes (`time.remap`) | no | integration: a record, compiled to a remap |
| Freeze | yes (remap held) | no | integration |
| Retime (constant speed) | partly: frames picked with a stutter; no source beyond the shot's length | no | **new**: floor frame picking; source extent from the remap; then a record |
| Speed ramp | as retime | no | **new**: as retime, plus speed keys compiled (integrated) to the source-time curve; landing on a beat |
| Frame blending | **no** (`time.blend` is a shutter average of output frames) | no | **new**: blend of the two source frames around the remapped instant (`interpolation: nearest | blend`); optical flow later |
| Offset between layers | yes (`time.offset`, and a layer's `start`) | partly: `start` in seconds | integration: `offset` on a layer, in frames or time |
| Trails and echoes | yes (`time.echo` with alpha) | no | integration: `echo`/`trails` on a layer, before its merge, so the trail follows it |
| Motion blur from a retime | yes, as a shutter (`time.blend`) | no | rename the semantics (a shutter), expose it with the retime |
| Point tracking | yes (OpenCV LK) | no | integration + **new**: a track record, re-seeding, a confidence |
| Planar tracking | yes (homography) | no | as point; corner pin exposure |
| Camera solve | refused | no | out of C7 (C8, Blender) -- planar is enough for "a window follows a camera" |
| Tracks in source time | **no** | -- | **new**: rate and origin; lookup by source time |
| Sound under a retime | **no** | -- | **new**: a policy |
| Time ops on GL | **no** (the whole graph falls to the reference) | -- | **new**: GL reads its inputs at other frames |

# The tracking adapter

- `compositing/tracking.py` is OpenCV behind one function, `measure`, and its
  output is tracker-independent (SPEC-0012 §1): the boundary exists; a
  Blender or model tracker (CoTracker) would be another function with the
  same output. OpenCV is the `media` extra; reused as it is.
- Weaknesses found: points lost are never replaced (the mean of what is left
  drifts as features die); no forward-backward check or confidence; a point
  track's rotation and scale are always 0 and 1 (one point); measured at the
  render's size, every render.
- Reusable: the format, `warp.corner_pin`'s plane input, `curve.from_track`,
  the frame-by-frame reading that holds two frames (CT-0071).
- To add: the track as a **production record** (measured once on the
  source at its own size, stored with its clock in ticks, reviewable and
  correctable by a person -- a human gate, ADR 0022 §5), read by `track.read`;
  forward-backward error per point as its confidence; re-seeding in the
  region when points are lost.

# Gaps, dependencies, tests

Gaps (all above): frame picking stutters; source shorter than a speed-up;
no blending between source frames; tracks without a clock, read by index,
misaligned by a trim; sound ignores retimes; one length for two; time ops
off GL; nothing exposed.

Dependencies: ADR 0023 (`timebase`: ticks, `frame_of_tick`, `TimeRange`) --
done; the beats in shot seconds (CT-0067) -- done; OpenCV -- present.

Tests to write, each before its fix:
- the frame-number clip: 2x gives 0, 2, 4, 6, 8, 10... over a source read to
  its needed length; half speed with blending gives 0, 0.5, 1, 1.5; a ramp's
  cadence is monotone;
- a ramp landing on a beat: the frame at the beat is the source frame the
  ramp names;
- a track with an origin read from a file made on the whole take lands on
  the cut's frames; a corner pin downstream of a remap follows the
  retimed plate;
- trails follow a moving layer (the echo before the merge);
- the sound of a retimed shot follows its policy (muted, or stretched to
  the picture);
- GL equals the reference on every time op.

# A sequence, from the audit

1. **The remap's semantics**: floor frame picking (ADR 0023); the source read
   as far as the remap reaches (an extent computed from the curve);
   `interpolation: nearest | blend` between source frames; `time.blend`
   renamed in the spec as a shutter. Engine work, small, tested on the
   frame-number clip.
2. **Time records with a clock**: tracks and retime curves carry rate and
   origin in ticks; tracks looked up by source time; `track.read` aligned by
   origin. The source/timeline contract.
3. **The shot's two lengths and the sound policy** in the assembly: source
   range and cut duration; sound muted, kept at speed 1, or stretched
   (FFmpeg's `atempo`/`rubberband`, pitch kept) -- the user to choose the
   default.
4. **Exposure**: a `retime` on a shot or layer (speed keys, reverse, freeze,
   on beats), `echo`/`trails` and `offset` on layers, a `track` and `pin`
   on layers -- compiled into the existing nodes (ADR 0022).
5. **The track as a record**: measured once, stored with its clock,
   reviewable; re-seeding and confidence in the OpenCV adapter.
6. **GL**: time ops reading their inputs at other frames.
7. **The done-when films**: the ramp on a beat, the trail, the window.

# The user's decisions on the audit (2026-10-15)

- **Mapping apart from interpolation**: the remap says which source instant;
  `nearest` or `blend` says how it is pictured -- so optical or model
  interpolation is a new name, not a new remap. `floor` finds the frame that
  contains an instant, and the two either side for a blend, whose fraction
  weighs them; it is not imposed on every sampling policy.
- **`time.blend` keeps its meaning**, a shutter over output frames.
- **Sound under a retime: no single policy.** Offered explicitly; `mute` the
  default for a non-trivial retime, so nothing drifts out of sync unseen; a
  shot without a retime keeps today's behaviour. Their limits, written
  before building them:

  | Policy | Does | Limits |
  |---|---|---|
  | `mute` | the take's sound silent for the shot | the shot needs another sound (music, a cue) or is silent; speech lost |
  | `preserve` | the take's sound at speed 1 from the cut point | in sync only where the picture runs at speed 1; when the shot's length changes, the sound is cut at the shot's end or ends before it (padded with silence) -- to be stated in the plan's notes; never in sync through a ramp |
  | `stretch` | the sound follows the picture's speed, pitch kept (`rubberband`, or `atempo` for a constant speed) | a constant speed is one filter; a ramp needs the sound cut in pieces each stretched to its speed, or a time-varying stretcher -- artefacts at extreme speeds (below 0.25x, above 4x) and on transients; reverse is not a stretch |
  | `resample` (later) | speed and pitch change together, a tape run fast or slow | for an effect only; a ramp needs a varying resample |

- **Tracking**: persistent records with the source's clock, coordinates
  independent of the render's size (fractions of the picture, as SPEC-0012
  §1 already stores them, with the measured size recorded), a confidence,
  and a person's review -- not a computation repeated on every render.

## Step 1 -- the remap's meaning (done 2026-10-15)

- `semantics.remap_samples` (one rule for both renderers): `nearest` is the
  frame containing the instant (`floor`); `blend` the two frames whose
  centres stand either side, weighted by the fraction.
- **Exact instants, after the user's review**: at 2x every instant falls on
  a boundary, and the curve -- float32 keys -- put it at 6.9999999, so a
  plain `floor` still stuttered (found by the test). A first fix added a
  tolerance to every floor; the user's review pointed out that it moves an
  instant truly before a boundary across it, against the exact base just
  built. Now: a map of linear or held keys, or a constant, is followed in
  exact fractions at the exact rate (`reference.exact_keys`,
  `remap_instant`) -- no tolerance; only an approximate map (Bezier eases,
  noise, combinations) is placed by the explicit, tested policy
  `BOUNDARY_TOLERANCE`.
- `time.remap` takes `interpolation` (`nearest` by default); its input is
  read as far as the map reaches (`reference.reach`, from the map curve and
  negative offsets), past the shot's end; past the source, its last frame
  (also for an array input).
- The assembly reads a shot's takes to the graph's reach.
- `time.blend` unchanged; the spec now calls it a shutter.

Implications for the next steps:
- **Step 3 is now pressing**: a shot retimed faster already reads past its
  cut point in the take, while its sound is still the take's span at speed
  1 -- exactly the drift the `mute` default prevents. The audio policies
  should come before any retime is exposed.
- Before the source's start a remap shows its first frame: the graph's
  extent begins at the cut point. Reading the take's frames before the cut
  (a pre-roll, for a map that goes back past the start) needs the source
  read from earlier with its origin -- part of step 2's clock.
- The reach is computed per remap node at output times; a remap nested
  under another is evaluated at the outer one's times, which the estimate
  does not follow -- a conservative bound (the larger of the two) or a
  composed evaluation is needed when nesting is exposed.
- `nearest` and `blend` are the reference's; GL still refuses time ops
  (step 6): a retimed shot draws on the reference, slower.

## Before step 2: a retimed shot is muted (done 2026-10-15)

The user: protect now, the other policies in step 3. A shot whose graph
shows any source at another time than its own, by half a frame or more
(`reference.retimed`, through the same composition as everything below), has
its take's sound muted, its speech cleared (no ducking under silence), and a
note in the plan. A shot without a retime is untouched -- including a remap
that changes nothing.

## Step 2 -- source time and timeline time (done 2026-10-15)

- `compositing/clock.py`, one walk: from a node to a source, composing each
  time operation (`step`: a remap's map, exact for linear or held keys; an
  offset's frames), over every path (`instants`) -- or the single one a track
  needs (`instant`, refusing disagreement). `extents` gives each source's
  first and last local frame read, over every output frame and path; the
  reference's `reach`, `preroll` and `retimed` use it, so nested remaps and
  offsets are followed exactly (the step-1 limitation lifted).
- **Origins**: `evaluate` and `render` take each source port's media origin;
  a `generate.source`'s is its `start`. The assembly gives a take's: its cut
  point, exact on the take's grid. Origins enter the cache identity.
- **Pre-roll**: a source is read before its local zero as far as its media
  has frames (`Shifted`: local frame -k is the frame k before the cut); the
  assembly reads takes that way; before the media, its first frame.
- **Tracks with a clock**: a track says its `clock` (`rate`, `origin` as a
  time record); `track.read` says what it describes (`of`); a measured track
  is given its input's clock. Read at the media instant its source shows,
  through the walk -- so a track of the whole take lands on the cut, and a
  reader over a retimed plate follows the plate. Without a clock, as before.
- `warp.corner_pin` and `curve.from_track` read tracks this way; a point
  track moves a pinned picture from where it was at the shot's first frame.
- Held frames, one rule (`_from_held`): before what a source holds, its
  first (a pre-roll's first); past its end, its last -- arrays, clips,
  shifted clips.

Implications:
- **Audio**: everything the sound policies need is now known per shot: the
  source's instant at every output frame (`clock.instants` from the output
  to the take), exactly where the map is exact. `preserve` is the take from
  the cut at speed 1; `stretch` follows the instants -- for a constant speed
  one stretch, for a ramp the instants cut into pieces each with its own
  speed; reverse refused for `stretch` (step 3).
- **Tracking**: a track can now be a production record measured once on
  the whole take and reused by any shot cut from it, any retime -- step 5
  writes those records (with confidence and review); `track.read` already
  reads them right.
- GL still refuses time ops and tracks (step 6); a retimed or tracked shot
  draws on the reference.

# Done

- Read every time and track node, its tests, SPEC-0012 §6, the assembly's
  reading of takes and sound; probed the remap, half speed, blend and
  reverse on a frame-number clip.

# Validation

- Step 1 (`tests/test_time_ops.py`): nearest is the frame containing the
  instant; blend weighs the two frames either side; 2x over ten frames
  reads twenty, 1, 3, 5 ... 19, evenly (was 1, 3, 4, 6, 8, 9, 9 ...); half
  speed repeats (0, 0, 1, 1) or blends (0, 0.25, 0.75, 1.25 ...); at speed
  1 both interpolations give the source; reverse and freeze; a ramp never
  steps back and runs faster at its end; past the source, its last frame;
  a graph reaches as far as its remaps and negative offsets read; a source
  file is read that far; `time.blend` stays a shutter.
- Boundaries (after the review): an exact instant on frame 7's start is
  frame 7, a billionth of a frame before it frame 6; the same instants in
  floats follow the stated tolerance; keys a billionth of a second short of
  2x give 0, 2, 4 ... (exact), on 2x 1, 3, 5 ...; an eased map stays
  monotone; a map that turns back reaches its furthest instant (15 frames
  for one peaking at 1.45 s and ending at 0.5 s); before the source, its
  first frame; a blend on the last frame holds it, for an array and a clip.
- Full suite: 855 tests pass.
- Step 2 (`tests/test_time_clock.py`): an offset under a remap composes
  (frame 0 of a 2x remap over a two-frame offset reads -0.1 s, exactly);
  nested remaps compose (0.25 s -> 0.5 s -> 1.5 s); a source at two times is
  kept for pictures and refused for a single instant; extents follow every
  path and reach back (-5 to 9 frames, a pre-roll of 5); a shot is retimed
  only when a source is shown at another time (a remap that changes nothing
  is not); a track of the whole take lands on the cut (entries 10, 11, 12 ...
  from a cut at 1 s; 0, 1, 2 with no origin); a reader over a 2x plate
  follows it (1, 3, 5, 7, 9); a reader whose source is shown at two times is
  refused; a measured track keeps its clock; a remap back past a source's
  start reads the file's earlier frames (5, 6, 7 before a start at 10); in a
  cut, a retimed shot is muted with a note and the other heard.
- The user's review asked for three scenarios explicitly (`ScenarioTests`):
  a whole-take track stays right after a trim (a cut at 2 s reads entries
  20, 21, 22), an offset (17, 18, 19) and a reverse (29 down to 20); a source
  in two branches at two times, mixed and echoed, composes without a false
  ambiguity -- only a reader needing one instant refuses; a corner pin after
  a retime that runs forward then back moves its strip by exactly the
  entries the plate shows, turning back with it. And a trim is not a
  retime: a later cut point (an origin), a zero offset or an identity remap
  leave the sound alone; a non-zero offset is a retime (its picture is
  shown late against the take's sound), and is muted.
- Full suite: 866 tests pass (the four scenario tests added after it, run
  alone).
- The probes above (reproducible with a ten-frame clip whose red channel is
  its frame number). No code changed.
