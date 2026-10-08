# CT-0074 addendum — Location consumer trace and spatial continuity

Date: 2026-10-08. Research only; no schema change.

## Verified consumer trace

1. `locations.py::load_locations` discovers `locations/*/location.yaml`, one flat level; no parent/environment identifier in the returned location.
2. `project.py` scene loader (around lines 639–670) reads one scene `location` ID, resolves its geography with exactly one location, reports `location_unknown` / `location_override`, and checks location plates using that same ID.
3. `project.py::_production_locations` computes `appearances` by equality between the scene location ID and location ID; no place-level grouping.
4. `project.py::load_production` exposes the resulting `locations` map alongside `cast`, `style`, and `look`.
5. `web.py` provides `GET /api/locations` from `locations_view`, including a parsed plan, appearances and backlot status. `GET /api/boards` is scene-based, not a place-level multi-environment view.
6. `locations.py::resolve` merges room, marks, pieces and cameras; scene-local differences are advice. No cross-set coordinate transform or doorway/topology relation is established.
7. `tests/test_locations.py` validates two scenes using one set and local camera/piece overrides. It does not test several sets belonging to one compound place.

## Dependency matrix

| Change | Confirmed current consumer | Potential effect | Evidence needed before claiming impact |
| --- | --- | --- | --- |
| Scene's `location` ID | scene loader, plate validation, appearances | Different set plan, plate source, location room links | actual scene bindings and references |
| Location room/camera/marks | scene geography resolver | scenes directly naming the set can resolve differently | compare before/after effective geography |
| Location plates | shot image derivation/plate check | new master image reference may differ | trace the shot's actual `derive` source |
| Backlot source | pin/status | source copy may differ | pinned digest and explicit update |
| Shared hospital identity (not modeled yet) | none established | navigation grouping only if metadata added | proposal and consumer compatibility audit |
| Hospital-room to corridor passage | narrative sequence/scene ordering exists | cinematic continuity may need checks | authored adjacency and/or edit references |
| Spatial doorway connection | not modeled by current location resolver | could support cross-set 3D previs | explicit coordinate transforms and topology |

## Three different continuities

- **Spatial**: rooms, adjacency, doors, common coordinates. Not implied by a shared building label. Two sets can have independent local coordinates.
- **Narrative**: ordered scenes, character movement, time and story events. Scene/sequence ordering is already represented.
- **Cinematic**: axis, screen direction, matching action, transitions, sound bridges and shot joins. May create an apparently continuous passage even with disconnected physical set models.

The hospital case should validate all three separately. Do not assume the room and corridor share a 3D model or that a transition automatically proves physical adjacency.

## Minimal compatibility-first hypothesis

Preserve independent set IDs such as `HOSPITAL-ROOM` and `HOSPITAL-CORRIDOR` as current `location` references. Explore a **separate optional place/group relation** for browsing and shared creative identity, without modifying `locations.resolve`, `plate`, `appearances` or existing backlot pin semantics. A grouping field alone does not imply inherited geometry or visual style.

A stronger parent-child model is justified only if verified requirements demand shared properties or physical topology. If adopted, specify override precedence, stable IDs, migrations, API changes, backlot pinning and existing consumer behavior in an ADR.

## UX validation tasks

1. Open hospital → show room/corridor/exterior and scenes grouped by set.
2. Open Claire's room scene → show hospital identity, room plan, dramatic situation and applicable creative decisions distinctly.
3. Navigate to corridor scene → preserve hospital identity but replace local geometry and dramatic context.
4. Compare cross-scene continuity: what is authored, what is computed, what remains unknown.
5. Follow room → corridor passage into storyboard and edit; do not display a verified spatial connection unless explicitly declared.

## Next checks

- Inspect `board` and `jobs` call paths for geometry and plate consumers.
- Audit scene-to-scene continuity and editing references; establish where spatial passage might be declared without inventing it.
- Prototype grouping-only vs explicit place entity, test against an actual Singular project fixture.
- Update SPEC-0010 and APIs only after a chosen compatibility design.

## Correction from Singular production evidence (2026-10-08)

The hospital room and corridor were spatially inconsistent until an integrated hospital was modeled in Blender. Flat grouping can aid browsing but cannot validate geometric connections. Research a shared spatial model, identified environments and verifiable links in addition to existing single-set consumers. Keep the UX question central: navigate from scene to place, adjacent environments and boards; distinguish proven spatial continuity from assumed proximity. Blender is a spatial/previs reference, not a requirement to animate characters or to model all Geneva. No schema change decided.
