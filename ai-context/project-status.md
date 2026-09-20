---
id: CTX-PROJECT-STATUS
title: Project status
type: status
status: current
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - status
  - tracker
  - roadmap
---

# Project status

Last updated: 2026-09-20

## Current phase

Ready to transition from the read-only prototype to the first canonical
production write.

## Product state

Cine Toaster can currently:

- open an external filesystem project;
- parse the project and per-scene operational manifests;
- build a disposable external SQLite index;
- expose project, scene, library, search, media, and transition queries;
- present a read-only Production Control Room in the browser;
- preview built-in and project transition assets;
- operate through the `toast` CLI;
- list and instantiate two independently identified demo productions: The Last
  Signal and Amiga Demo Reel;
- register multiple arbitrary external local projects simultaneously through an
  in-memory Project Manager;
- preserve manifest project identity across path changes and reject duplicate
  IDs opened from different locations;
- prevent `toast demo` from creating runtime productions inside the application
  source checkout unless an explicit fixture-development override is supplied;
- preserve project files as the production authority.

Cine Toaster cannot yet:

- mutate production state through a domain command;
- compare real generated take media and select a take from the UI;
- execute or recover background jobs;
- persist the multi-project registry or expose project switching in the UI;
- run project-scoped agents;
- ship as a Tauri desktop application.

## Active work

- No implementation item is currently in `doing` state.

## Ready next

- `CT-0002` — canonical take selection (`ready`).

The recommended next implementation is `select_take`, not a frontend rewrite or
agent integration. It establishes the mutation boundary that those interfaces
will later consume.

## Recently completed

- `CT-0007` — added Git ignore conventions and CLI protection against accidental
  in-repository runtime projects.
- `CT-0006` — added external local project locators, materialized workspaces, an
  in-memory Project Manager, identity conflicts, and the remote-source contract.
- `CT-0005` — added Amiga Demo Reel, selectable demo templates, stable indexed
  manifest identity, packaging coverage, and multi-project fixtures.
- `CT-0004` — accepted the scoped agent-thread and provider-session contract.
- `CT-0003` — standardized frontmatter across the development memory/tracker.
- `CT-0001` — architecture, tracker, decision records, and development guidance.
- Read-only Production Control Room.
- External filesystem projects and disposable search index.
- Transition library with GLSL and WebM preview support.
- Baseline architecture review against the proposed desktop and agent direction.

## Principal risks

- allowing GUI, CLI, and agents to develop separate write paths;
- moving long-lived runtime state into a renderer process;
- confusing project-scoped state with state stored inside the project folder;
- adopting CopilotKit, an orchestrator, or a media UI library before its boundary
  is proven by a spike;
- losing generation reproducibility by discarding provider provenance;
- claiming frame accuracy before measuring it.

## Validation baseline

On 2026-09-20, the repository test suite passed 20 tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The source distribution and wheel build successfully. The isolated installed
wheel can instantiate both demo templates and register both simultaneously in
the Project Manager. `git diff --check` also passed.
