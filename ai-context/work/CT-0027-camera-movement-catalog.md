---
id: CT-0027
title: A camera-movement catalog, shaped like the transition catalog
type: work
status: ready
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - camera
  - catalog
  - knowledge
  - future
---

# What

Build a shared, layered catalog of camera moves (built-in, external path,
production), in the same shape as the transition catalog (`docs/transition-library.md`):

- one manifest per move, with an id, a name, and a category (pan/tilt,
  zoom/lens, dolly/track, physical, handheld, drone/crane, specials);
- editorial guidance, with `use_when` and `avoid_when`, energy, and what the
  move says;
- the **geometry it implies**: which derived kind it must produce under
  SPEC-0005 (for example, `dolly_in` means the camera approaches its target
  with the lens held), so `toast check` can verify a declared move against the
  poses;
- an optional looping preview, rendered from the blockout or the blocking
  frame, never taken from a third party;
- the prompt fragment for generation adapters, authored here.

# Why

The user asked to record it for later (2026-09-29). Camera movement is one of
the two main production pains (`CT-0022`). SPEC-0005 already derives the kind of
a move from its start and end poses, but its vocabulary (`move.kind`, `speed`,
`rig`) is a closed list in code, with no guidance. That is where transitions
were before their catalog.

# Done

- Recorded the request.

# To do

1. After the blocking frame (plan step 3), because a preview of a move is a
   blocking frame animated from its start pose to its end pose.
2. Use aicameramovements.com's 46-move taxonomy as a checklist only. It states
   no licence, so its text and examples are not copied (`references.md`).
3. Move SPEC-0005's `move.kind` vocabulary into the catalog and keep the
   derivation as the check.
4. Decide whether a production may add its own moves, as it can add its own
   transitions.

# Decisions

- None yet.

# Validation

- Not started.
