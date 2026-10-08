---
id: CT-0067
title: Three-workspace low-fidelity wireframe — first UX study
type: work
status: proposed
owner: unassigned
created_at: 2026-10-08
updated_at: 2026-10-08
tags:
  - ux
  - wireframe
  - workspaces
  - validation
---

# Purpose

Preserve the **first low-fidelity, interactive wireframe study** of Cine Toaster's three-workspace experience, as discussed on 2026-10-08. The user liked the organizational concept but explicitly **has not validated whether it feels pleasant to a human or whether it is too visually crowded**. This is a design hypothesis, **not an approved UI implementation**.

## Three primary workspaces

1. **Screenplay & Storyboard**: screenplay, breakdown, storyboard 2D, static storyboard 3D.
2. **Production**: takes, production canvas, workflows, review.
3. **Editing & Post-production**: timeline/assembly, VFX, color, sound, delivery.

These are perspectives on one production, sharing Core data and stable project/sequence/scene/shot/take/version context. They are not independent applications.

## What the first wireframe showed

A shared shell with project identity, three top-level workspace tabs, contextual breadcrumbs, secondary mode tabs, a scene/shot explorer at left, main monitor/editor in the center, contextual properties at right, optional agent area, and shared assets/jobs/history/FinOps access.

The interactive conceptual mock-up included:
- Screenplay text or storyboard 2D/3D cards;
- Production take preview and alternatives, or a canvas/workflow schematic;
- Editing program monitor and simplified video/audio tracks;
- Contextual agent guidance and a way to open/close its panel;
- Selection of a shot carried between workspaces.

**Scope note:** This is a textual capture of the in-conversation prototype. No React component, screenshot, or working app was committed to the repository. The illustrative content and controls were placeholders, not proof of actual Cine Toaster behavior.

## What is intentionally undecided

- Whether a permanent left explorer and right inspector are needed in every mode.
- Whether a persistent assistant is beneficial or distracting.
- How much information fits comfortably on a laptop versus a large monitor.
- Which status information belongs in the main canvas versus a details-on-demand view.
- Whether the editing timeline and production canvas should share a visual layout.
- How to prioritize exceptions, pending approvals, failures and active work.
- Color, typography, density, spacing, iconography and accessibility standards.
- Actual navigation usability and task-completion performance.

## Design constraints to preserve

- **Human legibility over feature density**; avoid presenting every available function simultaneously.
- Progressive disclosure and task-oriented focus; show the right level of detail for the current decision.
- One Core source of truth for UI, CLI and agents; preserve the two-graph distinction in CT-0023.
- Preserve current work, navigation context and source lineage across workspace changes.
- Make consequential agent actions visible, inspectable and reversible.
- Do not confuse a pleasing screenshot with validated usability.

## Follow-up

The next task is **CT-0068**, a research-led investigation into human situation awareness, cognitive load, visual hierarchy, progressive disclosure and information architecture for complex creative applications. Only after that research should the wireframe be revised and tested with real tasks. Track both in the roadmap.

## Related

- [CT-0066](CT-0066-three-workspace-ux-vision.md): UX hypothesis and journeys.
- [CT-0065](CT-0065-integrated-editing-and-production-architecture.md): architectural foundations.
- [CT-0023](CT-0023-two-graphs-canvas-and-orchestration.md): canvas and orchestration are separate graphs.
