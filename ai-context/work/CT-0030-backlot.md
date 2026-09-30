---
id: CT-0030
title: Backlot — sets and locations as reusable entities
type: work
status: doing
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-09-30
tags:
  - locations
  - geometry
  - entities
  - catalog
---

# What

A **location** entity: a set's plan (room, marks, tested camera positions),
reference images, and look. It is declared once and referenced by scenes, as
cast is (ADR 0012, SPEC-0003). A **backlot** is a library of locations shared
across productions and layered like the catalogs (built-in, external path,
production).

# Why

The user wants reusable sets and locations (2026-09-29). Today each scene
restates its geometry. SC-010 and SC-030 are the same listening station, and
their plans can drift apart exactly as the character descriptions did before
ADR 0012. ADR 0012 names locations as the next entity of the same shape.

# Design constraints

- **The production stays authoritative.** A production using a backlot set
  **pins a copy** into itself, with the source id and version. Updating it
  from the backlot is an explicit, recorded decision. Otherwise, editing the
  backlot would change a film without trace.
- A scene's geometry resolves from its location. A scene may add or override
  within it, for example a mark only that scene uses, and the check reports
  the difference.
- Reference images are executable, as for cast: the provider layer receives
  them when a shot is at that location.
- Location first, inside one production; the shared backlot second.

# To do

1. After plan step 9 (generation adapter), because references only matter once
   something consumes them. The in-production location entity may come earlier
   if SC-010 and SC-030 drift.
2. Specification: location schema, pinning and versioning, and override rules.
3. Blocking frame and previs read set pieces from the location. This closes
   one of the blocking frame's recorded limits (`CT-0025` To do item 5).

# Decisions

- Pin, never live-link.

# Done (2026-09-30)

- **SPEC-0010** (accepted, partial).
- **`locations.py`**:
  - `load_locations` reads `locations/<id>/location.yaml`: room, marks,
    cameras, references (with existence) and look;
  - `resolve` merges a scene's geography into its location's. Room and
    marks come from the location; cameras merge by id (an id alone adds the
    scene's `shots`, a position replaces). It reports moved marks and
    cameras;
  - backlot helpers: `backlot()` reads `CINE_TOASTER_BACKLOT`; `pin`
    copies a location with `pinned.json` (source, digest, date) and refuses
    to overwrite without `update`; `status` says whether the backlot moved
    on or the copy was edited here.
- **Scenes and the production.** A scene's `location` (production aliases
  allowed) resolves its geometry before parsing. Findings:
  `location_unknown` (error) and `location_override` (advice). The
  production payload gains `locations`, with the scenes shot in each.
- **Demo.** `locations/listening-station` holds SC-030's room, mark and
  three cameras. SC-030 keeps only its subjects, axis and camera coverage,
  and SC-010 is set in the same room.
  - The geometry, movement, blocking, cut, project, graph and brief tests
    (120) pass unchanged, so the resolved geometry is the same.
  - `toast check` is clean, with 2 scenes that have geometry.
- **Surfaces.**
  - `toast backlot list|pin|status`;
  - the scene room's "Set in …" line;
  - the assistant's digest and overview.
- Docs are in `docs/locations.md`.

# Validation

- `tests/test_locations.py` (4 tests):
  - shared plan and appearances;
  - override advice;
  - an unknown location;
  - pin, status, the backlot moving on without changing the film, refusal
    to overwrite, and an explicit update.

# Remaining

- ~~Set pieces drawn in the blocking frame~~ done 2026-09-30 (CT-0025).
- ~~Plates as generation sources~~ done 2026-09-30. `locations.plate(root,
  location, camera)` reads the location's `references` (kind `plate`,
  `camera`); `pictures.source_picture` resolves `location:<camera>` and bare
  `location` (the shot's camera), so `plan_picture`, the Pictures panel,
  workflows and `set_reference` all accept it. `toast check` reports
  `plate_missing` (warning) before any paid edit. The graph carries each
  scene's `location` and existing `plates`; the canvas reference editor
  offers them. Tests: 2 in `test_pictures` (both spellings, the size taken
  from the plate; a missing plate found by the check and refused by the
  plan). Not done: no demo plate ships (a drawn stand-in would be edited as
  if it were a photograph).
- A Locations room in the control room.
