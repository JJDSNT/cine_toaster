---
id: CTX-CONVENTIONS
title: Development conventions
type: guide
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - conventions
  - development
  - workflow
---

# Development conventions

## Language and writing

- Write code, comments, tests, repository documentation, and `ai-context/` in
  English.
- Use filmmaking terms consistently with `project-model.md`.
- Use `Agent Runtime` for the product subsystem. Do not use `AI Crew` as a
  technical type or package name.
- State whether a document describes current implementation, accepted direction,
  a candidate, or a spike.

## Change workflow

1. Read `project-status.md`, the relevant architecture context, and active work
   records.
2. Create or update an `ai-context/work/CT-NNNN-*.md` record.
3. Inspect current code and tests before proposing a new structure.
4. Make the smallest coherent change that advances the vertical slice.
5. Run focused tests, then the repository-wide suite when practical.
6. Update the work record with completed work, remaining work, decisions, and
   exact validation.
7. Update `project-status.md` if capability, phase, queue, risk, or next action
   changed.
8. Promote durable decisions to a focused context document or ADR.

## Code boundaries

- Project Core code does not import UI, desktop, agent provider, orchestrator,
  generation provider, or media provider code.
- Interface handlers translate input and output; they do not implement domain
  decisions.
- Application services coordinate projects, commands, jobs, and adapters.
- External process invocations live behind a typed adapter.
- Use explicit `project_id`; do not infer it from active UI state.
- Do not pass unvalidated absolute paths from the renderer to shell commands.

## Python

- Support the Python version declared in `pyproject.toml`.
- Prefer standard-library solutions while the runtime remains small, but do not
  contort important contracts merely to avoid a justified dependency. PyYAML is
  the one such dependency so far, taken for the scene format (ADR 0010).
- Use type annotations, focused immutable dataclasses where useful, and domain
  errors instead of unstructured strings across boundaries.
- Keep filesystem writes atomic and path resolution constrained to the intended
  project or application-state root.
- Keep the dependency list short and justified. Each addition names the contract
  it protects.

## TypeScript and frontend

- Introduce TypeScript with the React/Vite UI rather than converting the Python
  runtime preemptively.
- Generate or share API schemas where practical; do not maintain unrelated
  handwritten domain models in Python and TypeScript.
- Renderer state is a projection. Persisted production decisions go through the
  Application API.
- UI components do not spawn providers or media processes directly.

## Schemas and compatibility

- Version canonical project formats and public application contracts.
- Reject unsupported versions with actionable errors.
- Add fixtures and migration tests before requiring a new canonical field.
- Preserve unknown namespaced provider provenance when reading and writing.

## Repository and production separation

- Runtime film projects live outside the Cine Toaster source checkout.
- Built-in templates and intentional test fixtures are the only project-shaped
  directories normally versioned with the application.
- Use `--allow-inside-repository` only for deliberate fixture development.
- A production may have its own independent Git repository; do not confuse that
  repository with the Cine Toaster application repository.

## Dependencies

- Do not add a library because it appears in an architecture candidate list.
- A spike records the capability tested, representative data, measurement,
  failure modes, and adoption recommendation.
- Prefer a narrow adapter so replacement does not affect domain code.

## Commits and review

- Keep a change focused on one coherent outcome.
- Explain architectural impact and list exact validation.
- Call out schema changes, migrations, new permissions, external processes, and
  unverified platform behavior explicitly.
