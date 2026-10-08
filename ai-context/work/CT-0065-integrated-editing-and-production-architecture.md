---
id: CT-0065
title: Integrated editing and production architecture — research and vision
type: work
status: proposed
owner: unassigned
created_at: 2026-10-08
updated_at: 2026-10-08
tags:
  - editing
  - post-production
  - architecture
  - interoperability
  - research
---

# Purpose

Deepen Cine Toaster's **whole-production architecture** before selecting an NLE engine or adding isolated features. The goal is a robust, standards-aware, agent-assisted filmmaking environment that reuses mature open components wherever possible, without discarding working Core capabilities. **This is an investigation, not an implementation decision.**

## Product principle

The filmmaker can change a film narratively, visually, technically or through an agent while preserving the relationship between screenplay, scene, shot, take, generated assets, edit decisions, sound, versions, provenance and approved outputs. Editing may also request regeneration or new material from production; production and post-production form a feedback loop.

Manual controls and agent commands must operate on the **same authoritative edit state**. An agent proposes an inspectable change; approval, versioning and rollback are first-class.

## Existing foundations to preserve and verify

- SPEC-0007 defines cuts, including J/L splits, transition decisions and human approval.
- CT-0050 documents rendered transitions and J/L cuts in scene assembly.
- CT-0038 documents scene assembly versions and review.
- CT-0059 provides a declared continuity ledger, not a visual inference engine.
- CT-0063 provides audio stems for external DAW workflows; do not rebuild Ardour.
- Existing screenplay, React canvas, sequence assembly, media generation and provenance workflows must be audited in the current code before adding a parallel editor model.

The items above are **documented existing capabilities**, not promises that a full interactive NLE timeline already exists.

## Capability map and research tracks

| Area | Reuse / standards to evaluate | Desired capability | Evidence needed |
| --- | --- | --- | --- |
| Editorial model | OpenTimelineIO; EDL, FCPXML, AAF adapters | Multitrack editing, timebase/timecode, clip identity, reconform, relink, media handles | Round-trip a real Cine Toaster sequence; record adapter losses |
| Media engine | Existing FFmpeg; MLT; GStreamer Editing Services | Frame-accurate preview, seeking, audio sync, proxy, cache, final render | Identical edit fixture in candidate engines, including J/L cuts |
| Editing UI | Kdenlive/Shotcut/Olive design references; React timeline components | Trim, split, ripple, roll/slip, snapping, waveform, keyframes, multitrack, undo | Prototype integrated with Core commands; no duplicate state |
| Color and finishing | OpenColorIO, ACES, OpenEXR | Color-space-aware renders, shot matching, HDR and intermediates | Mixed-model shot fixture with declared transforms |
| Effects and compositing | OpenFX hosts, Natron, Blender, FFmpeg | Masks, passes, title/VFX catalogs, external round trips | Evaluate host boundaries, licenses and project interchange |
| Sound | Existing stems/Ardour; EBU R128, true peak, multichannel | Dialogue/music/FX workflows, loudness targets, delivery profiles | Measured export against a declared profile |
| Delivery | Captions/subtitles, metadata, codecs, QC, IMF/AS-11 where relevant | Reproducible delivery profiles and validation | Profile-specific test outputs; no universal format claim |
| Production semantics | MovieLabs OMC / 2030 Vision | Stable asset, task, version and dependency relationships | Map existing project model; document gaps without forcing wholesale ontology adoption |
| Generative edit | Provider adapters, asset/version lineage | Replace/extend/reframe a shot without losing unrelated decisions | Regenerate one segment, reconform, compare before/after |
| Agentic editing | Typed operations, optimistic concurrency, audit logs | Propose → preview/diff → approve → apply → undo | Concurrent/conflicting edit tests and user approval gates |

### Candidate technologies are not commitments

OpenTimelineIO is an **interchange representation**, not a renderer or a substitute for the native Core model. MLT and GES are candidate execution engines, not mandatory replacements for FFmpeg. OFX requires a compatible host; OpenColorIO requires a defined color pipeline. Review project and dependency licenses (including copyleft, plugin distribution, commercial conditions) before adoption. Verify upstream maintenance, API stability, platform compatibility, performance and license compatibility against Cine Toaster's distribution model.

Reference projects and primary sources:
- https://github.com/AcademySoftwareFoundation/OpenTimelineIO
- https://github.com/mltframework/mlt
- https://gitlab.freedesktop.org/gstreamer/gstreamer
- https://github.com/KDE/kdenlive
- https://github.com/AcademySoftwareFoundation/OpenColorIO
- https://github.com/AcademySoftwareFoundation/openexr
- https://github.com/NatronGitHub/Natron
- https://movielabs.com/production-technology/ontology/
- https://movielabs.com/2030-vision/

## Architectural questions to resolve

1. Which Core entities own source media, generated asset variants, timeline instances, trims, effects, approvals and render outputs?
2. What is the canonical time representation (rational frame rate, sample time, variable-frame-rate media) and how are handles/timecode represented?
3. Which edit operations already exist, which are only UI gaps, and which require new Core semantics?
4. How do caches, proxies and playback remain consistent with the final render? What constitutes an acceptable preview/render difference?
5. How does replacing a generated take invalidate dependent caches and outputs without silently changing approved edit decisions?
6. What is the transaction model for agent proposals, conflicts, version diffs, undo and user approval?
7. Which color, sound and delivery profiles are actually needed for the four demo projects and future feature films?
8. What data can be exchanged with professional tools losslessly, and what must be flagged as lossy?

## Sequenced investigation (tracked, not a feature promise)

**P0 — Audit and contract.** Inspect current Core edit/assembly commands, version records, trim handling, UI, preview and sound paths. Publish a *capability matrix* (implemented / partial / missing / unknown), canonical edit operations and test fixture. Exit: documented single source of truth, timebase and edit-command contract.

**P1 — Interactive timeline proof.** Build a minimal React multitrack timeline over existing Core operations. Test seeking, trim/split, J/L cuts, transitions, waveforms, undo, agent proposal and approval. Exit: the same persisted edit renders through existing assembly without a second timeline model.

**P2 — Interchange and engine experiments.** OTIO export/import and relink/reconform fixture; compare existing FFmpeg against MLT and GES for preview, performance, accuracy, maintenance and integration cost. Exit: measured comparison and ADR; retaining FFmpeg alone is an acceptable result.

**P3 — Production-wide finishing and asset lineage.** Mixed-source color/ACES proof, stems and loudness validation, external VFX round-trip, generated-take replacement with dependency invalidation. Exit: documented profiles, reproducible artifacts and gaps.

**P4 — Intelligent workflows.** Agentic editing proposals, continuity observations with confidence and human review, semantic/narrative editing and local regeneration. Exit: safe transaction tests, user-visible diff, approved commit and rollback.

## Non-goals

- Rewriting a complete NLE, DAW, compositor or color suite before testing integrations.
- Choosing a specific engine, UI library or standard as mandatory in this document.
- Assuming an AI-generated shot can always be replaced seamlessly.
- Treating inferred visual continuity as an authoritative fact.
- Promising lossless interchange across all NLE formats.

## Immediate next action

Create a **current-code audit and capability matrix** for editing, preview, assembly, assets and versions; select one representative sequence fixture with J/L cuts, transition, audio and an alternative generated take. Then implement the P1 timeline spike and P2 OTIO round-trip against that same fixture. Record findings here and link resulting ADRs, issues and work items from the development roadmap. The investigation must not remain an untracked reference document.
