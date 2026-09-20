---
id: CT-0004
title: Specify scoped agent session bindings
type: work
status: done
owner: Codex
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - agent-runtime
  - sessions
  - context-scope
---

# What

Define how a Cine Toaster production agent can resume provider context through a
provider session ID without confusing provider identity, film-project scope, or
canonical production knowledge.

# Why

Claude, Codex, local models, and future providers may expose resumable sessions.
Cine Toaster should reuse that context where useful while preventing leakage
between projects, agent roles, scenes, shots, workflows, or tasks.

# Done

- Identified the need for a Cine Toaster-owned logical thread distinct from a
  provider-owned session handle.
- Identified project, role, provider, resource scope, revision, lifecycle, and
  permission checks required before resume.
- Added accepted `SPEC-0001` defining Cine Toaster-owned threads, replaceable
  provider bindings, immutable context scope, resume and rotation behavior,
  events, privacy, security, and acceptance criteria.
- Added the specification index and linked the contract from agent architecture,
  project model, roadmap, ADR 0004, and repository instructions.

# To do

- Nothing remains in this specification work. Implementation remains planned
  for the production-agent phase in the roadmap.

# Decisions

- Provider session IDs are opaque operational handles, never project identity or
  canonical film knowledge.
- Context scope and tool authorization are separate controls.
- A binding cannot move to another project, agent role, or context scope.

# Validation

- Verified that all `ai-context/` Markdown files begin with frontmatter.
- Verified discoverability of `SPEC-0001`, `AgentThread`,
  `AgentSessionBinding`, scope fields, and resume operations across context and
  ADR documentation.
- `git diff --check` passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed all 8 tests.
