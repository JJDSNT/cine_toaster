---
id: CT-0030
title: Backlot — sets and locations as reusable entities
type: work
status: ready
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-09-29
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

# Validation

- Not started.
