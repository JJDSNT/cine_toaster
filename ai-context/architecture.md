---
id: CTX-ARCHITECTURE
title: Architecture
type: architecture
status: accepted
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - architecture
  - runtime
  - boundaries
---

# Architecture

## Product boundary

Cine Toaster is a filmmaking environment with its own production model. Humans,
GUI, CLI, APIs, agents, generation systems, media tools, and future NLEs are
participants around that model. Cine Toaster is not a frontend for any one AI,
agent framework, or generation backend.

The project owns the film. Libraries and providers remain replaceable.

## Invariants

1. Project files are authoritative for production state.
2. Application and operational state must not become a second authority for the
   film.
3. Deleting caches or machine-local operational state must not destroy the
   production.
4. The Project Core is independent from UI, desktop, agent, orchestration,
   generation, and media providers.
5. Every mutation uses a shared domain command regardless of caller.
6. Human gates, comparisons, choices, and approvals are first-class production
   concepts.
7. Every background operation carries explicit project identity.
8. The active project is a UI concern and does not determine which project may
   have running work.
9. Agent communication and application telemetry are separate protocols.
10. Provider-specific data may be preserved for provenance, but the Core does
    not interpret provider behavior.
11. Development-agent context and production-agent runtime context never share
    a lifecycle or authority boundary.

## Logical layers

```text
Interfaces
  Browser UI | Desktop UI | CLI | External API | Agents
                         |
Application API
  commands | queries | subscriptions
                         |
Application Runtime
  Project Manager | Job Manager | Process Manager | Agent Runtime | Resources
                         |
Project Core
  Project | Scene | Shot | Take | Asset | Decision | Gate | Workflow | Render
                         |
Adapters
  agents | orchestration | generation | media | UI protocols
```

Dependencies point inward. The Project Core does not import interface,
application-host, or provider implementations. Adapters translate external
systems into Cine Toaster commands and results.

## Process topology

The durable application runtime must not live only in the browser or Tauri
WebView. Renderer reloads and project navigation must not own jobs, locks, or
canonical writes.

The initial target is:

```text
React/Vite renderer
        |
versioned Application API
        |
Tauri host
  window lifecycle | permissions | runtime supervision
        |
headless Cine Toaster runtime (Python initially)
  application services | project core | jobs | agents | adapters
```

The current Python runtime remains the starting point because it already powers
the CLI, project loader, index, media serving, and control room. A future
language migration requires its own decision and behavior-parity plan. Tauri may
supervise a packaged sidecar; it must not become the place where film-domain
logic is duplicated.

Browser-only operation may use the same Application API directly. Transport can
be local HTTP/SSE, Tauri IPC, or another validated mechanism; the command and
event contracts must not depend on the transport.

## State authority

| State | Authority | Deletion consequence |
| --- | --- | --- |
| scenes, shots, selected takes, approvals, decisions | project files | production damage; must be backed up/versioned |
| artifact provenance required to understand a result | project files | loss of production knowledge |
| indexes, thumbnails, derived previews | cache | rebuildable |
| open tabs, window state, recent projects | application data | UI preferences lost |
| agent session handles and transcripts not promoted to decisions | operational state keyed by project ID | conversation continuity lost |
| job execution records and recovery metadata | operational application state | job history/recovery lost, not the film |

Project-scoped does not mean project-directory-local. Machine-specific caches,
sessions, and job state should normally live in platform application data/cache
directories keyed by stable `project_id`. A project-local `.cinetoaster/`
directory is not assumed and must not be introduced without a portability and
concurrency reason.

## Commands, queries, and events

- Queries read project or application state and have no side effects.
- Commands express domain intent such as `select_take`, `approve_storyboard`, or
  `start_render`; callers do not edit TOML directly.
- Subscriptions report committed domain changes and operational progress.
- Canonical events are emitted only after a successful atomic write.
- Event consumers must be able to refresh authoritative state; an in-memory bus
  is never itself the source of truth.

Application events use an envelope containing, when relevant, `event_id`,
`event_type`, `project_id`, `resource_id`, `revision`, `occurred_at`,
`correlation_id`, and `causation_id`.

AG-UI is reserved for agent runs, messages, tool calls, agent-visible state, and
agent-driven UI actions. Job progress, filesystem changes, renders, assets, and
worker health use Cine Toaster application events.

## Job lifecycle contract

Changing or closing the active project must not stop its jobs. The target
lifetime guarantees are explicit:

- project switch: jobs continue;
- renderer reload or window recreation while the host runs: jobs continue;
- application restart: durable metadata is reconciled and interrupted work is
  marked recoverable, failed, or orphaned according to the adapter;
- full application exit or operating-system restart: execution is not promised
  until a future detached-worker design is accepted.

The job model must cover queueing, running, progress, cancellation requests,
cancellation, success, failure, orphan detection, retry attempts, provider job
identity, result staging, and reconciliation after restart.

## Adapter categories

Do not place all external systems in one generic provider package.

```text
adapters/
  agents/          Claude Code, Codex, local or future AI providers
  orchestration/   builtin state machine, LangGraph, ADK
  generation/      local/remote ComfyUI, future generators
  media/           FFmpeg, future MLT integration
  ui-protocols/    AG-UI
```

This is a boundary model, not a requirement to reorganize the repository before
the corresponding implementation exists.

## Technology status

Established directions:

- local-first, filesystem-authoritative productions;
- headless Project Core and Application Runtime;
- multi-project application state and global job management;
- shared command surface for GUI, CLI, API, humans, and agents;
- provider-independent agents and explicit adapter categories;
- human gates and preview/compare/choose/refine as domain behavior.

Strong candidates, introduced incrementally:

- Python for the existing headless runtime and Core;
- React, TypeScript, and Vite for the next visual interface;
- Tauri 2 as the desktop shell;
- FFmpeg as the first media adapter;
- ComfyUI as the first generation adapter.

Require spikes before adoption:

- CopilotKit and AG-UI integration;
- Monaco, Fountain parsers, ProseMirror, or Tiptap;
- Video.js, Remotion Player, WebCodecs, and frame-accurate playback claims;
- Fastify, WebSocket libraries, and alternative local transports;
- LangGraph, ADK, or another external orchestrator;
- MLT/Kdenlive timeline integration.

## Current implementation map

- `src/cine_toaster/project.py` loads the canonical operational project view.
- `src/cine_toaster/index.py` builds a disposable external SQLite index.
- `src/cine_toaster/cli.py` provides the current headless entry point.
- `src/cine_toaster/web.py` exposes read-only queries and constrained media.
- `src/cine_toaster/web_assets/` is the current prototype UI.
- `src/cine_toaster/transitions.py` is an existing production adapter boundary.

Preserve these working paths while extracting clearer domain and application
services. Do not create an empty monorepo tree in anticipation of future code.
