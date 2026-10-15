# ADR 0023: Time is exact -- fractions to compute, ticks to store, a media clock to play

Status: accepted (2026-10-15, CT-0079), on the user's word after a measured
investigation and an outside review the user brought. Applies to the time
records C7 creates and to playback (C9b); existing formats are not migrated
wholesale.

## Context

The assembly kept time as floating-point seconds and talked to FFmpeg in
decimals. Measured (CT-0079, a film whose takes flash and click at one
instant): every shot's sound led its picture by the fraction of a frame its
cut point fell inside (16.67 ms at 24 fps, from a 0.35 s trim); NTSC was
written as 2997/100; sounds were placed in whole milliseconds. Fixed through
one module, `timebase.py` -- rates as fractions, cut points on the frame grid,
sound in samples -- an hour at 30000/1001 keeps every click within half a
sample of its frame.

C7 adds time that is stored, compared and exchanged, not only computed:
tracks, retiming curves, keyframes, layer offsets, a version's cut points,
cache identities. FilmCraft and EffectCraft (`ai-context/references.md`) keep
all time as one integer: 254,016,000,000 ticks a second.

## Decision

1. **One interface**: every conversion between seconds, frames, samples and
   ticks is in `cine_toaster/timebase.py`. Operators of the graph and the
   assembly call it; none converts on its own.
2. **Compute with exact fractions** (`fractions.Fraction`): rates
   (`rate("30000/1001")`), instants, lengths. Never a rounded decimal; a
   decimal rate is read as the nearest fraction with a denominator up to
   1001 (29.97 is 30000/1001).
3. **Store and exchange in ticks**: `TICKS_PER_SECOND = 254_016_000_000`
   (2^12 x 3^4 x 5^6 x 7^2), FilmCraft's and EffectCraft's base, so an
   exchange with them is lossless. Exact for every frame rate we meet (8 to
   120, the /1001 family) and every common sample rate (8 to 192 kHz).
   - `to_ticks` is **exact by default**: a value that is not a whole number
     of ticks is refused (`NotRepresentable`), never rounded silently.
   - **Quantising is explicit**: `to_ticks(value, rounding=...)` with a named
     policy -- `floor`, `ceil`, `half_up`, `half_even`. An exact round trip
     (fraction, ticks, fraction) returns the value; a quantised one may not,
     which is why a record keeps the fraction (4).
   - **Bounded**: a stored instant or length is within +/-`TICK_LIMIT`, a
     quarter of a signed 64-bit integer (about 105 days, FilmCraft's own
     bound), so sums and offsets never overflow where ticks are 64-bit;
     beyond it, refused.
4. **Ticks do not limit sources.** A source at a rate the base does not hold
   (11 or 13 fps) is accepted; its own times stay rational, and a record of
   one of its instants keeps the exact fraction beside the quantised ticks
   (`to_record` -> `{"ticks": ..., "exact": "5/11"}`; `from_record` returns
   the fraction).
5. **Four kinds of time, each named**: an instant (ticks), a frame index (an
   int, `frame_of_tick`, `tick_of_frame`), a sample index (an int,
   `sample_of_tick`, `tick_of_sample`) and a **half-open range**
   (`TimeRange(start, duration)` in ticks: it holds its start and not its
   end, so ranges that meet do not overlap). A frame index is never a time,
   and a time is never a frame index, without the conversion saying so.
6. **People write what they read**: a person's YAML keeps seconds, frames or
   timecode, converted once on reading. Machines' records (tracks, retime
   curves, keys written by a tool, cut points of a version, cache
   identities) store ticks.
7. **Drawing is not editing**: the graph samples its curves at frame centres
   for pictures; those samples are not edit points and are not stored.
8. **No wholesale migration**: existing formats change when they are next
   touched for a reason, and new C7 records start in ticks.

## The media clock (playback; contract now, implementation with C9b)

Ticks say *when* something happens on the timeline; a media clock says
*which instant is playing now*. They are complementary, and only playback
needs the second -- the offline render stays deterministic, independent of
any clock of the machine.

- **The sound is the master** (FilmCraft, EffectCraft): while playing, the
  timeline's position is the position of the samples the device has
  *actually played* -- the samples sent minus what is still in the output
  buffer (its latency) -- and the picture shows the frame of that instant
  (`frame_of_tick`).
- **Its interface**: play, pause, seek (to ticks), the current position in
  ticks, a speed (a fraction: 1, 1/2, -1), and synchronisation with the
  audio device.
- **Normal playback only**: seek, scrubbing and stepping frame by frame (a
  review, C7's tracking review) set the position directly; no clock runs
  while they do, and playing resumes from the position set.
- **Without sound** (no device, or a silent preview): a monotonic clock is
  the master.
- **When**: the contract is recorded now; the clock is built with C9b's
  real-time executor and the player's audio backend, not before.

**Three responsibilities, apart**: `timebase.py` represents time; the media
clock governs playback; the renderer computes results for instants it is
given -- and never asks a clock which instant it is.

## Consequences

- C7's records are exact and exchangeable from their first version; a
  tracking result written today reads the same in FilmCraft tomorrow.
- A source at any rate is accepted; only its storage tells exact from
  quantised, and says so.
- Changing the representation again means changing `timebase.py`, not the
  operators.
- The flash-and-click films (`scripts/research/time_drift.py`,
  `tests/test_timebase.py`) are the regression bench for every change to
  time.

## How it was reached

CT-0079: the user asked for the research before C7, with FilmCraft's base as
the reference and the caution not to adopt ticks before a fault was shown to
come from the representation. The measurement separated three faults (frame
grid, rate, samples), corrected a statistical over-reading (a "drift" that
was scatter), and -- after the review asked for an exact instrument -- showed
every click within half a sample over an hour. The user then accepted
fractions to compute and ticks to store, adding: exact conversion by default
with quantising only on request; sources not limited by the base, their
fractions kept; frame, sample, instant and range kept apart; and the media
clock recorded as the playback half of the same architecture.
