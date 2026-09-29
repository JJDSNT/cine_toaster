---
id: CT-0025
title: Storyboard fidelity levels — computed blocking frame, sketch, master image
type: work
status: ready
owner: unassigned
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

1. **Blocking frame renderer.** For a shot's start and end state
   (`ShotMotion`), draw the camera's view: the frame at the aspect ratio,
   subjects as silhouettes sized by distance and lens, placed by screen
   angle, and heights used when declared. Show it beside the blockout. Add a
   golden test on SC-030.
2. Decide the storage class of a blocking frame. The proposal is that it is
   **derived, never stored**: regenerate it on demand, and keep it at most in
   the disposable cache.
3. Define the level on a picture: `blocking`, `sketch`, or `master`, with
   lineage (`from`) to the level below. This belongs with SPEC-0003 lineage.
4. When the generation adapter exists, add a first step that renders a master
   image from the blocking frame plus cast and look references, and record
   the adherence of each result against the frame.

# Decisions

- The blocking frame is computed, not generated. It is the cheapest level,
  and the only one that is correct by construction.
- Sketches remain optional. Some productions will go straight from the
  blocking frame to a master image.

# Validation

- Design only. No code yet.
