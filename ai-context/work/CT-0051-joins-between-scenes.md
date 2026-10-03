---
id: CT-0051
title: Joins between scenes in a sequence
type: work
status: review
owner: unassigned
created_at: 2026-10-03
updated_at: 2026-10-03
tags:
  - sequence
  - cut
  - transitions
---

# What

A scene declares how it is entered from the previous scene of its sequence
(`enter: {type, transition, reason}`), and the sequence assembly renders it.

# Why

After CT-0050 the cut inside a scene was complete, but a sequence still
glued its scenes straight. SPEC-0007 left cuts between scenes to the
sequence. SINGULAR fades each scene to black at its own end, a habit
better held as a decision on the join.

# Done

- `project._scene_enter`: parses `enter` and checks the type, the
  transition and its reason (`cut_type_unknown`, `transition_unknown`,
  `transition_reason_missing`); `scene["enter"]`.
- `jobs._sequence_plan`: each scene after the first gets its join through
  `assembly._resolve_join`; `enter` on the first scene is said. J/L joins
  between versions have no handle and are said straight (the note names a
  version, not a take).
- The Sequences room shows "↳ enters by …" between scenes (checked
  headless on a demo copy).
- SPEC-0007 amendment.

## Sound over several scenes (2026-10-03)

- A sequence in `project.yaml` takes `ambience` and `music` like a scene,
  `from`/`to`/`until` naming its scenes (`project._sequence_beds`);
  problems go to the production's attention list and the Sequences room.
- `_sequence_plan` places them with `sounds.place` over the versions (after
  the joins); the sequence render mixes them as a scene's cues.
- Ducking across scenes: the scene assembly job writes
  `<version>.mp4.speech.json` (the cut's speech on its timeline,
  `Plan.speech`); a sequence's segment reads it (`Segment.speech_spans`).
  A version made before this has no sidecar, and its lines are not ducked.
- The sequence version's summary says what was laid.

# Decisions

- Declared in `scene.yaml`, not in `project.yaml`'s sequence entry: a scene
  belongs to one sequence, and the incoming side already holds a shot's
  cut. The sequence order stays in `project.yaml`.
- No runtime decision command yet (`set_cut` covers shots only).

# Validation

- `tests/test_joins.py` `SceneJoinTests`: two recorded scene versions,
  SC-030 entered through a 0.4 s dip-to-black, the sequence job succeeds
  and is 0.4 s shorter than its scenes; an unknown type and transition are
  reported; music over both scenes (0.5 s into SC-010, 3.5 s long) ducked
  more than 7 dB under the line SC-030's speech sidecar reports; the scene
  job writes its sidecar (`tests/test_sounds.py`).

# To do

- A decision command for a scene's `enter` (canvas edge between scenes).
- Opening and closing a sequence (from and to black) without a scene
  before or after.
- A J/L between scenes from the next scene's takes (versions have no
  handles).
