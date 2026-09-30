# ADR 0015: The canvas is React, built into the package, beside the control room

Status: accepted

> Its Tauri desktop shell was cancelled by [ADR 0019](0019-no-desktop-shell.md) (2026-09-30).

## Context

The production needs a canvas: scenes, shots, takes and cuts as cards and
edges, in the Arcads style (CT-0022 to CT-0024). All six reference
repositories build theirs on React Flow. The existing control room is
dependency-free JavaScript served by the Python runtime (ADR 0002), and it
works.

CopilotKit, the candidate agent UI, was checked on this stack (CT-0033). It
works with React 19, Vite and React Flow 12 against a Python AG-UI agent, so
choosing React leaves that option open without committing to it.

## Decision

- **Stack:**
  - React 19, TypeScript and Vite for new interface work;
  - `@xyflow/react` 12 for the canvas;
  - exact versions pinned in `frontend/package.json` and its lockfile.
- **Where it lives.** `frontend/` holds the source. `make ui` builds it into
  `src/cine_toaster/web_assets/canvas/`. That output is ignored by git but
  included in the wheel as an artifact, and the Python runtime serves it at
  `/canvas/`. Since ADR 0016, the same app holds the screenplay editor: it is
  built into `web_assets/app/` and served at `/app/` (canvas) and
  `/app/script.html` (editor), and `/canvas/` redirects.
- **Node is a build tool, never a runtime dependency.** Reading, checking and
  rendering a production still need only Python. A machine without Node has
  no canvas, and `toast doctor` reports that and says what to run.
- **The canvas reads, the runtime decides.**
  - `GET /api/graph` (`cine_toaster/graph.py`) projects records into nodes
    and edges. The projection is in the core, so the CLI and agents can share
    it.
  - The canvas holds no production state and writes nothing. It refreshes on
    committed events, and job progress is ignored.
- **Positions are presentation.** A pure, tested layout function computes
  them from the graph every time: scenes as rows, shots in order, takes below
  their shot. When the canvas becomes editable (plan step 13), dragged
  positions may be remembered as disposable operational state. They never
  enter project files.
- **No rewrite.** The existing control room stays. Rooms move to React only
  when a change needs what React gives.

## Consequences

- Contributors need Node 20+ to change or build the canvas. `make setup`
  builds it when Node is present and skips it otherwise.
- The bundle is about 130 KB gzipped and needs 48 npm packages. CopilotKit,
  if adopted (plan step 12), would add roughly 700 packages. Weigh that
  against `@ag-ui/client` and a chat of our own.
- Tauri (plan step 14) can load the same build; nothing here assumes a
  browser tab.
