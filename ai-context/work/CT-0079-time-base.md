---
id: CT-0079
title: Research -- the time base (FilmCraft's ticks against our seconds)
type: work
status: done
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

# The fixes (done 2026-10-15, authorised by the user)

The user: implement the three fixes with their regression tests and a new
measurement, validating the engine on PCM before any lossy codec; keep one
time interface so ticks could replace it without touching the operators; and
**do not close the time-base question because Fraction passed the tests** --
decide it explicitly before C7.

- `cine_toaster/timebase.py`, the one interface: `rate` (an exact fraction
  from "30000/1001", "29.97", 29.97 or a float of a fraction -- the nearest
  fraction with a denominator up to 1001, NTSC recognised), `ffmpeg_rate`,
  `frame_at`, `seconds_of`, `snap`, `samples_of_frames` (positions from the
  frame count, rounded once: never summed per frame), `samples`, `seek`
  (floored to the microsecond, so the frame starting there is read).
- Rate: `probe` keeps the file's fraction; every rate handed to FFmpeg in
  the assembly and the reference (`-r`, `fps=`, `-framerate`) is a fraction.
- Frame grid: `plan_scene` snaps every take's cut points to the take's grid;
  pieces start where counted in frames (`seconds_of`), and every seek is
  `seek`.
- Samples: each shot's sound trimmed and padded by samples
  (`atrim=end_sample`, `apad=whole_len`) and laid with `adelay=...S`; the
  mix's length in samples.

# Remeasured

The engine (the joined picture's frame numbers against the PCM mix) and the
delivery (the cut's AAC) agree in every run: FFmpeg's decoder removes AAC's
priming, so the codec adds nothing measurable here.

| Rate | Film | Rate written | Click minus flash (samples) | Trend |
|---|---|---|---|---|
| 24 | 10 shots | 24 | **0** in every shot (was -800) | 0 |
| 30000/1001 | 40 shots | **30000/1001** (was 2997/100) | **-0.4 to +0.4** (was -780) | none |
| 30000/1001 | **an hour**: 6 takes of 10 min, a flash every 300 frames (360) | 30000/1001 | the assembly adds **-0.4 to +0.4** per click | 0.3 samples an hour |
| 25, 20 (on the grid), 24000/1001 | 4 shots each (tests) | as given | within 0.5 | -- |

+/-0.4 samples is the grid's own limit: an NTSC frame is 1601.6 samples, so
its boundaries fall between samples, and a shot's sound can only start on a
whole one.

**The instrument made exact** (the user's review: the meter must be more
precise than what it measures; the one-sample goal kept, not loosened). The
first hour-long run showed a 1.4-sample maximum; the takes themselves
carried up to one sample, from `aevalsrc`'s `mod(t, 10.01)` in floating
point. The clicks are now made by whole sample index (`n`): frame 20 and
every 300 frames after fall on whole samples at every rate measured (32,032
+ 480,480 k at 30000/1001), and a rate where they would not is refused.
Re-run: the takes exact (0 samples); the cut's clicks take exactly five
values, -0.4, -0.2, 0, +0.2, +0.4 -- the fractional parts of 1601.6 per
frame -- so **every click is within half a sample, by construction**: each
shot's sound is placed from its frame count, rounded once.

A fitted "trend" of 0.33 +/- 0.04 samples an hour remains, and is not a
drift: the errors are not noise but a deterministic pattern bounded by
+/-0.5 (positions are computed absolutely, never summed), so a line fitted
through it reflects where the pattern's values fall in the hour, and its
standard error -- which assumes independent noise -- does not apply. Over
any length the error cannot leave +/-0.5 samples (10.4 microseconds).

# Fraction or ticks -- to decide before C7

Open, as the user asked. What each would be in Cine Toaster:

| | `Fraction` (now, behind `timebase`) | FilmCraft's ticks (254,016,000,000 a second) |
|---|---|---|
| Exact for | any rate and any instant | every broadcast rate and common sample rate; not, say, 11 fps |
| Mixed rates (a 25 take in a 24 cut; 44.1 kHz in 48 kHz) | exact, by construction | exact, one integer for both |
| Records and caches | needs a text form ("1001/30000") in YAML and JSON | one integer: sortable, hashable, compact |
| Exchange | OTIO's RationalTime is (value, rate) -- converts from either; with FilmCraft/EffectCraft, ticks are theirs, lossless | |
| Speed | slow per operation, at planning scale irrelevant; not in per-pixel code | integer arithmetic |
| Where it would live | in memory, at the boundaries of `timebase` | in records and in memory |

What C7 adds to weigh: tracks (a sample per frame, often at the source's
own rate), retiming (`time.remap`: an instant per output frame, not on the
input's grid), sync of several sources -- all instants that are stored, compared
and exchanged, not only computed. That is where an integer is worth more
than a fraction: a track written today and read by FilmCraft tomorrow.

**Coverage of FilmCraft's base**, checked: 254,016,000,000 = 2^12 x 3^4 x
5^6 x 7^2. Exact for every frame rate Cine Toaster meets -- 8, 10, 12 (the
demo), 15, 16 (generated video), 20, 24, 25, 30, 48, 50, 60, 120 and the
/1001 family -- and every common sample rate (8 to 192 kHz, the 44.1 family
included). Not for rates with another prime (11 or 13 fps): a take at such a
rate would be read at its own fraction and placed on the film's grid, never
stored in its own ticks.

The user's review agreed on keeping both (Fraction to compute exactly,
ticks to store and exchange), with the decision taken on the whole graph's
time model -- curves, keys, layer offsets and tracks in C7 -- not only the
assembly's. **Decided (2026-10-15, the user): ADR 0023.** Fractions to compute, ticks
to store and exchange, people's YAML in seconds, frames or timecode -- with
the user's three additions:

1. **Exact and explicit conversions**: `to_ticks` refuses a value that is
   not a whole number of ticks (`NotRepresentable`); quantising only with a
   named policy (`floor`, `ceil`, `half_up`, `half_even`).
2. **Ticks do not limit sources**: an 11 or 13 fps source is accepted; a
   record of one of its instants keeps the exact fraction beside the
   quantised ticks (`to_record`/`from_record`).
3. **Four kinds of time kept apart**: instant (ticks), frame index, sample
   index, half-open `TimeRange` -- each with its own conversions.

Applied to the new time records of C7 (curves, keys, offsets, retiming,
cache identities), not as a wholesale migration of existing formats. The
**media clock** -- which instant is playing now, the sound as master,
counting the samples actually played (output latency included), a monotonic
clock without sound, an explicit position frame by frame -- is recorded in
the same ADR as a contract, to be built with C9b, not before.

# Done

- Read FilmCraft's and EffectCraft's section 2 and FilmCraft's
  `crates/time` API; checked the constant's arithmetic.
- Measured the assembly at 30000/1001 and 24 (above); the drift corrected
  by a fit over every shot after the user's review doubted it.
- Natron (CT-0078), checked again at the review's request: its round-trip
  test already uses premultiplied random alpha (transparent edges included)
  and values to 3x white; exact to half-float precision.
- The three fixes, the regression tests (`tests/test_timebase.py`) and the
  remeasurement, including an hour at 30000/1001.
- The decision (ADR 0023) and its interface in `timebase.py`:
  `TICKS_PER_SECOND`, `to_ticks` (exact, or by a named rounding),
  `from_ticks`, `representable`, `tick_of_frame`/`frame_of_tick`,
  `tick_of_sample`/`sample_of_tick`, `to_record`/`from_record`, `TimeRange`.

# Validation

- `tests/test_timebase.py`: a rate is an exact fraction however written;
  FFmpeg is told the fraction; cut points snap; sound positions from frames
  stay within half a sample over an hour; a seek never passes its instant;
  a cut at 24, 25, 20 (a trim on the grid), 24000/1001 and 30000/1001 keeps
  its rate and lays every click within half a sample of its flash, in the
  PCM mix and in the delivered AAC.
- Full suite: 829 tests; `test_stems` failed once more at exactly its 0.5 dB
  bound (the intermittent test recorded in the roadmap) and passed three
  runs alone.
- Ticks (`TickTests`, `RangeTests`): every frame and sample rate we meet is
  whole ticks; an exact conversion refuses 1/11 s and an 11 fps frame, and
  an unknown policy; each policy quantises as named; round trips through
  ticks and through records are exact; an 11 fps instant keeps "5/11" and
  reads back exactly; frame, sample and tick indices convert as stated
  (frame 10 at NTSC is sample 16,016); ranges are half-open; a quantised
  round trip differs while its record keeps the original; stored ticks stay
  within a quarter of int64 (about 105 days), beyond refused. Full suite:
  836 tests pass (the bound and its two tests added after, run alone).
- `scripts/research/time_drift.py` reproduces the tables (an hour: `<folder>
  6 30000/1001 600 300`).
