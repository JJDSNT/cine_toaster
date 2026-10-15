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
| 30000/1001 | 40 (80 s) | **2997/100** | **-16.3 ms** every shot | +0.24 ms (~11 ms an hour) |
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
3. **The small drift** (0.24 ms over 80 s) comes from that rounded rate and
   from placing sounds with `adelay` in whole milliseconds and passing
   lengths with three decimals (up to 24 samples at 48 kHz each). Small, but
   it grows with the film's length and it is avoidable: positions in samples.

So the answer to "does the problem come from the representation?": partly.
The audible one (half a frame, every shot) comes from boundaries; the
NTSC rate and the drift come from the representation. Both are what
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

# Proposal (to do before C7, if the user agrees)

1. `cine_toaster/timebase.py`: `TICKS_PER_SECOND = 254_016_000_000`, `Tick`
   (an int), `FrameRate(num, den)` with `tick_of`, `frame_at`, `snap`,
   `TimeRange(start, duration)` half-open; conversions to seconds, frames
   and samples. No dependency.
2. `probe` keeps `r_frame_rate` as a fraction; the cut is written at it.
3. The plan's cut points (take in and out, overlaps, splits) are snapped to
   the take's frame grid when planned, as ticks; picture and sound are cut
   from the same snapped instants -- the picture by frame count, the sound
   by sample count (`atrim=start_sample/end_sample`, `adelay=...S`).
4. Re-run the measurement: click on flash within one sample, no drift, the
   cut at 30000/1001.

# Done

- Read FilmCraft's and EffectCraft's section 2 and FilmCraft's
  `crates/time` API; checked the constant's arithmetic.
- Measured the assembly at 30000/1001 and 24 (above).

# Validation

- The measurement script reproduces the table; the full suite (823 tests)
  passed before this record, which changes no code.
