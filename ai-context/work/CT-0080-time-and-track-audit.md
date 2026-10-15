---
id: CT-0080
title: C7 -- time and track, the audit before building
type: work
status: done
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

## Step 3 -- the sound of a retimed shot (in progress)

**The contract** (`retime_sound.py`): a shot's `TimeMap` -- the media instant
shown at each output frame's centre, and the map itself at any instant
(`at`), so the sound, which lives between frames, follows the map and the
frames are where it is checked. Its kind: unchanged, **shifted** (each frame
its own instant moved by a constant, at speed 1: an offset) or **speed**; a
speed map cut into pieces of near-constant speed, edges where the map is.
The user's review separated the two properties: a shift needs no stretch --
the sound moves by the same amount -- and only a change of speed does.

**Binding and stems** (the user's addition, for the stems and a later DAW
exchange -- Ardour): the policy (mute, preserve, stretch) says what is done
to a sound; its **binding** says which clock governs it -- `source` (the
take's media: a shot's own sound, and only it, follows the map), `timeline`
(music, ambience, cues: they keep their place whatever the picture does --
already so: catalog sounds are placed on the cut, never muted by a retime),
`event` (bound to a visual event, a hit: later). Stems keep a stable
identity (dialogue, effects, Foley, music, ambience) so a policy applies to
the right one, and an exchange with a DAW -- stems aligned to the cut's
start, same rate, durations, sources named; reconform when the cut changes
-- is a later step, not C7's.

**Stretchers, measured** (`scripts/research/stretch_bench.py`, the user's
request: libraries before an engine of our own). One map -- 1x for a second,
2x, 0.5x -- and one set of signals: a sine, 2 ms clicks off any grid, and
three recordings (a voice, a synthwave track, the 1991 tape's sound).

| Stretcher | Licence | Length | Sine level | Pitch | Clicks (found, extra, worst) | Speed |
|---|---|---|---|---|---|---|
| anchored WSOLA (ours, numpy) | ours | exact | flat | 440 | 20/20, 0, 15 ms (mean 0.5) | 0.14 s/s |
| Rubber Band native (C API, offline R3, key frames every 10 ms) | GPL / commercial | exact | flat | 440 | 11/20, 6 extra, 10 ms | 0.10 s/s |
| FFmpeg rubberband, pieces + aligned splice | GPL (FFmpeg's, a process) | exact | -10.3 dB dips | 435 | 20/20, 3 extra, 7.5 ms | 0.49 s/s |
| SoundTouch (system library, ctypes, streamed) | LGPL 2.1 | exact | gaps (-180 dB) | 440 | 16/20, 3 extra, 19 ms | 0.02 s/s |
| AudioTSM WSOLA (streamed) | MIT | exact | flat | 440 | 20/20, 0, 23 ms (mean -10.6: drifts) | 0.05 s/s |
| Signalsmith Stretch (python-stretch) | MIT | exact | flat | 440 | whole buffer, constant speed: 17/17, -16 to -83 ms | 0.10 s/s |

Notes: `pylibrb`'s key-frame binding refuses every map (its std::map
conversion is missing), so Rubber Band was driven through its C API; its R3
engine keeps tones perfect but smears and doubles 2 ms clicks. Signalsmith's
Python wrapper processes a buffer per call, so it cannot be driven by a map
(blocks of 10 ms broke it: pitch 240 Hz -- our driver's fault, not the
library's); its C++ API (any input and output count per call) could be,
through a binding of our own. Onsets matched on the recordings are reported
in the results file but too few to rank on; **real material is judged by
listening** -- three files, every stretcher in turn, were given to the user.

**After the user's review of the benchmark** (architecture approved; the
algorithm conditional): the anchored WSOLA's worst 15 ms came apart into
three faults, each fixed and measured:
- at 1x every click +5 ms: in silence every candidate of the phase search
  scored nothing and the first (-5 ms) won the tie -- now searched from the
  anchor outwards, ties kept on the map;
- at 2x clicks at half their level (they fell in some of four overlapping
  grains), and at 0.5x repeated up to 15 ms early: **attacks are kept out of
  the grains and laid whole, at speed 1, on the instant the map gives them**
  (detected by a sharp rise of energy over the 8 ms before, to the sample;
  each copy ends before the next attack, close ones cross-fading faster);
- a detector that reported a 2 ms frame instead of the sample put attacks up
  to 95 samples off where clicks were not on that grid (found by the tests).
Measured after: the benchmark's 20 clicks at 0 or 1 sample, at full level;
ten attacks packed 10-30 ms apart around both changes of speed, all exact; a
sine flat within 0.01 dB and at 440 Hz; stereo coherent (a 1 ms offset
between channels kept to the sample, nothing leaking across); 60 s of music
under a 1x/1.5x/0.75x ramp in 25.8 s (0.43 s a second), 119 MB, length
exact. Shorter grains or less overlap were measured and rejected (transients
lost at 2x). Blind listening files (the original, then five stretchers in a
shuffled order, the key kept apart) were given to the user; the default
stretcher stays provisional until then.

**The stretcher chosen (2026-10-15).** The user could not judge the blind
files (the tape's excerpt was its quiet opening, -39 dB RMS -- the excerpt's
fault, not the code's) and left the choice here: **the anchored WSOLA**, the
only one measured to keep sync to the sample (anchored, never
accumulating), steady tones flat and in pitch through changes of speed, and
attacks whole on their instants, with no dependency or licence question.
Rubber Band's native engine is better on sustained tones but smears short
transients and would bring GPL code into the process; it and FFmpeg's
filters stay available by name. Not yet done, recorded in the roadmap: a
listening review of real material with representative, non-silent excerpts.

**Wired into the assembly** (the architectural part, released by the user):
`plan_scene` carries a shot's `retime_sound` (mute by default, preserve,
stretch) and `stretch_with` (anchored by default -- provisional -- or
rubberband, atempo by name, never swapped in silence); `_shot_drawing` builds
the shot's `TimeMap` from the source that is its take (`shown_instants`,
the same composition as everything in step 2); `_draw_shot` lays the policy's
sound under the drawing. Ambiguous maps, reverses and freezes under
`stretch` are refused with a note and muted. `toast doctor` reports the
stretchers available and the default.

