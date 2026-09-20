---
id: CT-0006
title: Add external project locators and the local Project Manager
type: work
status: done
owner: Codex
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - multi-project
  - project-manager
  - external-projects
  - storage
---

# What

Define the Project Locator and Project Source boundary, implement local external
project registration in the Application Layer, and add synthetic fixtures that
do not originate from Cine Toaster's built-in demo templates.

# Why

A third checked-in film would only prove another built-in template. Real
multi-project development needs arbitrary project locations, stable manifest
identity after moves, duplicate-ID detection, and a boundary that can later
materialize an object-store project without teaching Project Core about S3.

# Done

- Confirmed that built-in demos are copied externally at runtime but remain
  repository-owned source templates.
- Identified local external projects, mounted filesystems, and object stores as
  distinct source scenarios.
- Added accepted `SPEC-0002` for project locators, source adapters, materialized
  workspaces, synchronization, identity, and object-store constraints.
- Added ADR 0005 establishing the Project Source boundary.
- Implemented `ProjectLocator`, `MaterializedProject`, `LocalProjectSource`, and
  the initial in-memory `ProjectManager` in the Application Layer.
- Added synthetic external projects constructed independently from the built-in
  demo templates.
- Added coverage for unrelated roots, paths with spaces, simultaneous projects,
  idempotent reopen, duplicate identity, relocation, explicit close, and an
  unsupported S3 source.

# To do

- Nothing remains in this local-source foundation. Durable registration,
  relocation, active UI selection, and object-store adapters remain roadmap
  work.

# Decisions

- No third creative demo is needed for external-location behavior.
- The Project Core continues to operate on a local filesystem workspace.
- Object-store support requires materialization and explicit synchronization;
  an `s3://` URI is never passed directly to Core filesystem APIs.
- The manager has no process-global active project. Interface sessions select a
  project explicitly.

# Validation

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed all 19 tests.
- Python compile validation passed for `src` and `tests`.
- Tests proved unrelated external roots, spaces in paths, simultaneous
  registration, idempotent reopen, duplicate-ID rejection, relocation identity,
  explicit close, and unsupported S3 behavior.
- `uv build` produced the source distribution and wheel successfully.
- The isolated built wheel imported `ProjectManager` and simultaneously opened
  The Last Signal and Amiga Demo Reel with their canonical IDs.
- Every `ai-context/` Markdown document retains frontmatter.
- `git diff --check` passed.
