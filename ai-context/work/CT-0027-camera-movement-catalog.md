---
id: CT-0027
title: A camera-movement catalog, shaped like the transition catalog
type: work
status: done
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-09-30
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

# Done (2026-09-30)

- **`camera_moves.py`** and **32 built-in moves** in
  `camera_move_assets/<id>/move.toml`, in eight categories:
  - static, pan/tilt, zoom/lens, dolly/track, physical, drone/crane,
    human, specials.
  - Each move carries `says`, `use_when`, `avoid_when`, `energy`, an
    `[implies]` table (kind, direction, rig, speed, secondary) in SPEC-0005's
    vocabulary, and a `[prompt]` text.
- **Layers**: built in, then `CINE_TOASTER_CAMERA_MOVES_PATH`, then the
  production's `camera_moves/`. A later layer replaces by id.
- **Shots.** `move: {id: …}` is expanded when a scene loads
  (`project._expand_camera_moves`), so SPEC-0005's derivation and
  `move_kind_mismatch` check it unchanged. An unknown id is reported as
  `move_unknown` (error).
- **Generation.** `generation._camera` falls back to the move's words when
  the shot has no camera text.
- **Surfaces**: `toast moves [project] [--json]`, `/api/camera-moves`, the
  control room's **Camera moves** room, and the assistant's `moves` room.
- **The user's pointer to aicameramovements.com (2026-09-30).** Its 46
  names were used as a checklist. That added whip pans, crash zooms,
  walk-and-talk, side tracking, pedestal down, push past, drone moves,
  handheld, body-mounted, first person and time-lapse. None of its text is
  used, since it states no licence.

# Decisions

- SPEC-0005's derivation stays the check. The catalog names moves and says
  what they imply; it does not replace the geometry.
- A production may add or replace moves (to-do item 4), as it can for
  transitions.

# Validation

- `tests/test_camera_moves.py` (4 tests):
  - every built-in move is complete and speaks SPEC-0005's vocabulary;
  - a production can replace a move;
  - a named move takes its geometry from the catalog and its words reach
    the prompt;
  - an unknown move is reported.
- Headless screenshot of the room: 32 cards, and the navigation count.

# Remaining

- Looping previews of each move rendered from the blockout. The light previs
  can animate a shot, but not yet a move in the abstract.
