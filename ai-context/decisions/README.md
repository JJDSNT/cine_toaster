---
id: CTX-DECISION-INDEX
title: Decision index
type: decision-index
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - decisions
  - adr
  - architecture
---

# Decision index

Accepted architectural decisions are stored as ADRs in `docs/architecture/`.
This index is the development-memory view of those decisions; it avoids keeping
two full normative copies.

| ADR | Decision | Status |
| --- | --- | --- |
| `0001` | projects are external and indexes are disposable | accepted |
| `0002` | the application uses a headless runtime outside the renderer | accepted |
| `0003` | canonical project changes use shared commands | accepted |
| `0004` | development agents and production agents are separate systems | accepted |
| `0005` | projects are opened through locators and source adapters | accepted |
| `0006` | authored files are never rewritten; runtime state lives beside them | accepted, amended by `0010` |
| `0007` | scene geometry is authored, checkable project state | accepted |
| `0008` | sequences are the unit a production reviews | accepted |
| `0009` | accumulated knowledge is evidence-linked data, not documentation | accepted |
| `0010` | one native format, and it is YAML; no import step | accepted |

When a decision is proposed or superseded, update the ADR and this index in the
same change. Work records link the decision that affected execution.
