---
id: CTX-WORK-INDEX
title: Work records
type: index
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - work
  - tracker
  - execution
---

# Work records

This directory is the operational memory of Cine Toaster development. A work
record lets a human or another agent resume without reconstructing intent from
chat or Git history.

## Required sections

Each non-trivial record states:

- **What** — concrete scope and expected outcome;
- **Why** — product or architectural reason;
- **Done** — completed changes, kept current during execution;
- **To do** — remaining work and ordering;
- **Decisions** — choices, assumptions, and deviations from the initial plan;
- **Validation** — commands, results, and known gaps.

Use the common frontmatter fields `id`, `title`, `type`, `status`, `owner`,
`created_at`, `updated_at`, and `tags`. Work records use `type: work`. Valid
work statuses are `ready`, `doing`, `review`, `blocked`, and `done`.

Keep records concise. Stable knowledge is promoted to the focused
`ai-context/` documents or `docs/architecture/`; the work record remains the
execution history and links to those destinations.

## Work queue

- `CT-0002` — implement canonical take selection (`ready`)

## Recently completed

- `CT-0005` — add the Amiga Demo Reel multi-project fixture (`done`)
- `CT-0004` — specify scoped provider session bindings (`done`)
- `CT-0003` — standardize `ai-context/` frontmatter (`done`)
- `CT-0001` — consolidate the architecture and development context (`done`)

## Naming

Use `CT-NNNN-short-description.md`. Move old records to `history/` only when the
active directory becomes difficult to scan; moving a completed record is not
required.
