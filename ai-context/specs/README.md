---
id: CTX-SPEC-INDEX
title: Specification index
type: index
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-22
tags:
  - specifications
  - contracts
  - index
---

# Specification index

Specifications define detailed contracts needed by multiple implementations or
interfaces. They refine the architecture without binding the Project Core to a
specific library or provider.

## Lifecycle

Specification statuses are:

- `draft` — being explored and not safe to implement as a stable contract;
- `review` — internally coherent and awaiting acceptance;
- `accepted` — approved for implementation;
- `implemented` — acceptance criteria are satisfied in the repository;
- `superseded` — replaced by another specification or ADR.

An accepted specification may still have `implementation: planned` in its
frontmatter. Update it to `partial` or `complete` as code lands. Implementation
work is tracked separately under `ai-context/work/`.

## Specifications

| ID | Contract | Status | Implementation |
| --- | --- | --- | --- |
| `SPEC-0001` | scoped production-agent threads and provider session bindings | accepted | planned |
| `SPEC-0002` | project locators, sources, and materialized workspaces | accepted | partial |
| `SPEC-0003` | cast entities, executable references, and generation lineage | accepted | planned |
| `SPEC-0004` | the production schema for a feature and a demo reel | draft | planned |

## Rule

A specification describes observable behavior, identity, state, lifecycle,
security, and acceptance criteria. Source layout and library-specific details
belong in implementation work unless they are necessary to preserve the
contract.
