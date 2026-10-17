---
id: CTX-SPEC-INDEX
title: Specification index
type: index
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-29
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
| `SPEC-0003` | cast entities, executable references, and generation lineage | accepted | partial |
| `SPEC-0004` | the production schema for a feature and a demo reel | draft | planned |
| `SPEC-0005` | movement within a shot: camera moves, subject marks, exit state | implemented | complete |
| `SPEC-0006` | screenplay coverage: each shot knows its screenplay and dialogue | implemented | complete |
| `SPEC-0007` | the cut: how one shot becomes the next, within a scene | implemented | complete |
| `SPEC-0008` | jobs: background work that outlives the interface that started it | implemented | complete |
| `SPEC-0009` | workflows and human gates: the built-in state machine that stops for a person | accepted | partial |
| `SPEC-0010` | locations and the backlot: a set declared once, pinned from a shared library | accepted | partial |
| `SPEC-0011` | transition mattes and overlays: a join shaped by a picture, and a picture riding it | accepted | partial |
| `SPEC-0012` | the compositing graph: primitives, typed values, colour, identity, renderers (ADR 0022) | accepted | partial |
| `SPEC-0013` | creation candidates: immutable concept/screenplay versions and explicit upstream inputs (ADR 0026) | accepted | partial |
| `SPEC-0014` | storyboard drawings: retained candidates, pinned shot/reference context and review navigation (ADR 0027) | accepted | partial |
| `SPEC-0015` | Production Coordinator and bounded Inception agent loop inside the existing CoAgent | accepted | partial |
| `SPEC-0016` | Art Direction, retained visual briefs and independent pixel prevalidation | accepted | partial |
| `SPEC-0017` | Directing shot proposals and independent continuity review | accepted | partial |
| `SPEC-0018` | Decision inbox and approved stage inputs | accepted | partial |
| `SPEC-0019` | Sequence-level Inception adherence, screenplay/storyboard evidence and independent review | accepted | partial |

## Rule

A specification describes observable behavior, identity, state, lifecycle,
security, and acceptance criteria. Source layout and library-specific details
belong in implementation work unless they are necessary to preserve the
contract.
