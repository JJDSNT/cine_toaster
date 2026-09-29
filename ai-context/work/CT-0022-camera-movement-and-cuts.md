---
id: CT-0022
title: Camera movement, cuts between clips, and an Arcads-style graph
type: work
status: ready
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - camera
  - editing
  - transitions
  - interface
  - evaluation
---

# What

Screen external references for the two problems that hurt generated productions
most: camera movement and cuts between clips. Propose how both become project
records. Evaluate an Arcads-style graph as a view over those records. The
outcome is a spike plan, not a schema change.

# Why

Generated clips fail at the cut more often than inside the shot. A camera move
written as prompt prose can drift between regenerations. An adjacent pair of
shots can be coherent on its own and still not cut together, because the exit
state of one shot does not meet the entry state of the next. ADR 0007 already
makes camera positions project state. Movement and the cut itself are not.

# Done

- Recorded every reference, its licence, and whether its code may be reused in
  [`references.md`](../references.md).
- Ranked the repositories against camera movement, cuts, and the graph view:
  React Flow is the graph base. SceneFlow has state chaining for cuts. AI Video
  Production Editor has blockout-rendered camera moves, but only as ideas under
  GPL. CineGen has bridge generation between clips, also only as ideas because
  it has no licence.
- Confirmed that `taruma/SceneFlow` is the SceneFlow the user follows.
  `sceneflow.camera` is an unrelated product. Read Auteur Script v0.3.0 and the
  SceneFlow v2.3.0–v2.5.0 release notes: Timeline Anatomy and the BRIEF State
  Engine.

# To do

1. Draft a camera-move vocabulary, informed by the 46 moves in
   aicameramovements.com's taxonomy but written here. Attach a move to
   `[[geometry.cameras]]` as start pose → end pose, speed, and end state. Add a
   `toast check` rule that flags a move crossing the line of action.
2. Draft a `cut` record between adjacent shots with these fields: exit state,
   entry state, cut type (hard, match, action, J/L), frame chaining
   (last→first), optional bridge generation, and an optional catalog transition
   with a required `reason` (SPEC-0004). Decide whether it belongs in
   SPEC-0004 or a new specification.
3. Spike: read SceneFlow's `briefAnalysis.ts` and the Timeline Anatomy view.
   Test whether STAGING/EXECUTION and `STATE IN`/`STATE OUT` map onto our
   scene, shot, and geometry records. Test whether a prompt in Auteur Script
   form can be *derived* from those records, instead of authored by hand.
4. Compare two cut strategies on one real sequence:
   - **(a)** separate clips joined by chained frames;
   - **(b)** Auteur Script-style multi-setup generation, where one generation
     contains several `[CAM n]` setups and the model makes the cuts.

   Record for each strategy: continuity, screen direction, control over
   individual shots, and the cost of regenerating one shot.
5. Spike: build a React Flow prototype on a real sequence. Nodes are shots with
   the selected take, and edges are cuts. Edge edits call the shared commands.
   Compare it with the Cut and Transitions rooms (`CT-0020`).
6. Later, when a generation adapter exists, pass the declared move and chained
   frames to the provider. Measure drift against the declared move.

# Decisions

- The graph interaction model is **Arcads-style**: cards are production objects
  such as shots, takes, cast, and cuts. Users do not wire model parameters
  ComfyUI-style. This replaces the ComfyUI analogy recorded in `CT-0020`.
- The graph is a projection of project records. It is never its own file
  format.
- Copyleft and unlicensed references are studied and reimplemented, never
  copied (ADR 0011).

# Validation

- Documentation only. The repositories were inspected through GitHub metadata
  and READMEs on 2026-09-29. None was cloned or run.