## Step 4 -- exposure (done 2026-10-15)

Compiled into the existing nodes (ADR 0022), nothing new drawn:
- `compositing/retime.py`: a retime as written -- `speed` (a number, or keys
  `{t | beat, speed, ease: linear | hold}`), `reverse`, `freeze`,
  `interpolation` -- into a `time.remap` and its map: the integral of the
  speed, exact (linear keys) where the speed holds, sampled every 1/240 s
  where it ramps. A key on a beat takes the beat's time in the shot.
- A shot's `retime` compiles when it is drawn (its beats known), ahead of its
  effects and title; its sound follows `retime_sound`. A layer takes
  `retime` (seconds only: a layer compiles before its shot is cut -- beats
  and reverse refused with that reason), `offset` (seconds, a slope-1 map: a
  shift to the sound and the tracks), `echo` (after the move: trails follow
  the layer) and `pin` (`track` file or `measure` point/plane on a lower
  layer's source, `of`, `corners`; pinned or placed, not both).
- Found on the way: curve keys were held in float32 -- the source of the
  6.9999 frames of step 1 -- now float64 (GL conformance unchanged).

Limitations, recorded with how: a layer's retime cannot fall on beats or
reverse yet -- how: compile layers when the shot is drawn (as a shot's
retime is), not when the scene loads; a ramp's map is sampled every 1/240 s
(exact at each sample) rather than exact -- how: a curve op whose segments
are quadratic, if a use needs more.

## Step 5 -- the track as a production record (done 2026-10-15)

The user's direction: a track belongs to its media and is reused by any
shot under any retime; a persistent record with a stable identity, the
media referenced, the source's clock, normalised measurements and a
confidence per entry; manual review, correction, reseeding and weak
stretches; corrections kept apart from measurements, revertible without
losing the original; an explicit invalidation when the media or the
measuring change.

- `tracks.py`: `tracks/<id>/track.yaml` (identity, media path and content
  hash, kind, region, stretch, the measurement in use, revision),
  `measurements/NNNN.json` (each automatic measurement, never edited: its
  clock -- the media's exact rate, the origin on its frame grid -- its
  entries in fractions of the picture, what made it: tracker, version,
  region, media hash, size, when, by whom) and `corrections.json` (each
  correction: the entry, its value, the measurement it was made on, in force
  or reverted, by whom, when, why). Commands `measure_track`,
  `correct_track` (with an expected revision), `revert_corrections` (one,
  an entry's, or all) -- an actor, an event, a revision; `toast track
  measure | status | correct | revert`.
- **Invalidation**: `status` lists every reason a track no longer describes
  its media -- the media missing or changed (content hash), the tracker or
  its version changed, the kind, region or stretch asked differing from the
  measurement's -- and `load_track` refuses a stale track, naming the
  command that remeasures it. Corrections made on an earlier measurement
  are kept and counted, not applied to a new one.
- **The tracker** (`compositing/tracking.py`, version 2): measured at the
  media's own size; each entry's `confidence` is per step -- the share of
  the features followed into it that pass a forward-backward check (and a
  plane's RANSAC inliers), lowered under 16 features -- so features leaving
  the frame in a pan do not read as doubt, while an occlusion drops to 0;
  `reseeded` where features thinned out; a lost track held at no confidence
  and **re-acquired** by its last confident appearance (template matching
  around where it was), so it resumes where the content really is.
  `weak_spans` lists the stretches under a threshold.
- The graph reads a production track by id (`track.read` with `track`);
  layers' `pin: {track: <id>}` does.

Found on the way, each by a test: confidence first measured since the start
(features leaving a pan's frame made a clean track look doubtful; now per
step); a track losing every feature crashed OpenCV on the next frame (now
held, then re-acquired); reseeding where a lost track had been followed
another patch of the picture -- the texture had moved 14 px while hidden (now
re-acquired by appearance, exact).

Impact on the visual editor (C11): the record gives it what it needs without
another format -- the weak stretches to show (`status.weak`), a correction as
one command per entry kept apart from the measurement (a layer the editor can
show, hide or revert), the stale reasons to display before anything is
drawn, and every change as an event it can follow live. What it will add:
drawing corrections in the viewer (dragging a point or a corner at an entry),
interpolating between a person's corrections across a weak stretch (a
command over a range), and choosing the region by drawing it.

Limitations, recorded with how: re-acquisition matches the last appearance
by translation only -- a plane turned or scaled while hidden is found by its
centre, its corners carried, not re-fitted (how: re-seed and fit the
homography to the last confident appearance's features); a correction
replaces one entry -- no interpolation across a range yet (how: a
`correct_track` over `[first, last]` that interpolates between the entries
either side); a camera solve stays out (C8, Blender).

## Step 6 -- time and tracks on GL (done 2026-10-15)

**The audit first** (what GL drew, what it did on the CPU, what was
missing). In the reference and not on GL: in C7's scope `time.remap`,
`time.offset`, `time.blend`, `time.echo`, `track.read`, `track.measure`,
`curve.from_track` and a corner pin with a track; outside it
`colour.curve`, `colour.posterise`, `colour.solarise`, `filter.edges`,
`filter.glow`, `filter.sharpen`, `matte.label`, `merge.depth`,
`signal.align_depth`, `signal.read`, `warp.procedural` (left to their own
steps). Uploads of CPU-made data: decoded sources, text, noise, grain,
shapes; one download per output frame. No new primitive was needed: a
remap's blend is `mix` at a constant weight, the shutter a running mean of
`mix`es, an echo `over` with `mixing` = decay^i (the reference's formula).

**One semantics** (the user's condition): GL decides nothing about time.
- Shared with the reference, extracted from it: `TrackBook` (a track's data
  -- given, a file, a production record validated and corrected by
  `tracks.load_track`, or measured -- and the entry for the instant its
  source shows, by its clock), `pinned_corners`, `open_source` (a source read
  to the reach and back to its pre-roll), `_from_held`; plus `clock.remap_at`,
  `semantics.remap_samples`, `reach`, `source_extents`. GL calls them and
  draws what they decide.
- GL evaluates a node at any frame: values kept by (node, frame) as far back
  as the graph's time operations reach (`temporal_window`), let go after.
- A measured track's pictures come back to the CPU (OpenCV's), once.
- Origins reach GL as they reach the reference (`render`).

**Measured** (`scripts/research/gl_time_bench.py`, 1280x720, 48 frames):

| Graph | Reference | GL, llvmpipe (software) | GL, Intel UHD 620 (D3D12) |
|---|---|---|---|
| remap 2x blend | 29.6 ms/frame | 33.7 (0.9x) | 41.8 (0.8x) |
| trails | 399 | 83.9 (4.8x) | 34.0 (12.7x) |
| pin by track | 345 | 26.4 (13.1x) | 30.8 (11.5x) |
| all together | 678 | 74.3 (9.1x) | 37.3 (19.4x) |

Before step 6 every one fell back to the reference. Bottlenecks found and
fixed: allocating a 1280x720 float texture cost 7 ms -- more than most draws
-- so textures let go are pooled by size (with their framebuffer, kept on
the texture); framebuffers were made per draw. Left: a remap alone stays
transfer-bound (two frames up, one down, 14 MB each, through WSL's D3D12
layer) -- slower than the reference's array indexing; it gains only inside a
larger graph. GL ran on llvmpipe here by default; the GPU is used only with
`GALLIUM_DRIVER=d3d12` -- `toast doctor` now names the device and says so.

**Conformance** (`tests/test_gl_time.py`, on both drivers): retimes (2x,
half, reverse, freeze, an eased ramp, a turning map, before the start), each
nearest and blended; a blend on the last frame; offsets (+3, -2, 0); the
shutter (2, 3, 5); trails (several counts and spacings, none); nested and
combined (a reversed remap under a 2x remap, an offset, a move, trails); a
pin by a plane and by a point track; a pin over a plate retimed 2x, reversed
and turning; a curve from a track; a measured track; a production track
with a correction; a source read back past its start. Time operations
alone are held to every pixel (under 1e-4; measured ~1e-6); graphs that
warp, to the GL tests' mean and 99th percentile -- an Intel GPU samples a
warped edge with its own precision (2.2e-3 at worst there).

Limitations, recorded with how: a remap alone is transfer-bound -- how: keep
decoded frames on the GPU between output frames (an upload cache by source
frame), part of C9b's playback cache; the GL device is chosen by Mesa's
default -- how: pick the hardware driver when present, behind the doctor's
report (C9b); the eleven ops outside C7's scope still send a graph to the
reference.

## Step 7 -- the done-when films (done 2026-10-15)

In the music-piece production (`scripts/research/c7_films.py`), each drawn in
one graph by GL on the Intel GPU (D3D12), logged in `docs/trials.md`:

1. **A speed ramp lands on a beat** (SC-060 v2): the launch at 1x to the
   music's third beat, ramping and landing at 2x on the fifth (`{beat: n}`
   keys). Measured on the delivered film by identifying the take frame each
   film frame shows: 100 of 101 within one frame of the map; mean speed 0.96
   / 1.54 / 2.00 before, through and after the ramp (1.00 / 1.50 / 2.00
   asked).
2. **Trails follow a moving layer** (SC-070 v1): a launch flown across the
   Earth, `echo` after its move.
3. **A replaced window follows a moving camera** (SC-080 v2): SC-040's real
   cabin footage under a known camera move (synthetic, so its truth is
   known; the picture never shows its edges); the middle display becomes a
   window on the Earth, pinned by a plane track measured once on the plate.
   The track against the true move: 1.3 px mean, 2.3 px worst at 1920x1080,
   confidence 1.0 throughout.

Found by the films, each fixed with a test:
- **a shot made only of layers never read its `retime`** -- v1 of the ramp
  was not retimed, which only measuring the delivered film showed; the plan
  now carries it on that path too;
- **`layers` (since C4) and the new `retime`, `retime_sound`,
  `stretch_with` were undeclared shot fields** (a `shot_field_undeclared`
  advice on every layered scene); declared;
- a plane track could only fill its plane with the pinned picture; **with
  `corners` given, it now carries them as the plane moves** (the homography
  from its first corners to its current ones), one rule in
  `pinned_corners` for both renderers -- what a window on a moving wall
  needs.
- My first window film failed its own claim (the move too wide for its zoom,
  windows pushed out of the picture): redone with a contained move and the
  middle display.

Still to do, recorded: the same with real hand-held footage (a cabin or a
room filmed moving, its window tracked) -- the synthetic move proves the
chain and gives a truth to measure against, not the tracker's behaviour on
real motion blur and parallax.

## C7 closed

Done-when met (the three films). What C7 leaves, each recorded above with
how: a layer's retime without beats or reverse; a ramp's map sampled at
1/240 s; re-acquisition by translation only; corrections one entry at a
time; a remap alone transfer-bound on GL; the GL device left to Mesa's
default; eleven ops outside C7 still off GL; a listening review of retimed
sound; the moving window with real footage.

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
- Step 3 (`tests/test_retime_sound.py`): a map is unchanged, shifted or a
  speed; pieces follow the map between frames (1x, 2x, 0.5x from exact
  edges); policies are named, resample refused by name; stretch lays every
  attack on its instant to the sample and whole; keeps pitch (440 Hz in each
  speed) and level (within 0.5 dB) through the changes; stretch of a shift
  moves the sound exactly; preserve keeps the take's own speed from the cut
  point and pads where the take ends; mute is silence of the shot's length;
  a reverse or a freeze is refused; a stretcher asked and missing is refused,
  an unknown one too; stereo stays coherent; in a cut, a 2x shot with
  stretch lays its click at sample 12,000 as the picture shows it, and an
  offset of three frames moves the click by three frames.
- Found by the full suite: two assembly jobs timed out. A segment's sound
  map (Fractions) went into the job's JSON summary; storing the result
  raised outside the job's error handling, and the job stayed `running` for
  ever. Fixed twice: the map stays out of the summary (working state, not a
  record), and a result that cannot be recorded now fails the job
  (`tests/test_jobs.py`).
- Full suite after step 3 wired: 885 tests pass.
- Step 4 (`tests/test_retime_records.py`): a constant speed is an exact map
  (2x: 1, 3, 5 ... 19); held speeds are exact and a ramp integrates its speed
  (1x to 3x over a second: two seconds of source, 0.75 at the middle); a
  ramp lands on a beat (1x to the second beat at 0.7 s, then 8, 11, 14); a
  beat the shot does not have is refused; reverse and freeze; mistakes are
  named; a layer is retimed (2x) and offset (0.3 s: three frames late); a
  layer's retime refuses beats and reverse; trails follow a moving layer
  (lit to its left, fading); a layer is pinned by a track of the layer below
  (one pixel a frame); a pin says what it follows; in a cut, a shot's
  `retime: {speed: 2}` with `stretch` lays its click at sample 12,000.
- Full suite after step 4: 897 tests pass.
- Step 5 (`tests/test_tracks.py`): a track is a record of its media with its
  clock (24, origin 0) and a confidence per entry, following a 2 px a frame
  pan; an occlusion of six frames is the weak stretch (20, 25) and the track
  is found again where the texture really is (x = 28, for a point and a
  plane); corrections are kept apart and reverted without touching the
  measurement, with events measured, corrected, reverted; a correction is
  checked (index, shape, revision); a track whose media changed is stale and
  refused, naming the remeasure command, fresh again once remeasured, stale
  again when its region is changed; a new tracker version makes old tracks
  stale; corrections on an earlier measurement are kept, not applied; one
  track serves shots cut at 0 and 10/24 s, an offset, a 2x remap and a
  reverse, each reading the entry of the media instant it shows; a layer
  pins by a production track; the command line shows its status.
- Full suite after step 5: 907 tests pass.
- Step 6: `tests/test_gl_time.py` (above), on llvmpipe and on the Intel GPU;
  the GL refusal test now names an op GL still lacks (`colour.posterise`).
- Full suite after step 6: 918 tests pass.
- Step 7: the films measured as above; `PlanTests` (a shot of layers alone
  keeps its retime, its fields known) and the plane-pin carrying test.
- Full suite after step 7: 920 tests pass.
- The probes above (reproducible with a ten-frame clip whose red channel is
  its frame number). No code changed.
