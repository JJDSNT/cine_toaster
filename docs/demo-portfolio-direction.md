# Demo portfolio and integrated reel — creative direction

Status: **proposed direction, agreed in discussion 2026-10-17**. This is a living creative brief, **not** a production-ready screenplay, feature-completion claim, or authorization to spend on generation.

## Principle

Produce **up to five standalone cinematic demos**, each a complete work in its own right, followed by **one integrated cinematic demo reel** built from their approved footage and assets. Fewer demos are acceptable if the creative and validation goals are met. **Singular is a real film and validation case, not a demo.**

The demos are not feature-checklist videos. They should be artistically compelling, use Cine Toaster's real production pipeline (intention → screenplay → breakdown/storyboard → production/review → finishing), and supply reusable shots, characters, environments or effects to the reel. The reel itself tells a continuous story and reveals the product through cinematic results, not a tutorial.

## Proposed five productions

1. **Historical cinema** — work with surviving archival footage, including a cameraman filming high on a building under construction. Preservation/provenance, restoration *within* the film, and historical-to-modern compositing are opportunities. The cameraman opens and closes the reel.
2. **Something New Is Coming** — standalone animated narrative in which a character and the visual language evolve *together* across animation eras. The character reaches a mountaintop; a possible 3D Gaussian Splatting camera orbit gives volume. A fall into a new world is a proposed reel bridge, not necessarily a scene in the standalone short.
3. **3D world / Juggler homage** — a self-contained 3D production inspired by the Amiga Juggler. The character from demo 2 can enter its world in the reel. Reflective spheres may display footage from other demos using Cine Toaster's video-on-sphere warp. Evolution from early computer graphics to contemporary 3D is a promising direction, not a locked screenplay.
4. **Music video** — an independent music-driven production, potentially featuring a character or element from the modern 3D world. Explore performance, rhythm, beats, editing, retiming, effects, audio and finishing. Musical concept, cast and track remain open.
5. **Cine Toaster advertisement** — a standalone commercial for the product, potentially paying tribute to the original Video Toaster. The reel can enter the commercial via a television visible within the music video. Do not confuse this advertisement with the reel's own emotional ending.

## Reel narrative (working spine)

An archival cameraman films → his subjective view reveals the animated story → the animated character falls into the 3D/Juggler universe → a 3D element joins a music-video performance → a television within the music video broadcasts the Cine Toaster advertisement → the product is revealed → return to the original cameraman, astonished by the future of filmmaking.

This is a **narrative direction**, not a final edit, timing, script or mandate that each standalone demo contain the bridges. The reel-only connective shots can be produced separately. Its circular ending should retain the emotional payoff after the product reveal.

## Functional coverage to preserve and place opportunistically

The following are **coverage obligations / opportunities**, **not fixed assignments or mandatory story beats**. Attach them to the production where they naturally serve the film. Track evidence of actual use, not merely availability of a feature.

