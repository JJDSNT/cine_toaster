---
id: CT-0029
title: Previs — the shot in motion, from the same records as the blocking frame
type: work
status: ready
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-09-29
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

# To do

- Stage 1 after the brief builder (plan step 4).

# Validation

- Not started.
