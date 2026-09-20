---
id: CT-0002
title: Implement canonical take selection
type: work
status: ready
owner: unassigned
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - project-core
  - take-selection
  - canonical-write
---

# What

Implement `select_take` as the first production-state mutation shared by Core,
CLI, HTTP API, and the review UI.

# Why

Selecting an alternative is the smallest real creative decision that proves the
filesystem authority, shared command boundary, atomic persistence, human
control, and event semantics needed by every later agent or workflow.

# Done

- Read-only scene and shot state already exposes selected and review-needed
  takes in the demo project.
- Product scope exists in `docs/milestone-02-canonical-take-selection.md`.

# To do

- Finalize the take and decision schema without inventing provider-specific
  fields.
- Add typed command/result/error contracts.
- Implement validation, optimistic revision checking, and atomic TOML writes.
- Record the resulting canonical decision and emit an event after commit.
- Expose the same operation through CLI and HTTP.
- Add compare/select UI behavior without bypassing the command.
- Add unit, integration, path-safety, conflict, and failure tests.

# Decisions

- No React/Tauri or agent dependency is required for this milestone.
- A selection is canonical; generated alternatives remain candidates until a
  human explicitly selects one.
- All callers use one application command and may not edit scene TOML directly.

# Validation

- Not started. Acceptance criteria are defined in the milestone document.
