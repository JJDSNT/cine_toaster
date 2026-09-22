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

The first canonical production write is delivered. Cine Toaster is no longer a
read-only prototype: a human or an agent can compare registered alternatives and
commit a decision through one shared command.

## Product state

Cine Toaster can currently:

- open an external filesystem project;
- parse the project and per-scene operational manifests;
- build a disposable external SQLite index;
- expose project, scene, library, search, media, and transition queries;
- present a read-only Production Control Room in the browser;
- preview built-in and project transition assets;
- operate through the `toast` CLI;
- register concrete take alternatives per shot, with status, media, note, cost,
  and preserved provider provenance;
- commit a take selection through one shared command from Core, CLI, HTTP, or
  the browser, with revisions, typed errors, atomic writes, and a durable
  decision history;
- compare alternatives side by side in the browser and record why one was
  chosen;
- read scene geometry and report continuity problems before anything is
  generated (`toast check`);
- draw a plan-view blockout of the set, the cameras, and the line of action;
- group scenes into sequences and report progress at the level a production
  actually reviews;
- follow committed decisions live, including decisions made from another
  terminal;
- record every assembled version of a scene with the takes it was built from,
  the author's verdict, and the reason, then roll selections back to any of
  them and list what differs between two cuts;
- read a production's own YAML breakdown directly, with no import step, and
  discover a shot's alternatives — including rejected ones and why — by reading
  the work directory;
- record what a production learns as data with dates, evidence, and a link to
  the check that enforces it, and report how much of it software actually
  enforces (`toast knowledge`, `toast why`);
- carry measured provider capability claims that a future generation adapter
  will read;
- list and instantiate two independently identified demo productions: The Last
  Signal and Amiga Demo Reel;
- register multiple arbitrary external local projects simultaneously through an
  in-memory Project Manager;
- preserve manifest project identity across path changes and reject duplicate
  IDs opened from different locations;
- prevent `toast demo` from creating runtime productions inside the application
  source checkout unless an explicit fixture-development override is supplied;
- distinguish reusable Cine Toaster mechanisms from production-owned creative
  values and one-off tools, demonstrated by a working project-local transition
  in Amiga Demo Reel and the no-extension case in The Last Signal;
- preserve project files as the production authority.

Cine Toaster cannot yet:

- run a generation from the interface: the providers exist but no command or job
  calls them yet;
- execute or recover background jobs;
- persist the multi-project registry or expose project switching in the UI;
- run project-scoped agents;
- ship as a Tauri desktop application.

## Active work

- No implementation item is currently in `doing` state.

## Closed: scene import

There is no import step. Cine Toaster reads the production's own YAML where it
lies, and takes are discovered from the work directory rather than declared
(ADR 0010). The exporter, the generated scene files and the staleness check they
required are all deleted.

## Delivered

- `CT-0013` — production-specific tooling boundary and demo examples (`done`).
- `CT-0002` — canonical take selection (`done`).
- `CT-0008` — scene geometry, continuity checks, sequences, live board (`done`).
- `CT-0009` — knowledge layer and the eyeline direction check (`done`).
- `CT-0010` — closed decision loop, assembly versions, staleness (`done`).
- `CT-0011` — one native format, read the production's YAML directly (`done`).
- `CT-0012` — generation providers moved into the tool (`done`).

## Ready next

- Phase 2 — application runtime and jobs. The first job should be the one the
  external production already needs: assemble a sequence from its selected takes
  with FFmpeg, with progress and cancellation.
- A generation adapter reading `[[geometry.cameras]]` as camera intent, so a
  shot can be regenerated from the project rather than from a script.

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
- hiding one film's creative values inside application defaults;
- claiming frame accuracy before measuring it.

## Validation baseline

On 2026-09-20, the repository test suite passed 141 tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The source distribution and wheel build successfully. The isolated installed
wheel can instantiate both demo templates and register both simultaneously in
the Project Manager. `git diff --check` also passed.
