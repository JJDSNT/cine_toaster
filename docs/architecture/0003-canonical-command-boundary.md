# ADR 0003: Canonical changes use shared commands

Status: accepted

## Context

Project files are the authority, but GUI, CLI, HTTP, agents, and future
automation all need to change them. Allowing each interface to edit TOML or
media metadata directly would create multiple business-rule implementations,
lost updates, and events that disagree with committed state.

## Decision

All canonical production mutations go through shared application commands
implemented by the Project Core. A command carries explicit project and
resource identity, actor information, validated intent, and an expected
revision where existing state is changed.

Canonical file updates are atomic. Conflicting revisions fail explicitly.
Domain events are emitted only after a successful commit. Interfaces and
provider adapters translate to and from these contracts but do not implement
parallel write paths.

The first command will be `select_take`, because it is a small, real creative
decision already represented in the read-only control room.

## Consequences

- Filesystem authority gains explicit transaction and concurrency semantics.
- CLI, HTTP, UI, and agent behavior can be contract-tested against one result.
- Current manifest loaders will evolve into a repository and command boundary
  incrementally.
- Schema revisions and typed errors become necessary before broader editing.
- General-purpose metadata editing is deferred until real domain commands show
  what abstractions are needed.
