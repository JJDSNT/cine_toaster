---
id: CT-0002
title: Implement canonical take selection
type: work
status: done
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

- Concrete take entities on shots (`[[shots.takes]]`) with status, media,
  note, cost, and a namespaced provenance envelope preserved verbatim.
- `commands.py`: `select_take`, `clear_selection`, and `dispatch`, returning one
  `CommandResult` shape to every interface.
- `state.py`: runtime-owned `scenes/<scene>/state.json` with revisions,
  selections, and decision history, written atomically (ADR 0006).
- `errors.py`: typed domain errors with stable codes and HTTP status mapping.
- `events.py`: append-only operational event log written after commit.
- CLI: `toast shots`, `toast take select`, `toast take clear`, `toast events`.
- HTTP: `POST /api/commands`, `GET /api/events`, `GET /api/events/stream`.
- UI: a comparison room with A/B playback, per-take selection, rationale
  capture, and the scene decision history.
- `SPEC-0002` conformance: a command on a read-only source fails with a typed
  `permission_denied` before touching the filesystem.

# Decisions

- Authored files are never rewritten; decisions live in a runtime-owned file
  (ADR 0006). This replaces the original assumption that the command would write
  `scene.toml`.
- Re-selecting the same take with no new rationale is a no-op, so history stays
  meaningful.
- A take with status `rejected` is not eligible for selection.
- Superseding records a new decision and keeps the previous one.

# Validation

- `tests/test_commands.py` (19) — commit, supersede, no-op repeat, stale
  revision, ineligible take, unknown resources, authored file untouched,
  unrelated state preserved, event emitted on success and never on failure,
  atomic write with no leftover temporary file, future schema version refused.
- `tests/test_http_commands.py` (8) — HTTP reaches the same command and maps
  each domain error to its status code.
- `tests/test_cli_takes.py` (9) — CLI parity and exit codes.
- Full suite: 70 tests passing (was 20), under both
  `PYTHONPATH=src python3 -m unittest discover -s tests` and pytest.
