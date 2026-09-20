# ADR 0004: Separate development agents from production agents

Status: accepted

## Context

AI agents may both help develop Cine Toaster and operate inside Cine Toaster to
make films. Both may use instructions, tools, skills, and persistent context,
but they have different users, authority, data, and lifecycles. Treating them as
one system risks exposing source-development memory to film agents and packaging
coding procedures as filmmaking capabilities.

## Decision

Development agents operate on the Cine Toaster source repository. They use
`AGENTS.md`, `ai-context/`, source tools, tests, and optional development skills
under `.agents/skills/`. `ai-context/` is the English-language memory and
tracker for developing the software.

Production agents are Cine Toaster product features. They operate through the
Agent Runtime on an explicitly addressed film project, use runtime filmmaking
skills and authorized application tools, and store sessions in project-scoped
operational application state. Only explicit domain commands promote their
outputs into canonical production decisions.

The technical subsystem is named `Agent Runtime`. `AI Crew` is not a normative
architecture term, though it may be evaluated later as UI language.

The detailed contract for Cine Toaster-owned agent threads, provider session ID
bindings, context scope, resume, rotation, and isolation is maintained in
[`ai-context/specs/SPEC-0001-agent-session-binding.md`](../../ai-context/specs/SPEC-0001-agent-session-binding.md).

## Consequences

- Runtime agents never use `ai-context/` as film context.
- Development skills and runtime filmmaking skills have separate formats,
  packaging, permissions, and release lifecycles.
- Agent providers remain independent from production roles.
- Security permissions remain separate from creative human gates.
- Repository tracking can evolve without changing the film project format.
