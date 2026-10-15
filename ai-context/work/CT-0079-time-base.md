---
id: CT-0079
title: Research -- the time base (FilmCraft's ticks against our seconds)
type: work
status: doing
owner: unassigned
created_at: 2026-10-15
updated_at: 2026-10-15
tags:
  - time
  - assembly
  - sound
  - research
---

# What

The user asked to research the time base before C7 -- to avoid floating point
-- with FilmCraft's and EffectCraft's as the reference (their architecture,
section 2), and the caution that the ticks are not adopted before a problem
seen is shown to come from the representation and not from how segments are
aligned and encoded. Tracking, retiming and sync in C7 depend on the answer.

# The reference (read 2026-10-15)

- **One integer time**: `Tick(i64)` at 254,016,000,000 a second, the least
  common multiple of every broadcast frame duration (x1001) and every common
  sample rate: 23.976 -> 10,594,584,000 ticks a frame, 24 -> 10,584,000,000,
  29.97 -> 8,475,667,200, 48 kHz -> 5,292,000 a sample, 44.1 kHz -> 5,760,000.
  Every frame and sample position is an exact integer.
- **A frame rate is a fraction** (`FrameRate { num, den }`): `tick_of(frame)`,
  `frame_at(tick)`, `snap(tick)`.
- **Ranges are half-open**, a start and a duration (`TimeRange`): the end is
  never in doubt, and two ranges that meet do not overlap.
- **Seconds and timecode at the edges only**: commands take ticks, frames,
  seconds or timecode, converted once at the boundary; timecode is display.
- **Snapping**: EffectCraft snaps layer times, keys and durations to whole
  frames (as After Effects does); FilmCraft places video on frame boundaries
  and keeps sound sample-accurate in multicamera sync.
- **The audio clock** (FilmCraft's playback, EffectCraft's preview): while
  playing, the samples the sound card has played drive the playhead and the
  picture follows; without a device, the wall clock. A playback concern.

# Measured here (`scripts/research/time_drift.py`)

A film of N shots whose takes flash white at their frame 20 with a click at
the same instant (exact in the take), cut by the assembly, then each click
measured against its flash in the cut.

| Rate | Shots | The cut's rate | Click minus flash | Drift over the film |
|---|---|---|---|---|
| 30000/1001 | 40 (66 s) | **2997/100** | **-16.2 ms** every shot, scatter 0.26 ms | none measurable |
| 24/1 | 10 | 24/1 | **-16.67 ms** every shot | none |

What it shows:

1. **The big error is a boundary, not precision.** Every take is cut from
   0.35 s (a generated take's still first frame). 0.35 s is 8.4 frames at 24
   and 10.49 at 29.97: the picture starts on a whole frame, the sound at
   0.35 s exactly -- so the sound leads the picture by the fraction (0.4 x
   41.67 ms = 16.67 ms; 0.49 x 33.37 = 16.3). Any cut point not on the frame
   grid does the same, in every shot, at any rate. Floats did not cause it;
   the absence of one canonical instant for "where this shot starts" did --
   which is exactly what snapping to the frame grid, in one representation
   for picture and sound, prevents.
2. **The rate is rounded**: `probe` keeps three decimals, so 30000/1001
   becomes 29.97 and the cut is written at 2997/100 -- not an NTSC rate.
   This is representation: a rational rate kept as a fraction fixes it.
3. **The scatter, not a drift.** A first reading (first and last three
   shots) claimed ~11 ms an hour; the user's review (via ChatGPT) doubted it,
   and a linear fit over all 40 shots gives -9.8 +/- 8 ms an hour -- a change
   over the film (0.18 ms) below the scatter (0.26 ms): **no drift is shown**
   at this length. The scatter is what whole-millisecond `adelay` predicts
   (an error uniform within +/-0.5 ms: 0.29 ms deviation): each shot's sound
   is placed up to 24 samples off at 48 kHz, independently.
4. **The rounded rate drifts against the world, not within the cut**:
   picture and sound are both placed on the same rounded 29.97, so they keep
   together in the cut; but the cut runs 3.6 ms an hour off true 30000/1001
   (the ratio of the two rates) -- against another program's timeline, a
   timecode, an OTIO exchange.

So the answer to "does the problem come from the representation?": partly.
The audible one (half a frame, every shot) comes from boundaries; the
NTSC rate and the millisecond scatter come from the representation. Both are what
FilmCraft's contract solves together: a rational rate, every boundary
snapped to the frame grid, sound placed in samples from the same instant,
half-open ranges -- and one integer time that makes those exact.

# What the crafts teach us -- and what not

- **Adopt**: the integer tick (their constant; ours would be the same, so an
  OTIO exchange with FilmCraft keeps times exact), rational frame rates,
  half-open ranges, snapping cut points to the frame grid, sound in samples,
  seconds only where a person reads or FFmpeg is told.
- **The audio clock is a player's**: Cine Toaster renders offline and plays
  finished files; there is no playhead to drive. Its lesson applies when a
  preview player exists (the control room's, or C7's tracking review): the
  sound drives, the picture follows. In rendering, the equivalent is that
  the sound's placement is computed from the same snapped instants, in
  samples, never re-derived from a rounded picture time.
- **Curves and beats**: the graph samples curves at frame centres in seconds
  (`(frame + 0.5) / fps`); with an exact rational rate this is exact enough
  for drawing. Beats come from analysis as seconds and are measurements, not
  edit points: kept as they are, snapped where they place a cut.

# Causes, fixes and the tests that keep them fixed

Kept apart, as the user's review asked: numeric precision, the frame grid,
sample precision.

| Kind | Cause (measured) | Fix | Regression test |
|---|---|---|---|
| Frame grid | Cut points off the frame grid: picture on a whole frame, sound at the exact second -- the sound leads by the fraction (16.67 ms at 24 for 0.35 s) | Snap every cut point (in, out, overlap, split) to the take's frame grid when planned; sound cut from the same snapped instant | Flash and click: every click on its flash within one sample, at 24, 25, 30000/1001, 24000/1001, for trims on and off the grid |
| Rate | `probe` rounds `r_frame_rate` to 3 decimals: 30000/1001 written as 2997/100 (3.6 ms an hour off true NTSC) | Keep the rate as a fraction from probe to the writer | The cut's `r_frame_rate` is 30000/1001 for an NTSC take; a 24000/1001 take likewise |
| Samples | Sounds placed with `adelay` in whole ms and lengths in 3 decimals: up to 24 samples off per shot (0.26 ms scatter) | Positions and lengths in samples (`adelay=...S`, `atrim` by samples) from the snapped instants | Scatter of click-minus-flash below one sample across 40 shots |
| Precision | None shown yet: the fitted trend is within its error | Exact arithmetic where times are combined (see below) | A long film (an hour, synthetic) at 30000/1001: no trend beyond one sample |

**Exact without ticks, in Python**: `fractions.Fraction` keeps any rate and
any instant exact (`Fraction(30000, 1001)`), which is what FilmCraft's int64
ticks buy in Rust. So the first three fixes need no new time type: rates as
fractions, cut points as whole frames of their take, sound in whole samples.
Ticks become worth adopting when times must be one integer across rates --
a 30000/1001 take in a 24 fps cut, 44.1 kHz sound in a 48 kHz film, OTIO
exchange with FilmCraft -- to be decided after the remeasurement, as the
user's review recommends.

# Proposal (to do before C7, if the user agrees)

1. `probe` keeps `r_frame_rate` as a `Fraction`; the cut is written at it.
2. The plan's cut points snapped to the take's frame grid when planned
   (whole frames, half-open: a start and a length); picture and sound cut
   from the same snapped instants -- the picture by frame count, the sound
   by sample count (`atrim` by samples, `adelay=...S`).
3. The regression tests of the table, from `scripts/research/time_drift.py`.
4. Remeasure; then decide on ticks (`TICKS_PER_SECOND = 254_016_000_000`,
   half-open `TimeRange`) for mixed rates and exchange.

# Done

- Read FilmCraft's and EffectCraft's section 2 and FilmCraft's
  `crates/time` API; checked the constant's arithmetic.
- Measured the assembly at 30000/1001 and 24 (above); the drift corrected
  by a fit over every shot after the user's review doubted it.
- Natron (CT-0078), checked again at the review's request: its round-trip
  test already uses premultiplied random alpha (transparent edges included)
  and values to 3x white; exact to half-float precision.

# Validation

- The measurement script reproduces the table; the full suite (823 tests)
  passed before this record, which changes no code.
