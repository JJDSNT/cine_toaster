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
- preserve project files as the production authority.

Cine Toaster cannot yet:

- mutate production state through a domain command;
- compare real generated take media and select a take from the UI;
- execute or recover background jobs;
- manage multiple open projects in one application runtime;
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

On 2026-09-20, the repository test suite passed 8 tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

`git diff --check` also passed after the architecture consolidation. No product
code or canonical project schema changed in `CT-0001`.
