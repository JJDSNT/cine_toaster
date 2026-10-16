---
id: CTX-DECISION-INDEX
title: Decision index
type: decision-index
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-10-15
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
| `0010` | one native format, and it is YAML; no import step | accepted, amended by `0013` |
| `0011` | reuse from copyleft sources is by reimplementation, not incorporation | accepted |
| `0012` | recurring entities are declared at project level, not per scene | accepted |
| `0013` | the schema is English; a production's language stays in its content | accepted |
| `0014` | Final Draft is interchange, never the screenplay of record | accepted |
| `0015` | the canvas is React, built into the package, beside the control room | accepted, amended by `0018` |
| `0016` | a person may edit the screenplay; the program never rewrites it | accepted; amends `0006` |
| `0017` | LangGraph runs the agents; production workflows stay built in | accepted |
| `0018` | CopilotKit carries the assistant through an optional, supervised Node sidecar | accepted; amends `0015` |
| `0019` | no desktop shell: the browser, served by the local runtime | accepted |
| `0020` | Claude Code works on a film through Cine Toaster's MCP server | accepted |
| `0021` | a production keeps its own history beside what it is the history of | accepted |
| `0022` | composition is a typed graph of primitives, not a collection of effects | accepted |
| `0023` | time is exact: fractions to compute, ticks to store, a media clock to play | accepted |
| `0024` | signals are production records: their kind, origin and transformations | accepted |

When a decision is proposed or superseded, update the ADR and this index in the
same change. Work records link the decision that affected execution.
