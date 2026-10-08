# CT-0072 — Contextual creative decisions and navigation research

Status: research, not approved redesign. Date: 2026-10-08.

## Core question

How should Cine Toaster make **film-wide creative decisions and their scene/shot-specific applications** visible, navigable and understandable across Screenplay & Storyboard, Production, and Editing & Post-production, without overwhelming the user?

## Findings from existing repository

- `src/cine_toaster/web_assets/index.html` groups a persistent left sidebar by Writing, Production and Reference. It includes separate Cast, Locations, Styles, Emotions and Sound destinations. This is **feature-oriented navigation**; contextual relations are not evident in the sidebar itself.
- `docs/styles.md` already defines style axes (technique, direction, format), per-axis cascading and scene-level changes. It reports the level responsible for a style decision, and treats departures as advice rather than prohibitions.
- `docs/locations.md` defines reusable location geometry, cameras, marks and plates. Scenes reference locations and may override parts of them. The location room links scenes that use a set; checks distinguish missing locations and local overrides.
- `docs/emotions.md` describes shot-level performance choices, per-character emotion/intensity/arc/reason, distinct from film-wide visual style.
- `docs/research/moodboard-visual-style-investigation.md` is exploratory only. It distinguishes visual mood/style from emotional performance; it does **not** establish an implemented first-class moodboard.
- `src/cine_toaster/project.py` imports cast, looks, continuity and project-state logic. This indicates existing concepts to inventory precisely, not proof of a single unified creative decision graph.

## Distinctions to preserve

**Resource** (a location, cast asset, look preset) is not the same as **decision** (use it for a film/scene/shot). **Creative intent** is not the same as **execution state**. **Inherited setting**, **local override**, **intentional departure**, **unconfirmed inference** and **detected inconsistency** must be visibly distinguishable.

Moodboard (visual palette, texture, lighting) is not character emotion/performance. Do not invent a film-wide mood field where only a catalog or research document exists.

## Candidate conceptual model

A read-only **Creative Context projection** can connect existing records:
- Film-level: project style axes, casting/character identity, location catalog, reusable looks and declared aesthetic direction.
- Sequence/scene-level: dramatic beat, participating cast variants, chosen location, time/weather, continuity, local style and look overrides.
- Shot-level: camera, reference, performance emotion, take selection and technical/generative choices.
- Editorial level: actual selected take and assembly references, cut/transition decisions and versions.

Each surfaced relation should answer: **what applies here, where did it come from, what overrides it, what evidence supports it, and what other objects reference it?** Only show impact after inspecting actual references; unknown is not stale.

This is not a mandate for a new graph database or a new source of truth.

## Navigation alternatives to test

| Variant | Left side | Context presentation | Risk |
| --- | --- | --- | --- |
| A — Feature menu + contextual inspector | Current-style destinations | Relevant creative decisions in inspector | Context may remain secondary or hidden |
| B — Task/workspace navigation + context rail | Three workspace destinations and scene explorer | Collapsible film → scene → shot context | Too many simultaneous columns |
| C — Object-centered navigation | Current scene/shot and related creative entities | Links to casting, location, look, mood and their origins | Users may struggle to discover unrelated functions |
| D — Hybrid | Compact workspace navigation + searchable global tools | Contextual relations on selection, optional expanded impact view | Complex behavior unless consistent and predictable |

**Initial hypothesis:** compare A against D before choosing; no new permanent pane should be assumed.

## Cross-workspace questions

- In Screenplay/Storyboard: which global casting, location, visual and dramatic decisions govern this scene? Which local departures are intentional?
- In Production: which of these decisions actually condition the chosen shot/take, and which remain references only?
- In Editing/Post: which decisions are visible in the assembled result, and what is affected if an upstream choice changes?
- Across all: can a user follow a decision to its uses and return to the original task without losing scene/shot context?

## Decision-impact examples to verify

1. Film style changes: determine which scenes override the relevant axis; never imply every scene is affected.
2. Location geometry changes: inspect scene references and pinned backlot revisions; avoid silently replacing local modifications.
3. Cast variant changes: inspect appearances and take provenance; do not assume existing renders are automatically updated.
4. Scene mood changes: distinguish a future moodboard feature from currently implemented style/look settings.
5. Shot emotion changes: distinguish declared performance direction from what a rendered video actually conveys.

## Evidence and UX research plan

- [ ] Inventory actual data fields and resolver semantics for cast, looks, styles, locations, continuity and emotion; map authoritative source and effective value at each level.
- [ ] Trace current left-sidebar navigation and existing scene/cast/location cross-links in live UI code.
- [ ] Produce a **decision → origin → scope → override → dependent object → evidence** matrix, distinguishing implemented, derived and missing links.
- [ ] Study object-centered navigation, progressive disclosure, information scent and provenance patterns in creative tools; cite verified primary sources.
- [ ] Prototype variants A and D at laptop and desktop sizes; compare task success, wrong-context actions, navigation steps, visual search and perceived workload.
- [ ] Test film-wide style change, scene location override, shot performance decision and editorial trace-back.
- [ ] Document validated navigation rules and ADRs before changing the sidebar.

## Guardrails

Do not conflate three workspaces with three context levels. Do not convert every resource into a permanent sidebar item. Do not force all creative decisions into a rigid inheritance hierarchy. Do not claim a dependency without traceable Core evidence. Preserve author control and explicit exceptions.

Related: CT-0066, CT-0067, CT-0068, CT-0069, CT-0070, CT-0071, and `docs/research/moodboard-visual-style-investigation.md`.
