---
id: CTX-INDEX
title: Cine Toaster AI context
type: index
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - ai-context
  - memory
  - tracker
---

# Cine Toaster AI context

This directory is the repository-owned memory and development tracker for Cine
Toaster. It lets a human or AI contributor answer: what the project is, why it
is built this way, what exists now, what was done, what is being done, what
comes next, and how the work was validated. It does not depend on Claude,
Codex, or any other coding-agent provider.

It is not runtime film data and it is not a replacement for product
documentation or accepted architecture decision records.

## Scope boundary

`ai-context/` belongs exclusively to development of the Cine Toaster software.
Development agents use it to modify this repository. Production agents running
inside Cine Toaster use a film project, Agent Runtime contracts, and runtime
filmmaking skills. They do not read this directory as production context.

## Reading paths

For any architectural or domain change, read:

1. `project-status.md` — current phase, delivered capabilities, active work,
   next action, risks, and recent validation;
2. `architecture.md` — boundaries, process topology, state authority, and
   technology status;
3. `project-model.md` — canonical production concepts and mutation rules;
4. `agent-architecture.md` — agents, skills, tools, workflows, providers, and
   UI protocols;
5. `development/roadmap.md` — the implementation order and milestones;
6. `work/README.md` and the relevant active record — what is being done, why,
   what is complete, what remains, and how it is being validated.

Then read the focused guidance relevant to the task:

- `conventions.md`
- `development/core.md`
- `development/frontend.md`
- `development/testing.md`
- `decisions/README.md`
- `specs/README.md`

## Documentation authority

- `README.md` describes the product and current public status.
- `ai-context/` describes the current consolidated engineering model.
- `docs/architecture/` contains accepted decision records and their rationale.
- `docs/milestone-*.md` defines stable milestone scope and acceptance.
- `ai-context/work/` records live execution and handoff state.
- `ai-context/specs/` defines accepted or proposed technical contracts that are
  more detailed than architectural direction.
- source code and tests show what is implemented today.

If these disagree, do not silently choose one. Preserve working behavior,
identify the mismatch, and update the appropriate decision or context document
as part of the change.

## Current state

Cine Toaster currently has a small dependency-free Python runtime, a `toast`
CLI, a local HTTP control room, a filesystem project loader, a disposable
SQLite index, a vanilla browser UI, and a transition library. The current UI is
read-only.

The next milestone introduces the first canonical write: selecting a take. It
must establish the shared command, validation, atomic persistence, decision
record, and concurrency behavior that later GUI, CLI, API, and agent operations
will reuse.

## Execution memory

Every non-trivial task has a work record containing:

- what is changing;
- why it matters;
- what has been completed;
- what remains;
- decisions or deviations;
- exact validation and known gaps.

Update the record while executing. When work is complete, keep the concise
record as history and promote durable conclusions into architecture, project
model, conventions, or an ADR. Do not copy raw conversations into this
directory.

Update `project-status.md` whenever a work record changes the project phase,
active queue, delivered capability, principal risk, or next recommended action.

All content under `ai-context/` is written in English.

## Frontmatter contract

Every Markdown document in `ai-context/` begins with YAML frontmatter. Common
fields are:

- `id` — stable identifier unique within this directory;
- `title` — human-readable title;
- `type` — document role such as `architecture`, `guide`, `roadmap`, `status`,
  `index`, `decision-index`, `specification`, `work`, or `work-template`;
- `status` — lifecycle state appropriate to the document type;
- `owner` — current maintaining role or assignee;
- `created_at` and `updated_at` — ISO dates;
- `tags` — plain YAML list used for discovery.

Work records additionally use the workflow statuses defined in
`work/README.md`. Keep the frontmatter synchronized when the body changes in a
way that affects status, ownership, or classification.
