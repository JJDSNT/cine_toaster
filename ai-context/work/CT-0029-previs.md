---
id: CT-0029
title: Previs — the shot in motion, from the same records as the blocking frame
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-10-03
tags:
  - previs
  - camera
  - storyboard
  - generation
---

# What

Show each shot as motion over its duration, computed from the records that
already exist: camera pose and lens, start and end poses, marks, subject paths,
speed, and duration (SPEC-0005). Previs is a storyboard fidelity level
(`CT-0025`), sitting between the blocking frame and the master image, with
lineage to both.

# Why

Camera movement is the main production pain (`CT-0022`). The blocking frame
shows only the start and end of a shot. The move between them is still a
claim that nobody sees until a model generates it, which is the most expensive
point to discover that it is wrong. Agreed with the user on 2026-09-29.

# Stages

1. **Light previs, in the app** (plan step 4b). The blocking frame animated
   across the shot's duration: camera and subjects interpolated, speed
   respected, and the move's derived kind shown. It reuses `blocking.py`, and
   it is also the preview for the camera-movement catalog (`CT-0027`).
2. **3D previs** (after plan step 9). Export the scene (glTF or USD, or a
   Blender script) and render an animatic per shot in Blender, the tool
   `toast doctor` already detects. The result is a take at the `previs` level.
3. **Previs as the motion reference for generation** (after plan step 9). The
   animatic or its depth pass goes to the provider adapter as a motion or
   structure reference, so the camera no longer depends on prompt wording.
   Measure adherence against the previs. AI Video Production Editor
   (`references.md`, GPL, ideas only) does this.

# Decisions

- Previs is derived from records. Stage 1 is never stored. Stage 2 is a take
  with lineage, because rendering it costs something.
- Paths interpolate between declared positions only. Nothing is inferred from
  action lines.

# Stage 1 — done (plan step 4b, 2026-09-29)

- `blocking.state_at(motion, t)` interpolates only what the records declare:
  - the camera travels straight, except an `arc`, which turns around its end
    target;
  - lens (zoom), target and height are mixed;
  - subjects walk straight from their start to their end position.

  Easing follows the declared speed: ease in and out by default, even pace
  for `fast`, whip and settle for `snap`. A move is assumed to span the whole
  shot.
- `blocking_frame(..., at=t)` accepts a time from 0 to 1.
  `previs(scene, shot)` samples the shot at 12 frames per second.
- `GET /api/previs?scene=&shot=`, `toast frame … --at 0.5`, and
  `toast previs <project> <scene> <shot> --output p.mp4` (FFmpeg with
  librsvg).
- Scene room: a shot that moves shows a previs player (play and scrub, at the
  shot's real length) above its start and end frames.

Known limits:

- the move's timing within the shot is not a record; the move always spans
  the whole shot;
- paths are straight lines between declared positions, with no waypoints;
- the blocking frame's own limits apply (`CT-0025` To do item 5).

# To do

- **Revisit the light previs limits** (recorded 2026-09-29 at the user's
  request), each when a real shot needs it:
  - timing of a move within a shot: holds before or after it, and a move over
    part of the shot (`starts_at` and `ends_at`);
  - paths with waypoints and curves, for subjects and for the camera (only
    arcs curve today);
  - separate timing for a subject's walk and the camera move; today both span
    the whole shot;
  - acceleration beyond the four speed words, such as a declared ease or a
    speed in metres per second;
  - tilt and roll moves (tilt is declared-only in SPEC-0005), and handheld
    shake as a rig trait;
  - playback of a whole scene or sequence across cuts, not one shot at a
    time;
  - sound: dialogue and effects placed on the animatic's timeline;
  - the blocking frame's own limits (`CT-0025` To do item 5).
- Stages 2 and 3 after plan step 9.
- A `move` timing record (`starts_at`, `ends_at` within the shot) when a real
  shot needs a hold before or after the move.

# Validation

- `tests/test_blocking.py` `PrevisTests` (7 tests):
  - the animatic's ends equal the start and end frames;
  - Mara walks into frame on SC-030 P2 and stays in;
  - a hand-built dolly travels straight and eases;
  - an arc keeps its distance from its subject;
  - a zoom mixes the lens;
  - the sampling covers the shot, and out-of-range times are refused.
- `toast previs` rendered SC-030 P2 to a 9 s mp4. Frames at 0, 50, 74 and
  99 % were inspected.
- Headless screenshot of the player scrubbed to 60 % (5.4 of 9 s).
- Full suite: 292 tests OK.

# Closed (2026-10-03, close-out pass)

Light previs and the 3D animatic (CT-0049) are delivered.

What remains moved to the backlog (`development/roadmap.md` § Backlog): The previs limits listed above: move timing within a shot, waypoints, separate walk and camera timing, easing, tilt/roll/handheld, scene playback, sound on the animatic.
