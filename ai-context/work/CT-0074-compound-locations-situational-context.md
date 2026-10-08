# CT-0074 — Compound locations and situational context (Singular hospital)

Status: investigation; no Core schema or UX change approved. Date: 2026-10-08.

## Research question

How should Cine Toaster represent a physical place with multiple reusable environments, while keeping dramatic situation separate from set geometry? Validation case: the hospital in *Singular*, with Claire's room and the corridor (and potentially exterior).

## Verified implementation

- `ai-context/specs/SPEC-0010-locations-and-backlot.md`: each `locations/<id>/location.yaml` defines a reusable **set**. Scenes name one `location` and inherit room, marks, cameras and set pieces with scene-local changes. SPEC status accepted, implementation partial.
- `src/cine_toaster/locations.py::load_locations` scans **one directory level** (`locations/*/location.yaml`) and indexes locations by ID. `_location` returns id, label, room, marks, set_pieces, cameras, references, look and pin metadata. It has no first-class parent/child or environment relationship.
- `src/cine_toaster/locations.py::resolve` merges a scene's geography with **one** location's geometry. Its override notes describe moved marks, pieces and cameras. This is not hierarchical composition across multiple sets.
- `tests/test_locations.py` verifies shared set across scenes, scene-local overrides, location view appearances, unknown locations and backlot pin behavior. These tests do not establish compound locations.
- `docs/locations.md` says the Locations room shows scenes associated with a set and the scene room links related scenes.
- `ai-context/project-model.md` distinguishes canonical project content, scenes and runtime state; authored film decisions should remain portable.

## Domain distinctions

**Place / compound location:** hospital as a real or fictional site with shared identity, architectural language and geographical context.

**Set / environment:** room, corridor, exterior entrance; independently reusable geometry, cameras, plates and set pieces.

**Scene / situation:** who is present, dramatic objective, time, weather, lighting and local dressing or disruption. The same set may appear under different situations.

**Shot / take:** framing, movement, performance and produced audiovisual evidence.

A change to shared architectural identity should not automatically rewrite geometry or regenerate media. A change to a scene's lighting should not redefine the reusable corridor.

## Three possible representations to evaluate

### A. Flat sets + shared grouping metadata

Keep `HOSPITAL-ROOM` and `HOSPITAL-CORRIDOR` as existing independent locations, with optional grouping metadata linking both to `HOSPITAL`. This preserves the one-location-per-scene resolver and backlot layout. Shared creative decisions require explicit resolution rules; grouping alone is not inheritance.

### B. Parent place + child sets

Introduce `Place` and `Set` (or `Location` and `Environment`) with stable identities and explicit parent relationship. Child sets own geometry; parent may own references, architecture, mood direction and geography. Must define precise precedence, backlot pinning and partial override behavior. Higher migration and implementation cost.

### C. Hierarchical nested location files

Model nested environments inside a location folder or YAML. Can simplify authoring for a complex site but conflicts with the current flat directory loader, existing references and backlot semantics unless adapted.

**Initial recommendation for a prototype:** test A first as the smallest compatible approach; do not commit to grouping metadata or new schema until a data/API compatibility audit. Compare against B for genuine shared-identity requirements. Avoid assuming shared physical site implies shared 3D coordinate space.

## Hospital validation scenario

```text
Singular / Hospital (shared place identity)
  ├─ Claire's room (set: room geometry, medical props, camera positions)
  │    └─ Hospital bedroom scene (oxygen-support failure, Kael/Claire)
  ├─ Corridor (set: corridor geometry, ATLAS drone paths, camera positions)
  │    └─ Corridor scene (Kael's reaction and confrontation)
  └─ Exterior (candidate set, if needed)
       └─ Exit scene (lake, drones, Geneva)
```

This is a conceptual model, not a claim that the actual Singular project currently stores these relationships. Scene IDs should be read from the project rather than assumed.

### UX questions

- Selecting the hospital should reveal its environments and all scenes using them.
- Selecting Claire's room should show the shared hospital identity **and** the room's unique geometry, props and references.
- Switching to the corridor should retain the hospital context while replacing set- and scene-specific decisions.
- Selecting a scene should distinguish shared identity, set facts, scene situation and shot choices.
- A global change should display only verified affected set/scene references; no silent edits to scene overrides, takes or cuts.
- Film/sequence/scene/shot navigation and place/set/scene relations are **different axes**; do not conflate them.

## Next technical investigations

- [ ] Trace scene location parsing and `load_production` output; confirm assumptions about single set per scene.
- [ ] Inspect all location consumers (rendering, board, references, web endpoints, checks and backlot pinning) before proposing a schema.
- [ ] Test flat grouping metadata vs parent/child entity model using room/corridor/exterior example.
- [ ] Establish shared identity fields vs set geometry fields vs scene situation fields and explicit precedence.
- [ ] Verify deep links and selection retention when navigating hospital → room → scene → corridor.
- [ ] Compare contextual UX with actual users and record any ADR only after choosing a model.

## Guardrails

No new generic inheritance engine without evidence. No implicit cross-set geometry or camera transfer. No assumption that a visual moodboard feature already exists. No automatic regeneration or reinterpretation of previous media. Preserve existing location IDs and backlot pin semantics unless a migration is explicitly designed.

Related: CT-0071, CT-0072, CT-0073, SPEC-0010, docs/locations.md.

## Production evidence and UX priority (2026-10-08)

Singular's hospital room and corridor were spatially inconsistent until the hospital was modeled as one integrated Blender environment. Therefore flat location grouping is useful for navigation but insufficient to guarantee spatial coherence. Investigate a shared spatial reference with identifiable room/corridor regions and verified connections, while preserving scene-specific cinematic decisions. Blender should inform previs and storyboard, not control generative character animation. A full Geneva model is not required to validate the hospital case.

This remains a UX-led investigation: the filmmaker should navigate hospital, environments, scenes and shots, see what is spatially verified, and understand creative decisions without dealing with Blender internals by default. No new Core schema or engine choice is approved.
