---
id: CTX-DEVELOPMENT-CORE
title: Core development
type: guide
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - development
  - core
  - python
---

# Core development

## Current shape

- `application.py` owns local project locators, materialization, and the initial
  multi-project registry;
- `project.py` reads the production's YAML directly -- manifest, breakdowns,
  sequences and geography -- and overlays committed runtime state;
- `takes.py` discovers a shot's alternatives by reading the work directory;
- `state.py` owns runtime state: revisions, selections, decision history, and
  the atomic write;
- `commands.py` is the write boundary: `select_take`, `clear_selection`, and
  `dispatch`;
- `errors.py` defines typed domain errors with stable codes and HTTP mapping;
- `events.py` appends committed events to the operational log and tails them;
- `geometry.py` parses scene geometry, runs the continuity checks, and owns
  `CHECK_CODES`, the registry knowledge records validate against;
- `knowledge.py` loads practices and provider capability profiles from the
  built-in, shared, and project layers, and reports enforcement coverage;
- `model.py` defines index-facing data transfer objects;
- `index.py` owns the disposable SQLite index and cache paths;
- `scanner.py` classifies filesystem content;
- `web.py` hosts HTTP queries, the command endpoint, the event stream, and
  media;
- `cli.py` exposes the application entry point;
- `web_assets/` holds the browser UI: `ui.js` (shared primitives and the single
  command call), `compare.js` (the comparison room), `blockout.js` (the plan
  view), and `app.js` (rooms and navigation).

Extract further boundaries in response to real jobs and adapters; do not perform
a directory-only refactor.

## Delivered write path

The `select_take` slice established, and every later mutation reuses:

```text
interface adapter (CLI or HTTP)
            |
application command handler        commands.py
            |
project repository + domain validation   project.py
            |
atomic filesystem commit           state.py
            |
post-commit domain event           events.py
```

Each responsibility is tested independently, and CLI and HTTP are tested for
parity against the same command.

## Authored files are read-only to the runtime

No command rewrites `project.toml`, `scene.toml`, a screenplay, or a world file.
Committed decisions go to `scenes/<scene>/state.json`. See
[`ADR 0006`](../../docs/architecture/0006-authored-and-runtime-files.md). A new
command that needs to persist something asks first whether the value is authored
intent or a committed decision; only the second kind may be written.

## Filesystem safety

- Resolve project roots once at the trusted application boundary.
- Constrain project-relative paths with `Path.resolve()` and `relative_to()` or
  an equivalent safe helper.
- Write a temporary sibling file, flush it as justified, and atomically replace
  the destination.
- Never use a cache copy as the source for canonical writes.
- Keep a recoverable migration path for schema transformations.

## Application runtime

The headless runtime owns project registrations, command serialization, event
subscriptions, job supervision, and agent sessions. The active project belongs
to an interface session, not a module-level global.

When multi-project support is introduced, APIs accept `project_id` and resolve
it through the Project Manager. A stable manifest ID, not the filesystem path,
is used to associate operational state.

The initial in-memory manager implements this identity boundary for local
projects. Persistence, recent-project history, source synchronization, file
watching, and per-interface active selection remain Application Layer work.
Storage-source behavior follows
[`SPEC-0002`](../specs/SPEC-0002-project-sources.md).

## Events

`Event` values are appended to a JSON Lines log in the application cache, keyed
by project location, after the canonical write succeeds. A failure to record an
event never fails a command that already committed.

Interfaces tail the log by byte offset rather than subscribing in process, so a
decision committed from the CLI reaches a browser opened by the server. The log
is operational: deleting it loses session history, never production truth.

Events are notifications of committed state, not a substitute for reading the
project.

## Provider data

Adapters may create namespaced provenance payloads. Core code validates the
common envelope and preserves opaque provider details without importing
provider packages or branching on provider names.
