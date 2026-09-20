---
id: CT-0001
title: Consolidate the architecture and development context
type: work
status: done
owner: Codex
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - architecture
  - documentation
  - foundation
---

# What

Turn the three temporary architecture inputs into repository-owned guidance,
formal decisions, a concrete roadmap, and an execution-memory convention.

# Why

Cine Toaster needs one coherent direction before introducing writes, desktop
infrastructure, agents, or generation providers. Future contributors must be
able to distinguish implemented behavior, accepted architecture, candidate
technology, and active work.

# Done

- Inspected the current Python runtime, UI, project fixtures, tests, and ADR.
- Reviewed the three temporary input documents.
- Compared the proposed direction with the current implementation.
- Established `AGENTS.md` and the initial `ai-context/` index and architecture.
- Added the operational work-record convention requested by the project owner.
- Established `ai-context/` as the English-language memory and tracker for
  developing Cine Toaster.
- Explicitly separated development agents from production agents and their
  instructions, memory, skills, authority, and lifecycle.
- Added focused project-model, agent, conventions, core, frontend, testing, and
  roadmap guidance.
- Added accepted ADRs for runtime topology, canonical commands, and the two agent
  systems; clarified external operational-state placement in ADR 0001.
- Specified Milestone 02 and its live `CT-0002` execution record.
- Updated the public README and Milestone 01 status.
- Removed the fully incorporated temporary files `1.md`, `2.md`, and `3.md`.

# To do

- Nothing remains in this work record. Begin `CT-0002` as a separate change.

# Decisions

- The working Python runtime remains the initial headless Core/runtime.
- React/Vite/Tauri are incremental interface candidates, not grounds for an
  immediate Core rewrite.
- `Agent Runtime` is normative technical vocabulary; `AI Crew` is not.
- `ai-context/` includes both consolidated knowledge and live execution state.

# Validation

- `git diff --check` passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed all 8 tests
  after consolidation.
