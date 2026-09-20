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

The Python package currently combines several early concerns:

- `application.py` owns local project locators, materialization, and the initial
  multi-project registry;
- `project.py` loads the production manifest and scene manifests;
- `model.py` defines index-facing data transfer objects;
- `index.py` owns the disposable SQLite index;
- `scanner.py` classifies filesystem content;
- `web.py` hosts read-only HTTP queries and media;
- `cli.py` exposes the current application entry point.

This is appropriate for the prototype. Extract boundaries in response to real
write commands and jobs; do not perform a directory-only refactor.

## Near-term extraction

The `select_take` slice should establish:

```text
interface adapter (CLI or HTTP)
            |
application command handler
            |
project repository + domain validation
            |
atomic filesystem commit
            |
post-commit domain event
```

Names may evolve, but these responsibilities must be testable independently.

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

Start with explicit typed event values and a simple in-process publisher if that
is sufficient. Transport and durability may evolve independently. Events are
notifications of committed state, not a substitute for reading the project.

## Provider data

Adapters may create namespaced provenance payloads. Core code validates the
common envelope and preserves opaque provider details without importing
provider packages or branching on provider names.
