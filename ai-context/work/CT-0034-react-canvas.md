---
id: CT-0034
title: React stack decision and a read-only production canvas
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - interface
  - canvas
  - react
---

# What

Plan step 7: decide the interface stack and build the first canvas on it.
The canvas is read only and projects real records.

# Why

The Arcads-style canvas is the target interaction model (CT-0022 to
CT-0024). A stack decision needs working code on real data, not a comparison
table. The user confirmed React after the CopilotKit check (CT-0033) and
chose automatic layout.

# Done

- ADR 0015: React 19, TypeScript and Vite, with `@xyflow/react` 12. The
  source is in `frontend/`; the build lands in the package, is served at
  `/canvas/`, and Node is needed only to build.
- `graph.py` and `GET /api/graph` project the production:
  - scene, shot and take nodes;
  - cut, take and scene-order edges;
  - each shot's best picture (still, then take, then blocking frame);
  - speakers, moves and findings.
- Canvas app:
  - custom cards for scenes, shots and takes, and a labelled cut edge;
  - a pure layout function, tested with `node --test`;
  - a details panel with links into the control room;
  - a takes toggle and live refresh from committed events.
- `make ui` and `make ui-test`; `make setup` builds the canvas when Node is
  present; `make test` also runs the canvas checks.
- `toast doctor` reports whether the canvas is built. The wheel includes the
  build as an artifact. The control room navigation links to the canvas.

# To do

- Plan step 13: an editable canvas through commands, with remembered
  positions as disposable operational state.
- Cast, location and workflow-step nodes, once those records exist
  (SPEC-0003, CT-0030, plan step 10).

# Decisions

- The projection lives in the Python core; the layout lives in the interface.
- The minimap was removed: on a read-only canvas that fits its view, it
  covered cards and added nothing.
- Stills of composed shots appear only after a build, which is when they
  exist.

# Validation

- `tests/test_graph.py` (10 tests): the projection, no positions in the
  view, the endpoint, the "not built" page, SPA fallback, and path safety.
- `frontend`: `tsc` typecheck clean; 4 layout tests pass.
- Headless Chromium on the demo:
  - both scenes, 5 shots with blocking frames, 8 takes, L-, hard and J-cuts,
    and the scene-order line;
  - selecting a cut, a shot and a take shows each record;
  - live check: after `select_take` for SC-030 P3 "One blink" through
    `/api/commands`, the canvas marked the take and the P3 card switched
    from "Blocking frame" to "Selected take", without a reload.
- Wheel built with the canvas assets included. Full Python suite: 331 tests
  OK.
