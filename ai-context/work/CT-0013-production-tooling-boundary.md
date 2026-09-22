---
id: CT-0013
title: Document the production-specific tooling boundary
type: work
status: done
owner: unassigned
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - architecture
  - projects
  - tooling
---

# What

Define how a production keeps scripts, values, recipes, and visual mechanisms
that are specific to its film without turning them into Cine Toaster defaults.
Demonstrate the boundary in the two built-in demo productions.

# Why

Moving film-independent mechanisms into Cine Toaster is only half of the
boundary. A new production also needs to know what to do with the creative
logic that remains: keep it with the film, pass creative values explicitly,
and avoid assuming the application will discover or execute arbitrary project
code.

# Done

- Added `docs/production-tooling.md` with the ownership test, production
  guidance, execution-safety rule, and the four motivating Singular examples.
- Added the stable boundary to the project model and linked the public guide
  from the main README.
- Documented the parameterized-mechanism case in The Last Signal: it has no
  local executable extension and keeps palettes and curves as explicit film
  inputs.
- Added `amiga-copper-bars` to Amiga Demo Reel as a real project-local
  transition whose creative constants stay out of Cine Toaster.
- Linked the working demo from the transition catalog documentation and added
  a focused loader test.

# To do

- Nothing remains in this documentation change. A general recipe, script, or
  project-command contract remains deliberately undefined until an integrated
  production workflow needs one.

# Decisions

- Document current ownership and safety rules without introducing a general
  plugin, recipe, or project-command schema.
- Use the existing project-local transition catalog for the executable demo;
  it is already a supported extension boundary.
- Do not auto-discover or execute arbitrary scripts from a production.

# Validation

- `PYTHONPATH=src python3 -m unittest tests.test_transitions -v` — 3 passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — 141 passed when
  run outside the restricted sandbox so HTTP tests could bind localhost and
  event tests could write operational cache state.
- `git diff --check` — passed.
