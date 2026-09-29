---
id: CTX-REFERENCES
title: External references
type: reference
status: active
owner: project
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - references
  - interface
  - camera
  - editing
  - licensing
---

# External references

Products and repositories we study for Cine Toaster, with what each is worth to
us and whether code may be reused. A reference is not a dependency. Adopting any
of them requires a focused spike and a work record (see `AGENTS.md`).

Licence rule: ADR 0011. Copyleft (GPL, AGPL) and unlicensed sources are
**ideas only** — study them and reimplement from the description, but never
copy their files. Permissive sources (MIT, Apache-2.0) may be reused with
attribution after a spike.

Facts below were checked on 2026-09-29 against GitHub and the public sites.

## Priority problems these references are measured against

1. **Camera movement** — a shot needs a movement that is declared, repeatable,
   and checkable, not rewritten as prompt prose every time.
2. **Cuts between clips** — adjacent generated clips must cut together: the
   exit state of one shot has to meet the entry state of the next.
3. **Graph view** — an Arcads-style production canvas of shots, takes, and
   cuts. It is not a ComfyUI-style computation graph of model parameters.

## Proprietary UX references

| Reference | What it is | Worth to us |
| --- | --- | --- |
| [Arcads.ai](https://www.arcads.ai/) | AI video ad platform. Its Workflow canvas connects scripts, actors, generations, and edits on one infinite canvas. It includes variations, API, and MCP support. | **Target interaction model** for the graph view. Cards are production objects, and edges express production relationships. Users do not wire model parameters. |
| [AI Camera Movements](https://aicameramovements.com/) | Library of 46 camera moves in 7 categories: Pan/Tilt, Zoom/Lens, Dolly/Track, Physical, Human Camera, Drone/Crane, and Specials. Each move has a looping example and a prompt that separates camera instruction from scene content. It targets Kling, Seedance, Higgsfield, and Runway. | **Vocabulary reference for camera movement.** Use its taxonomy to inform a controlled `move` vocabulary. No licence is stated, so do not copy its prompt text. |
| [sceneflow.camera](https://sceneflow.camera/) | A commercial animatic product. | **Not our SceneFlow.** It is unrelated to `taruma/SceneFlow` and is recorded here only to avoid confusion. |
| [Okay Wannabe](https://okaywannabe.com/) | Script-first AI filmmaking: Write, Create, and Film. Each scene has a checklist: Location → Cast → Opening Frame → Blocking → Direction. It renders in 15 s chunks that are then stitched. | Room navigation and a per-scene readiness checklist. The opening frame is composed from references. Cost is quoted before every render. Closed source, so it is a reference only. Details are in `CT-0020`. |

## Open-source repositories

Ranked by value to the three priority problems.

| Rank | Repository | Licence | Reuse | What matters to us |
| --- | --- | --- | --- | --- |
| 1 | [xyflow/xyflow](https://github.com/xyflow/xyflow) (React Flow) | MIT | code | **The base for the graph view.** Custom node components can show take thumbnails, and custom edges can carry cut data. It fits the React/Vite/Tauri direction. |
| 2 | [taruma/SceneFlow](https://github.com/taruma/SceneFlow) by Taruma Sakti (@tarumainfo) | MIT | code | **The SceneFlow we follow, and the closest reference for cuts.** See the section below. |
| 3 | [LudwigKienle/ai-video-production-editor](https://github.com/LudwigKienle/ai-video-production-editor) | GPL-3.0 | ideas only | **Closest to the camera-movement problem.** It turns a 3D blockout into keyframed camera moves such as push-in, orbit, and crane, then renders them as motion references for video models. It uses start and end frames, continuity review, and a re-film queue. Its full loop is the nearest in scope to Cine Toaster. |
| 4 | [christopherjohnogden/CineGen](https://github.com/christopherjohnogden/CineGen) | none | ideas only | Its **Fill Gap / Extend** generates bridge footage between clips. **Shot Board** creates a 9-angle coverage grid from one reference. A Storyboarder node emits per-shot camera prompts. It has a React Flow canvas and an NLE in one app. |
| 5 | [BeatAPI/BeatDesign](https://github.com/BeatAPI/BeatDesign) | Apache-2.0 | code | Local-first canvas → timeline, "AI Takes" alternates, 29 MCP tools for agents. It does not include advanced transitions. |
| 6 | [oshtz/noder](https://github.com/oshtz/noder) | MIT | code | Same stack as our target: Tauri 2, React, Vite, and React Flow. It is a reference for the shell, OS credential store, and signed releases. It is small and early. |
| 7 | [Valiera00/SPITE](https://github.com/Valiera00/SPITE) | AGPL-3.0 | ideas only | A scene strip over the canvas, with nodes tagged as "Shot 1 of Scene A". It shows cost on every Generate button and recovers generation jobs after a reload. It covers pre-production only. |
| 8 | [shrimbly/node-banana](https://github.com/shrimbly/node-banana) | MIT | code | Popular generic node workflows with typed handles. It is closer to ComfyUI than Arcads, so it is less relevant. |
| — | [gl-transitions/gl-transitions](https://github.com/gl-transitions/gl-transitions) | MIT (items MIT, BSD-2, BSD-3) | **submodule** | **Adopted** as the transition catalog's shader bank (`CT-0026`). 125 shaders in our own GLSL contract; 123 usable, 6 reviewed so far. |
| 9 | [NatronGitHub/Natron](https://github.com/NatronGitHub/Natron) | GPL-2.0 | ideas / external tool | Node-based compositor. It is not a graph-UI candidate. At most, it is an external tool for VFX shots behind an adapter. |

## SceneFlow and Auteur Script in detail

SceneFlow is the tool. [Auteur Script](https://auteur-script.taruma.my.id/) is
the prompt framework it renders. Auteur Script is v0.3.0 and labelled open,
experimental research notes. Its source lives in the SceneFlow repository under
`docs/articles/auteur_script/`. Versions checked: v2.3.0 through v2.5.0, released
2026-09-10 to 2026-09-16.

- **Two phases.** `STAGING` (`[INTENT]`, `[LOGIC]`, `[AESTHETIC]`, `[OPENING]` =
  first frame S₀) holds what does not change. `EXECUTION` (`[<BRIEF>]`) holds
  what moves, as macro-states S₁…Sₙ chained with `->`.
- **Single-dimension tags.** `[CAM]` covers optics and movement only. `[ACT]`,
  `[BLOCK]`, `[DIAL]`, and `[AUDIO]` each cover one dimension. This separates
  camera instructions from content, the same principle as aicameramovements.com.
- **State carryover ledger.** `Sₙ = f(Sₙ₋₁ | STAGING)`. Every beat inherits
  framing, posture, and props unless it changes them explicitly. `[STATE IN]`
  and `[STATE OUT]` mark the boundaries.
- **Cuts inside one generation.** The examples place `[CAM 01]`…`[CAM 04]`
  setups in a single Seedance 2.5 generation, so the model makes the cuts under
  one shared STAGING block. That is an alternative to stitching separate clips.
  Its `[LOGIC]` block carries screen direction and spatial order across setups.
- **Timeline Anatomy (v2.3.0).** This view plays the generated video and fires
  each EXECUTION sub-state beat by beat on a multi-track timeline. Its tracks
  are dialogue, action, camera, shot, audio, VFX, transition, and environment.
  The purpose is to compare what was written with what the model produced.
  Cine Toaster has the same review loop, applied at beat level.
- **BRIEF State Engine (v2.5.0).** `briefAnalysis.ts` parses `->` chains and
  counts macro-states and sub-states per scene.
- **Video source.** SceneFlow plays YouTube only (`youtubeId`). Cine Toaster
  reviews takes as local files in its own player, and exports SceneFlow's JSON
  shape plus `video` (2026-09-29).
- **Author's stance.** Write a detailed script and go straight to video
  generation, skipping separate asset generation. This contrasts with our
  reference-image path (SPEC-0003). Treat it as an option to test, not a rule.

## Mapping to Cine Toaster

- `[[geometry.cameras]]` (ADR 0007) already gives named positions. A **camera
  move** extends a position with start and end poses, a vocabulary term, speed,
  and an end state. It can be checked against the line of action before
  generation.
- A **cut** becomes a record between adjacent shots. It contains the exit state
  of A, the entry state of B, the cut type, whether frames are chained (last
  frame of A → first frame of B), and an optional bridge generation. A catalog
  transition is used only when it has a reason (SPEC-0004).
- The **graph view** projects these records. Nodes are shots with the selected
  take, and edges are cuts. Every edit goes through the shared application
  commands.

The exploration of these three items is tracked in `CT-0022`.
