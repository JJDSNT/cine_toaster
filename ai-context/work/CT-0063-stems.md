---
id: CT-0063
title: Stems -- a version's sound in parts, for a final mix in a DAW
type: work
status: done
owner: unassigned
created_at: 2026-10-04
updated_at: 2026-10-04
tags:
  - sound
  - assembly
---

# What

Backlog "Next": stems for Ardour (CT-0048's remainder; `docs/sound.md`; the
Sound Designer in `docs/production-agents.md`: "prepare stems and hand work to
an external DAW such as Ardour; Cine Toaster should not reimplement a DAW").

# Done

- `stems.py`: `write` lays the pieces the mix already uses into five stems:
  - `dialogue`: takes while someone speaks, and voice-overs;
  - `room`: takes otherwise;
  - `effects`, `ambience` and `music`: catalog cues by kind.
  Each stem keeps the mix's gains, fades, J/L handles and ducking. It is a
  stereo 48 kHz 24-bit WAV, the length of the cut, starting at zero. Empty
  stems are not written. `stems.json` gives the manifest and Ardour import
  steps.
- `assembly.render`: with `plan.stems`, the stems are written from the same
  `takes`/`cues` list the 5.1 uses, computed once for both.
- Assemble job param `stems`. The stems land beside the version in
  `versions/vN.stems/`, and only for the main cut: a format's sound is the
  same. Also `toast assemble --stems` and MCP `assemble_scene(stems=True)`.
- `docs/sound.md` § Stems.

# Decisions

- **No DAW session file.** Ardour's session format is versioned XML, and
  generating it would be the start of reimplementing a DAW. Equal-length WAVs
  from zero plus import steps work in any DAW.
- **No limiter on stems.** The final limiter belongs to the final mix.
- **Stereo stems.** 5.1 stems wait for the 5.1 phases the user paused
  (CT-0052).

# Validation

- `tests/test_stems.py` assembles the demo with an ambience, music and an
  effect, adopts the version, and checks:
  - the stems' format and length;
  - none is clipped or empty;
  - summed, they match the mix within 0.5 LU and 0.5 dB along the cut.
  A sample-by-sample subtraction is not usable: the mix passes through AAC
  twice and the limiter has a 5 ms lookahead.
- Investigation on the same fixture: 0.1 LU apart, envelope within 0.05 dB.
- 3-01 on the scratch SINGULAR copy, at real length: see below.
- Full suite before commit.
- 3-01 at real length on the scratch copy: 88.4 s; dialogue (19 pieces),
  room (6), effects and ambience; none clipped. 3-01 has no music.

# Found on the way

- **Migration defect.** The migration archived a scene's `teste/` folder into
  `archive/tests/` but did not rewrite the references to it. So 3-01 P2's
  "Claire?!" (Kael, recorded apart) was not heard in the migrated film; the
  assembly only noted it.
  - Fixed: the migration rewrites `teste/` to `archive/tests/` (and `compare`
    knows it), with a test.
  - ~/films/singular: the one reference was corrected and committed in the
    film's git (`aed0f91`). The migration was not re-run, because SINGULAR now
    holds two files a re-run would carry (below).
- **A missing line audio is now an error** (`line_audio_missing`), before any
  assembly, registered in `CHECK_CODES` and `every-line-is-filmed`.
- **SINGULAR was written by me.** On 2026-10-04 at 16:36, during CT-0055, I
  ran SINGULAR's own `cena_ltx.py <scene>/ltx prompts` believing it only read.
  For 1-04 it extracted two last frames into
  `cenas/1-04/ltx/trabalho/` (`p01-ultimo.png`, `p1s-ultimo.png`).
  - They are ignored by its git and are not in the migration or the
    2026-09-29 backup.
  - Moving them out was refused by the session's safety rules, so they stay
    for the author to remove.
  - Lesson: never run SINGULAR's tools, even to read, without reading what
    every code path they take writes.
- **Two readings of one field.** `toast voice` (the reel) writes a line's
  `mix.file` relative to the production root, while the assembly reads it
  relative to the scene's folder (SINGULAR).
  - `line_audio_missing` accepts either place, as their consumers do.
  - A line spoken by Cine Toaster itself (`voice: piper/...`) that is not
    made yet is advice (`toast voice`), not an error.
  - Remains: one convention for `mix.file`. The scene's folder is the
    likelier one, since a version snapshots the scene.
