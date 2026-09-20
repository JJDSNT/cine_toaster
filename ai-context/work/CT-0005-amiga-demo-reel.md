---
id: CT-0005
title: Add the Amiga Demo Reel multi-project fixture
type: work
status: done
owner: Codex
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - demo-project
  - multi-project
  - cli
---

# What

Add a second complete Cine Toaster demo production named Amiga Demo Reel and
make the `toast demo` command list and instantiate either available template.

# Why

Two productions with distinct stable IDs, content, paths, and workflow states
provide the minimum realistic fixture for developing a multi-project Project
Manager and verifying that active-project UI state never becomes global project
identity.

# Done

- Inspected the existing demo template, CLI packaging, project loader, and tests.
- Added Amiga Demo Reel with five scenes, screenplay, character, locations,
  decisions, blockers, shots, iterations, and varied workflow states.
- Added a two-template CLI registry, `toast demo --list`, and explicit
  `--template` selection while preserving the default command.
- Packaged both demos and verified the built wheel can create Amiga Demo Reel.
- Removed redundant forced inclusion of assets already packaged automatically by
  Hatchling, resolving a duplicate-wheel-path build failure.
- Aligned index identity with the canonical manifest project ID while retaining
  path-derived identity for generic directories.
- Added project, CLI, index, and scanner coverage for independent identities and
  template creation.
- Updated README, milestone, roadmap, and project status documentation.

# To do

- Nothing remains in this work record. The multi-project Application Runtime and
  Project Manager remain Phase 2 roadmap work.

# Decisions

- `toast demo DESTINATION` remains backward-compatible and creates The Last
  Signal.
- `toast demo --list` exposes available IDs and titles.
- `toast demo DESTINATION --template amiga-demo-reel` creates the new project.
- This work supplies fixtures and template selection; it does not pretend to
  implement the future multi-project Application Runtime.

# Validation

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed all 13 tests.
- `toast demo --list` reported both template IDs and the default.
- Indexing Amiga Demo Reel reported canonical ID `amiga-demo-reel`, 11 files,
  and 11 directories.
- `uv build` produced the source distribution and wheel successfully.
- Wheel inspection confirmed both demo projects, web assets, and transition
  assets are packaged once.
- Running `toast demo ... --template amiga-demo-reel` from the isolated built
  wheel created the project successfully.
- `git diff --check` passed.
