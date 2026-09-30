---
id: SPEC-0010
title: Locations and the backlot — a set declared once, pinned from a shared library
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-09-30
updated_at: 2026-09-30
tags:
  - locations
  - geometry
  - entities
---

# Goal

A set is declared once and reused by the scenes shot in it (ADR 0012, CT-0030).
Before this, each scene restated its plan, and two scenes in the same room
could drift apart, as character descriptions did before cast sheets. A
backlot shares sets across productions without letting a shared file change a
film behind its back.

# The location

`locations/<id>/location.yaml`:

```yaml
id: LISTENING-STATION
label: The listening station
description: A cramped radio room, console on the east wall, the speaker stack opposite.
room: [6.0, 4.5, 3.2]              # metres, as in a scene's geography
marks:
  - {id: HALFWAY, x: 2.6, y: 2.3, label: Two steps short of the stack}
cameras:                           # positions tested on this set
  - {id: CAM-A, x: 3.4, y: 0.9, height: 1.05, target: [4.1, 2.2], lens_mm: 50, label: Console side, on the chair}
references:                        # plates, stills: what the set looks like
  - {path: plates/cam-a.png, kind: plate, camera: CAM-A}
look: NIGHT_INTERIOR
```

Everything but `id` is optional.

# A scene in a location

A scene says `location: LISTENING-STATION`. Its geometry resolves as:

- the **room** is the location's, unless the scene gives its own;
- **marks** are the location's, plus the scene's own. A scene mark with a
  location mark's id replaces it;
- **cameras** are the location's. A scene camera entry with a location
  camera's id and no position takes the location's camera and adds the
  scene's `shots` (and label). With a position, it replaces the location's
  camera;
- **subjects** and the **axis** are the scene's own: who is in the room is a
  scene matter.

**Checks**

| Code | Severity | Meaning |
| --- | --- | --- |
| `location_unknown` | error | The scene names a location the production does not have. |
| `location_override` | advice | The scene redefines one of the location's marks or cameras with a different position. Intended or drift: the check shows the difference. |

# The backlot

A backlot is a folder of locations with the same layout, shared across
productions. It is found at the paths in `CINE_TOASTER_BACKLOT`.

- **Pin.** `toast backlot pin <project> <id>` copies the location into the
  production's `locations/<id>/`. It records `pinned.json`: the source
  folder, the digest of its files, and the date. The production owns the
  copy.
- **Status.** `toast backlot status <project>` compares the backlot's
  current digest with the pinned one. It reports whether the backlot moved
  on, and whether the copy was edited in the production.
- **Update** is explicit: `toast backlot pin … --update`. Editing the backlot
  never changes a film by itself.

# Out of scope here

- Set pieces (furniture, doors) drawn in the blocking frame and previs.
  This is CT-0025's recorded limit, which the location will carry.
- Plates as generation sources (`derive: {from: location:CAM-A}`).
- A shared backlot shipped with the application.
