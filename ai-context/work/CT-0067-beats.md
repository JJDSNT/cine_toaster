---
id: CT-0067
title: Beats as a record -- shots cut to music in beats
type: work
status: done
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - demos
  - music
  - editing
---

# What

Point D1 of the demos line (`development/roadmap.md`): a track's beats heard
and kept beside it, and a scene cut to music giving each shot's length, and
each transition's, in beats.

# Why

The first music piece was cut to the beat by two scripts outside the tool:
one heard the beats, the other worked out each shot's length in seconds. The
breakdown held only the seconds, so the next change to one shot would have
moved every join after it, and nothing would have said so (CT-0064).

# Done

- `toast sound beats <project> <sound>`: librosa, in the voice environment, as
  a worker (`beats_worker.py`, like `words_worker.py`); writes
  `sounds/<id>/beats.json` (tempo, beats in seconds, detector, the recording's
  SHA-256). `librosa` is now named in `requirements-voice.txt`; it was there
  only as Chatterbox's dependency.
- `beats:` on a shot, and on a shot's `transition`. `beats.lay_out` turns
  them into seconds when the scene loads: a straight cut on the beat, a
  transition with its middle on it. The scene's music must start with it.
- Checks, under the practice `cut-to-the-beat`: `beats_mixed`,
  `beats_without_music`, `beats_music_not_at_start`, `beats_past_end`,
  `beats_invalid` (errors); `beats_missing` (no beats, or beats heard in
  another recording; warning); `join_off_beat` (a transition longer than half
  a shot it joins, which the cut would shorten; warning).
- `toast doctor` reports Beats.
- `docs/trials.md`: a diary of the pieces made to judge the tool, at the
  user's request.

# To do (solvable limitations; the roadmap's D1b)

- Bars: a downbeat tracker and a person's correction in the record, then
  `bars:` on a shot and a check for a join that should open a bar.
- Music that starts after the scene does: count from where it starts.
- A missed or doubled beat: corrected by hand in the record, seen over the
  waveform.

# Decisions

- **The music starts with the scene.** Beats are counted from the scene's
  start; music placed later is an error, not an offset worked out silently.
  A piece that needs it can ask.
- **The beats are the detector's, kept with a checksum.** Another recording
  of the track is another set of beats, so beats heard in a file that has
  changed are refused rather than reused.
- **A bar is not assumed.** librosa gives beats, not downbeats; a shot counts
  beats, and the piece decides its own phrasing.
- **Tempo is shown, not used.** librosa reads it off a grid (117.5 for a
  120 BPM click track); the lengths come from the beats themselves.

# Validation

- `tests/test_beats.py` (4): joins at the right beats for cuts and both kinds
  of transition length, and the scene's total; each refusal and warning; a
  120 BPM click track heard with beats half a second apart.
- For real: `toast sound beats` on the music piece's track (123.047 BPM, 349
  beats), its first scene rewritten in beats, assembled as v3: 41.441 s, every
  shot's length within a millisecond of v2's, which a script had computed.
- Full suite: 628 tests pass (2026-10-14).
