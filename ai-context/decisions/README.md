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

When a decision is proposed or superseded, update the ADR and this index in the
same change. Work records link the decision that affected execution.
