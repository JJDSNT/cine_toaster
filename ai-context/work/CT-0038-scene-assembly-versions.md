---
id: CT-0038
title: Scene assembly from the chosen takes, as kept versions
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - assembly
  - versions
  - jobs
  - phase-2
---

# What

Assemble a scene's cut from the take chosen for each shot. Each assembly is
kept as a **version** that can be watched, judged, compared and restored.

# Why

The user wants "better control over the clips and the cuts/montages,
preserving versions to choose between them" (2026-09-29). Takes and assembly
records already existed. What was missing was making a version from the
chosen takes, since `build` renders only composed cards. This costs nothing
and runs on footage that already exists, so it came before generation
(CT-0037), which needs a budget.

# Done

- `assembly.py`:
  - `plan_scene` uses, for each shot, its selected take or the current one
    (`CUT`);
  - the cut point is `trim` (`{in, out}` or `{head, tail}`) or the shot's
    duration;
  - joins are straight cuts;
  - notes list what is not rendered yet: J/L cuts, transitions, composed
    cards, missing takes, and takes shorter than their shot.
- `render` cuts and normalises each take (size, frame rate, 48 kHz stereo;
  silence for a take without sound) and joins them without a second encode.
- Job kind `assemble` (SPEC-0008). A kind can now register an `adopted`
  hook: adopting an assembly places it at
  `renders/assemblies/<scene>/<version>.mp4` (never overwritten) and calls
  `record_assembly` with the takes it actually used. `record_assembly` gained
  a `takes` override.
- `toast assemble <project> <scene> [--version] [--summary]`.
- Versions panel: "Assemble a new version from the chosen takes". Adopting
  from the jobs tray refreshes the room.
- `ai-context/production-flow.md`: the two phases, what exists, and what is
  missing.

# Decisions

- SINGULAR's `corte` is **not** mapped to `trim`. Its `antes` and `depois`
  are seconds around the first and last spoken word, from transcription.
  Speech-aware trimming is a later step, and until then the notes say what
  differs.
- Versions made by a production's own tools can still be registered
  (`toast version record`), so both kinds can be compared.

# To do

- Transitions and J/L cuts in the assembly; speech-aware trims (needs
  transcription, which `toast doctor` already detects).
- Sequence assembly from approved scene versions.
- The phase gate: storyboard approval as a production record (plan step 10).

# Validation

- `tests/test_assembly.py` (8 tests):
  - trims;
  - the plan uses the selected take;
  - an adopted assembly becomes v1 with its takes, and the next one is v2;
  - an existing version is refused;
  - a version file is never overwritten.
- Demo: two versions of SC-030, each with sound and picture, and notes for
  the J-cut and the short takes.
- SINGULAR 3-01, on a scratch **copy**:
  - 24 shots and 98.0 s assembled in 39 s, with sound and picture aligned
    (98.00 s and 98.02 s);
  - real frames checked, against SINGULAR's own montage at 94.85 s, which
    trims around speech;
  - from the UI: assemble, adopt from the tray, and the version list updated
    at once.
- Full suite: 360 tests OK.
