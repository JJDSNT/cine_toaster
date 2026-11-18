---
id: CT-STAGEFLOW-SCENEFLOW
title: StageFlow and SceneFlow filmmaking repertoire
type: work
status: ready
owner: project
created_at: 2026-11-18
updated_at: 2026-11-18
tags:
  - research
  - toolbelt
  - previs
  - blocking
  - continuity
  - screenplay
  - review
---

# StageFlow and SceneFlow: filmmaking repertoire

## What

Record two independent, related open-source references for Cine Toaster's agent-discoverable toolbelt. This is a research intake, **not** an integration commitment, implementation plan, or mandate to adopt either project's data model.

- **StageFlow** — https://github.com/taruma/stageflow — live studio: https://stageflow.taruma.my.id/
- **SceneFlow** — https://github.com/taruma/SceneFlow — live studio: https://sceneflow.taruma.my.id/

Both are by Taruma Sakti and advertise MIT licensing; verify the specific files and upstream state before code reuse.

## Why

Cine Toaster already has screenplay coverage, shot geometry/movement, blocking frames, camera previews, storyboards, a continuity ledger, and review of generated takes. These references may expose useful ideas or reusable instruments for describing directorial intent, inspecting spatial and temporal coherence, and comparing intended scenes with actual footage. **Continuity is a first-class investigation**, including spatial staging, movement across cuts, screenplay-to-screen fidelity, and the limits of continuity checks on generated footage.

The toolbelt should preserve a broad, discoverable repertoire. Each filmmaker and their agent can investigate which tools or approaches best fit the production; this record must not preselect a single workflow or dictate what the agent should extract.

## Reference inventory

### StageFlow — 3D blocking and choreography

Upstream describes a browser-based, lightweight Three.js diorama synchronized with local video, YouTube, or a simulated camera. Its human-readable YAML scores express characters, shots, camera positions, lenses, focus, and rig trajectories. It supports frame stepping, free spatial inspection, optical previews, storyboard/contact-sheet export, and viewport recording. The documented architecture separates core script/math from media, hooks, 3D stage, and UI.

Study starting points:
- https://github.com/taruma/stageflow/blob/main/README.md
- https://github.com/taruma/stageflow/blob/main/docs/STAGEFLOW_SCRIPT_SPECIFICATION.md
- https://github.com/taruma/stageflow/blob/main/docs/CORE_MATH_AND_SCORE_SPECIFICATIONS.md
- https://github.com/taruma/stageflow/blob/main/docs/MEDIA_CLOCK_AND_SYNC_SPECIFICATIONS.md
- https://github.com/taruma/stageflow/blob/main/docs/VIEWPORT_RECORDER_GUIDE.md

Questions worth exploring: scene-space coordinate systems and units; shot/actor trajectories; focus and camera optics; frame/time alignment; how a previs plan relates to approved storyboard, shot coverage, and real takes; and what continuity evidence the diorama can and cannot establish.

### SceneFlow — script-to-screen alignment and review

Upstream describes a script/video synchronization and AI-footage evaluation workstation, with cue categories for dialogue, action, camera, shots, audio, VFX, transitions, and environments. It offers cue timelines, manual cue editing, optional externally generated multimodal cues, prompt/script adherence review, and portable JSON projects. **It does not claim to automatically extract synchronization cues in the background**.

Study starting points:
- https://github.com/taruma/SceneFlow
- https://github.com/taruma/SceneFlow/blob/main/README.md
- https://github.com/taruma/SceneFlow/blob/main/SCENEFLOW_CATALOGUE.md

Questions worth exploring: evidence for screenplay-to-take correspondence; temporal cue provenance and confidence; omissions, drift and deliberate deviations; review across candidate takes; relationships to Cine Toaster's existing screenplay coverage, independent review agents, and decision records.

## Architectural investigation, not instructions to implement

- Audit Cine Toaster's **existing** spatial geometry, movement, storyboard, screenplay coverage, timebase, continuity, review, and toolbelt discovery before proposing any new model or adapter.
- Distinguish descriptive intent, estimated spatial measurements, generated output, and independently verified evidence. A 3D sketch is not proof that generated footage is geometrically correct.
- Consider continuity **across** shots, scenes, locations, and revisions as well as within a single shot; compare directorial intent with observed output without treating deviations as automatic failures.
- Evaluate interchange and adapter opportunities only after comparing upstream schemas with canonical Cine Toaster project records; avoid parallel sources of truth and duplicate project state.
- Keep film-specific creative choices in productions, shared mechanisms in the application, and human approval in the established decision/gate system.
- Preserve tool and model independence; a user/agent may use either reference as inspiration, an external tool, a validation aid, or not at all.
- Evaluate maintenance, license/attribution, browser/Node requirements, test coverage, security, export fidelity, and whether practical value warrants integration.

## Done

- Identified and documented both upstream repositories, live demos, relevant capabilities, and architectural questions.
- Recorded continuity and screenplay-to-screen evaluation as explicit investigation topics.
- Kept adoption and implementation undecided.

## To do

- Inventory the relevant existing Cine Toaster implementation and active research records.
- Examine upstream schemas and actual exports with a small reproducible scene.
- Compare outcomes and limitations against existing Cine Toaster mechanisms, especially spatial continuity and script-to-screen review.
- If evidence supports a concrete addition, propose a separate scoped work item with validation and filmmaker approval.

## Decisions

- Research-only intake; no dependency, schema, workflow, new adapter, GPU spend, or agent behavior is authorized by this document.
- Keep both references available for agent-led discovery rather than prescribing a preferred use.
- Existing Cine Toaster project files remain authoritative.

## Validation

- Read the upstream README pages and their published feature/architecture descriptions on 2026-11-18.
- Checked the Cine Toaster README, AGENTS.md, production-tooling principles, and work-record conventions.
- No upstream executable tests or Cine Toaster integration tests were run; this change is documentation only.