| Capability or prior commitment | Natural candidate | Placement / evidence still to decide |
| --- | --- | --- |
| Historical footage, rights, source, licence, credit, provenance, traceable derivatives | Historical cinema | Preserve the surviving source; restoration becomes visible in the film |
| Live-action / archival footage with ray-traced CG, compositing, occlusion, keys/mattes and camera coherence | Historical cinema or 3D | Preserve the hybrid-scene validation objective |
| Animation across techniques, consistent character identity, intentional visual-style evolution | Animated short | Story and style change together; 3DGS orbit remains exploratory |
| 3D geometry, camera moves, materials, ray tracing, reflections, spherical video warp | 3D/Juggler | Show real execution; distinguish 3D demo from reel-only homage |
| Music beats as production records, music-led edit, retiming, sound mix/stems | Music video | Preserve the earlier music-first technical objectives |
| Narration / generated voices, dialogue placement, audio mix, titles, motion graphics, formats | Advertisement or other fitting demo | The old reel's offline voice path must not vanish untested |
| Scene geography, blocking, eyeline/axis of action, continuity checks | Any narrative demo | Formerly exercised by The Last Signal; retain tests and real-scene evidence |
| Multiple takes, comparison, selection reasons, human approvals and durable creative decisions | Across demos | Capture in normal production workflow |
| Project-specific creative tooling: transition shader, declared custom shot fields, per-project looks | 3D, music video, advertisement, or reel | Preserve the *extension contract*, not necessarily copper bars or old parameter names |
| Editorially justified transitions, sequence assembly, cross-production asset lineage | Reel | Previously five documented transitions; retain meaningful variety without forcing arbitrary counts into the film |
| Project identity, isolation of jobs, switching projects, repeatable CLI checks | Test fixtures and portfolio | Technical tests need not become cinematic scenes |
| Reproducible no-API-key demonstration | Small fixture or reduced reel path | Preserve as an accessible onboarding/test path, not a restriction on finished films |
| Storyboard, previs, spatial consistency, model/workflow choice, FinOps, review gates, agent participation | Across demos | Cross-cutting evidence; do not invent claims of implemented features |

For each obligation, later record **assigned production**, **planned cinematic use**, **test/evidence**, **status** (unassigned/planned/exercised/verified), and **cost implications**. Unassigned means *open for opportunity*, not dropped.

## Superseded plan and migration safeguards

The earlier set (The Last Signal as a narrative demo; a music piece also serving as an advertisement; an animated cartoon; a separate hybrid scene; and a card/transition-driven Amiga reel with Juggler only in the reel) is **superseded as a creative plan**. **The Last Signal is discontinued as a demo**, not reserved as a sixth production. Its tests/contracts may survive as technical fixtures.

Do **not** immediately delete `examples/demo-project`, `examples/amiga-demo-reel`, their templates, `Makefile` commands or tests: first inventory dependencies, preserve coverage, and migrate runnable examples. The old Amiga reel's project-local `amiga-copper-bars`, `copper_phase`, `scanline_rate`, five reasoned transitions, offline voice and no-credential build are evidence of contracts to retain or replace with equivalent tests—not necessarily aesthetic requirements of the new films.

The previous production order is no longer authoritative. A new sequence should follow creative dependencies, production readiness, budget and user approval. **No paid generation without explicit approval.**

## New capability candidate: morphing (2026-10-17)

The proposed advertisement-to-archival-cameraman return creates a concrete cinematic motivation for **morphing**: a controlled transformation between two images/shapes/compositions, possibly combined with a reverse film-era look change and sound transition. Morphing is **not synonymous with** a cross-dissolve, grading, film grain or ordinary opacity blend.

**Status: capability to investigate and specify, not implemented or committed to a particular algorithm.** Evaluate image/landmark-guided morphs, optical-flow-assisted morphs, geometry/depth-guided transformations and (where artistically warranted) model-based video transitions. Compare temporal stability, occlusions, controllability, artifact handling, deterministic/reproducible rendering, provenance, CPU/GPU cost, and compatibility with the existing shot compositing graph. Preserve start/end image and duration, easing, anchors/masks and human review as production decisions where relevant. First prototype should use a small, inspectable transition with known endpoints; avoid paid generation without approval.

Potential placements: reel advertisement → archival camera, the animation short’s stylistic evolution, and other justified transformations. Do **not** force a morph if a match cut, lens/viewfinder reveal or look transformation serves the narrative better. A reverse film-stock look change is a separate, potentially already supported compositing concern.

## Next documentation/production decisions

- Write one-page artistic intentions for each standalone work, keeping reel-only bridges separate.
- Maintain the coverage ledger above and allocate capabilities as story opportunities emerge.
- Inventory old demo/CLI/test references and migrate before removing obsolete fixtures.
- Refine the reel's middle-to-end transitions and emotional payoff without prematurely fixing scripts or duration.
