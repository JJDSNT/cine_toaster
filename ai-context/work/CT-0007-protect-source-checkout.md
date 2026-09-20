---
id: CT-0007
title: Prevent runtime projects entering the source repository
type: work
status: done
owner: Codex
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - projects
  - git
  - safety
  - cli
---

# What

Protect the Cine Toaster source checkout from accidentally receiving runtime
film projects created by `toast demo`.

# Why

Built-in templates belong in the repository, but instantiated productions have
independent identity, storage, and version-control lifecycles. A user can
currently choose a destination inside the source checkout and accidentally add
the resulting film to the Cine Toaster Git repository.

# Done

- Confirmed that `.gitignore` has no runtime-project convention.
- Confirmed that `toast demo` currently checks only whether the destination
  already exists.
- Added root-level ignore rules for `projects/`, `local-projects/`, and
  `.cinetoaster-projects/`.
- Added source-checkout detection based on the repository root, `.git`, and
  `pyproject.toml`.
- Made `toast demo` refuse new destinations anywhere inside that checkout.
- Added the explicit `--allow-inside-repository` override for fixture work.
- Documented repository/production separation in README and development
  conventions.
- Added a test proving refusal causes no filesystem creation and the explicit
  override succeeds.

# To do

- Nothing remains in this work record.

# Decisions

- Do not ignore arbitrary `project.toml` files or directories because built-in
  templates and fixtures are intentionally versioned.
- Detection is limited to the Cine Toaster source checkout; projects may still
  live in their own independent Git repositories.
- An explicit override is required for intentional fixture development.

# Validation

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed all 20 tests.
- `toast demo --help` exposes the explicit override.
- The safety test confirms the refused destination is not created.
- `git diff --check` passed.
