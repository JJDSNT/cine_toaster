---
id: CT-0025
title: Storyboard fidelity levels — computed blocking frame, sketch, master image
type: work
status: doing
owner: development agent
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - storyboard
  - geometry
  - generation
  - interface
---

# What

Give a shot's pictures explicit fidelity levels, each a node in the shot's
chain with lineage to the next:

```
[blocking frame] → [sketch (optional)] → [master image] → [video]
 computed from       drawn, or generated    photoreal, with     start/end
 geometry            as line art            cast and look       frames
```

The first deliverable is the **blocking frame**. It is computed from scene
geometry with no model call, so it needs no provider and can be built now.

# Why

The user noticed that some storyboard tools use sketches while Cine Toaster's
productions go straight to photoreal images. Sketches exist for a reason:

- they settle composition, meaning camera, sides, and what is in frame,
  without committing to a face, a light, or wardrobe;
- they are cheap to throw away;
- they do not need cast consistency.

A photoreal image is still required later: it is what an image-to-video model
takes as a start or end frame. A sketch used directly would pass its line
style into the video.

Cine Toaster already holds what a sketch conveys:

- the camera pose and lens;
- where every subject stands, and since SPEC-0005, where they walk;
- the screen side of each subject.

A view rendered from that data costs nothing, updates the moment a mark
moves, and cannot contradict `toast check`, because it comes from the same
numbers. Used as a composition input for the master image (depth, silhouette,
or ControlNet-style guidance through the provider adapter), it carries the
axis, the screen sides, and the shot size into generation. Those would
otherwise depend on prompt wording.

# Done

- Recorded the idea and the reasoning (2026-09-29).
- Corrected a premise: Cine Toaster itself generates no images yet. The
  photoreal stills come from the production's own pipeline and are
  discovered by the runtime. The levels can be defined before the generation
  adapter exists.

# To do

1. ~~**Blocking frame renderer.**~~ Done (plan step 3). The original step read:
   **Blocking frame renderer.** For a shot's start and end state
   (`ShotMotion`), draw the camera's view: the frame at the aspect ratio,
   subjects as silhouettes sized by distance and lens, placed by screen
   angle, and heights used when declared. Show it beside the blockout. Add a
   golden test on SC-030.
2. ~~Decide the storage class~~ Decided: **derived, never stored**. It is
   drawn on every request (`/api/blocking-frame`, `toast frame`) and nothing
   caches it yet, because drawing costs less than a millisecond.
3. Define the level on a picture: `blocking`, `sketch`, or `master`, with
   lineage (`from`) to the level below. This belongs with SPEC-0003 lineage.
4. When the generation adapter exists, add a first step that renders a master
   image from the blocking frame plus cast and look references, and record
   the adherence of each result against the frame.

5. **Revisit the blocking frame's limits** (recorded 2026-09-29 at the
   user's request). Most need schema fields, so they wait for a real shot
   that the frame gets wrong:
   - every subject is drawn as a person, including the speaker stack. A
     subject `kind` (person, object) and a size would fix it;
   - silhouettes always face the camera. Subjects have no facing direction,
     although eyelines imply one;
   - a subject's height is fixed for the scene, so standing up or sitting down
     inside a shot cannot be shown;
   - the set is an empty box: no furniture, doors, windows or occluders, so
     nothing can hide a subject;
   - only the start and end are drawn, not the move between them;
   - camera: no roll or dutch angle, no lens distortion, no depth of field,
     and a 16:9 full-frame sensor is assumed; there is no per-production
     aspect ratio or sensor;
   - heights default to 1.5 m for the camera and 1.6 m for eyes when the plan
     omits them. The caption says "assumed", but no check reports it.

# Decisions

- The blocking frame is computed, not generated. It is the cheapest level,
  and the only one that is correct by construction.
- Sketches remain optional. Some productions will go straight from the
  blocking frame to a master image.

# Implementation (step 1)

- `src/cine_toaster/blocking.py`:
  - a pinhole camera on a full-frame 16:9 sensor, at the shot's start or end
    pose (SPEC-0005);
  - screen right uses the plan convention of `screen_side`, so sides cannot
    disagree with the checks;
  - the camera tilts toward the eye height of the subject it follows, and is
    otherwise level;
  - defaults when heights are missing: camera 1.5 m, eyes 1.6 m. The caption
    says "assumed".
  - subjects are drawn as silhouettes, far to near, with labels; those out of
    frame or behind the camera are named at the matching edge;
  - the room's edges, the axis and the marks are clipped at the near plane;
  - output is facts (`public_frame`) plus an SVG drawing (`render_svg`).
- `GET /api/blocking-frame?scene=&shot=&at=start|end[&format=json]`.
- `toast frame <project> <scene> <shot> [--at] [--output] [--json]`.
- In the scene room, selecting a shot chip in the blockout shows its start
  and end frames (a single frame when nothing moves).

Known limits (to revisit; listed in To do item 5).

# Validation

- `tests/test_blocking.py` (9 tests):
  - golden values on SC-030, measured by hand: P2 starts with the stack at
    x ≈ −0.99 and Mara off right, and ends with Mara centred at 1.8 m; in P1
    Mara is behind the camera; in P3 the stack is off left;
  - an agreement test: every framed subject in every shot is inside the frame,
    on the same side;
  - the tilt, the SVG content, and the HTTP endpoint.
- SVGs rasterised with rsvg-convert and inspected. The head and shoulder gap
  was corrected after the first look.
- Headless screenshot of the SC-030 blockout with P2 selected.
- Full suite: 271 tests OK.
