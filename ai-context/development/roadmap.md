---
id: CTX-DEVELOPMENT-ROADMAP
title: Development roadmap
type: roadmap
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - development
  - roadmap
  - milestones
---

# Development roadmap

This roadmap orders architectural risk. It is not a promise that every listed
technology will be adopted.

## Phase 0 — foundation

Status: in progress under `CT-0001`.

- Consolidate architecture, state authority, agent boundaries, and process
  topology.
- Establish `ai-context/` as the English-language project memory and tracker.
- Preserve and document the working read-only Python prototype.

Exit: contributors can identify current behavior, accepted decisions, active
work, and the next vertical slice without relying on chat history.

## Phase 1 — first canonical decision

Status: ready under `CT-0002`.

- Introduce concrete take candidates for a reviewable shot.
- Implement `select_take` through one application command.
- Add atomic persistence, revisions, typed errors, and a post-commit event.
- Expose the command through CLI, HTTP, and the existing review UI.
- Record selection as a durable creative decision.

Exit: GUI, CLI, and API prove one shared production mutation with conflict and
failure tests.

## Phase 2 — application runtime and jobs

- Use The Last Signal and Amiga Demo Reel as independent fixtures for Project
  Manager identity, active-project switching, and job isolation tests.
- Add Project Manager registration by stable project ID.
- Add a durable operational store outside project directories.
- Implement a minimal FFmpeg job with progress, cancellation, reconciliation,
  and explicit result staging/adoption.
- Prove a Project A job continues while Project B is active.

Exit: background work survives navigation and renderer lifecycle according to
the documented job contract.

## Phase 3 — React and desktop shell

- Spike React/TypeScript/Vite against the versioned Application API.
- Migrate one production room at a time with behavior parity.
- Spike Tauri supervision of the headless runtime and constrained native
  capabilities.
- Keep browser-mode development and tests available.

Exit: the desktop shell can open a project, supervise the runtime, observe jobs,
and recover from renderer reload without owning domain logic.

## Phase 4 — preview and comparison

- Add real take assets and proxy strategy.
- Measure linked playback, seek, stepping, A/B, and side-by-side comparison.
- Choose the simplest playback stack that meets measured requirements.
- Do not claim frame accuracy unless the spike proves it.

Exit: a human can compare real alternatives and commit a selection through the
same command established in Phase 1.

## Phase 5 — first production agent

- Define tool schemas over existing queries and commands.
- Spike AG-UI and CopilotKit without making either a Core dependency.
- Implement scoped Cine Toaster agent threads and provider session bindings
  according to
  [`SPEC-0001`](../specs/SPEC-0001-agent-session-binding.md).
- Add `Follow Agent` navigation preference.
- Implement a small built-in workflow ending at a real human gate.

Exit: an agent can analyze a scene, present alternatives, request a canonical
decision, and continue from the committed result without bypassing permissions.

## Later evaluation

- ComfyUI local and remote generation adapters;
- screenplay editor architecture;
- external orchestrators such as LangGraph or ADK;
- MLT/Kdenlive exchange and timeline integration;
- detached workers and execution across full application exit or machine
  restart;
- professional frame-accurate comparison if product requirements justify it.
