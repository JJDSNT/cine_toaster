---
id: CT-0066
title: Three-workspace UX vision and validation
type: work
status: proposed
owner: unassigned
created_at: 2026-10-08
updated_at: 2026-10-08
tags:
  - ux
  - workspaces
  - navigation
  - research
  - agents
---

# Goal

Develop and validate a coherent user experience for Cine Toaster across **three primary workspaces**:

1. **Screenplay & Storyboard** (pre-production).
2. **Production** (generation and take review).
3. **Editing & Post-production** (assembly, finishing and delivery).

These are **three views of one film, not three separate applications, databases or pipelines**. The workspace architecture is a product hypothesis pending usability validation, not a commitment to a specific component library or redesign.

## Research references and lessons

- **Blender workspaces**: task-specific editor arrangements, customizable layouts, saved context. https://docs.blender.org/manual/en/latest/interface/window_system/workspaces.html
- **DaVinci Resolve**: specialized pages for media, editing, compositing, color, sound and delivery; simpler and advanced editing modes can coexist. https://www.blackmagicdesign.com/products/davinciresolve
- **Kdenlive**: task-focused editing layouts; evaluate panel density, preview and timeline workflows. https://kdenlive.org/
- **Unreal Sequencer**: shot/sequence/take navigation and editorial context. https://dev.epicgames.com/documentation/en-us/unreal-engine/cinematics-and-movie-making-in-unreal-engine
- **CopilotKit**: React frontend tools and human-in-the-loop approval components. https://docs.copilotkit.ai/frontend-tools
- **Existing Cine Toaster design**: CT-0020 (Okay Wannabe reference), CT-0023 (production graph versus orchestration graph), CT-0034 (React canvas), CT-0036 (screenplay editor), CT-0046 (editable canvas), docs/canvas.md, docs/screenplay-editor.md.

Public examples are **UX references**, not authorization to copy proprietary code. Validate actual workflows in working software before claiming parity.

## Workspace responsibilities

| Workspace | Primary modes | Core user question |
| --- | --- | --- |
| Screenplay & Storyboard | Write, breakdown, 2D board, 3D static board, references, shot planning | What film do I intend to make? |
| Production | Shot/take browser, generation, workflow status, comparisons, approvals, provider controls | What material do I have, and what must be produced? |
| Editing & Post-production | Timeline, cuts, transitions, VFX/compositing, color, sound, titles/captions, export/QC | How does the finished film play and meet delivery requirements? |

A mode is a panel/layout configuration, not a new top-level product. Storyboard 3D is for blocking/comparison, **not mandatory Blender-driven character animation**. Production may offer both **shot-oriented** and **node/canvas-oriented** views; the graph remains a projection of production records, never the authoritative workflow or film state.

## Shared UX shell

- Persistent **project / sequence / scene / shot / take / version** context and breadcrumbs.
- Shared media/assets library, contextual inspector, activity/jobs, approval inbox, assistant and search/command palette.
- Direct navigation from a screenplay beat to its board, shot, takes and edited use; reverse navigation from a timeline clip to its screenplay/production origin.
- Saved layout presets and optional user customization; responsive resizing and keyboard shortcuts.
- Distinct visual language for **authored**, **generated**, **inferred**, **approved**, **stale/out-of-date** and **failed** data.
- No silent context reset when switching workspaces; preserve selection, playhead, scroll and panel arrangement where sensible.
- Accessibility: keyboard-only paths, focus order, screen-reader labels, contrast, captions and reduced-motion preference.

## Four end-to-end validation journeys

**J1 — From screenplay to first cut.** Write a scene, break it into shots, compare 2D and static 3D boards, generate alternatives, approve a take and assemble it. Validate discoverability and consistent identity across spaces.

**J2 — Fix a shot during editing.** From a timeline clip, open its source take and reference, request an extension or replacement, compare alternatives, approve a reconform and preserve unrelated edits, transitions and sound. Show stale dependencies explicitly.

**J3 — Agent-assisted change.** Ask the agent to improve pacing or check continuity; it highlights affected shots, proposes structured edit operations and a before/after preview; the user accepts, modifies or rejects. Verify revision conflicts, undo and audit history.

**J4 — Finalize and deliver.** Review picture, VFX, color, stems, captions, delivery profile and QC; export and reopen a version with traceable sources and warnings.

## Interaction rules

1. **Direct manipulation first where appropriate**: a person can always inspect and edit without prompting an agent.
2. **One source of truth**: UI, CLI and agents call Core commands; a React timeline or graph must not become a competing persistent model.
3. **Progressive disclosure**: simple defaults, advanced controls on demand, without hiding critical review states.
4. **Agent actions are visible and reversible**: proposal, scope, cost/side effects, preview, approval, execution, diff and rollback.
5. **Fast feedback**: immediate local UI state where safe, background job progress, proxies/cache and explicit preview-versus-final limitations.
6. **Interoperability and media lineage**: all workspace views refer to stable identities and revisions.

## Research and design questions

- Does a three-space navigation outperform a task-based home dashboard for returning users?
- Which secondary modes should be persistent tabs, and which should be inspector panels?
- Is the canvas a default Production view, a secondary mode, or both depending on the task?
- How should users compare storyboard 2D, 3D blockout, references and generated take side by side?
- Should the assistant appear as a dock, inline action, selection toolbar and/or review inbox?
- How do we surface jobs, cost and failed generation without turning every screen into a dashboard?
- What are minimum laptop-size and large-monitor layouts? How does keyboard navigation work?
- What user-facing language distinguishes cut, trim, take, shot, scene, version and render?

## Deliverables and next steps

- [ ] **Audit current routes, React components and real user journeys**; map existing screens to the three workspaces without assuming absent functionality.
- [ ] **Information architecture**: navigation tree, global context, modes, shared panels and cross-workspace deep links.
- [ ] **Wireframes** for all three spaces, including small laptop and large monitor; Production shot view vs node view.
- [ ] **Interactive journey prototype** for J1 and J2 using existing Core data; validate context preservation and replacement of a take.
- [ ] **Agent UX prototype** for J3 with visible proposal/approval/undo; evaluate CopilotKit hooks against current integration.
- [ ] **Usability and accessibility review** using tasks, time-to-completion, wrong-context errors and recovery.
- [ ] Record accepted decisions in ADRs, implementation work items and the roadmap; update this investigation with evidence.

## Success criteria

A user can complete J1–J4 without losing selection or source lineage; can locate any edited clip's originating shot/take; can reject an agent proposal safely; and can switch between manual and agent-driven operations without divergent project state. No final UI layout or technology is approved until a prototype demonstrates these behaviors.

## Related work

- [CT-0065](CT-0065-integrated-editing-and-production-architecture.md): cross-product architecture, standards, editing and post-production.
- [CT-0023](CT-0023-two-graphs-canvas-and-orchestration.md): film graph versus workflow graph.
- [CT-0046](CT-0046-editable-canvas.md): command-based editing from the canvas.
