---
id: CTX-AGENT-ARCHITECTURE
title: Agent architecture
type: architecture
status: accepted
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - agents
  - development-agents
  - production-agents
---

# Agent architecture

## Two separate agent systems

Cine Toaster has two agent contexts that must never be conflated.

### Development agents

Development agents help build the Cine Toaster software.

- They operate in this source repository.
- Their instructions begin in `AGENTS.md`.
- Their memory and tracker are in `ai-context/`.
- Reusable development procedures may live in `.agents/skills/`.
- Their outputs are source code, tests, documentation, and development records.

Development agents are not part of the Cine Toaster product architecture and
must not be modeled as a film crew.

### Production agents

Production agents are product capabilities used while making a film.

- They operate through the Cine Toaster Agent Runtime.
- Their authority is limited to a specific film project and granted tools.
- Their capabilities may come from runtime filmmaking skills.
- Their sessions are operational state; promoted decisions are canonical state.
- They use the same application commands as GUI, CLI, and API callers.

Production agents do not read `ai-context/` or development work records as film
context. Development skills must not be packaged as runtime filmmaking skills.

## Runtime concepts

The Agent Runtime distinguishes:

- **Agent** — a reasoning role such as Director, Continuity, or Cinematography;
- **Skill** — a versioned capability such as shot breakdown or continuity
  analysis;
- **Tool** — an executable operation backed by a query or command;
- **Workflow** — coordination of agents, skills, tools, decisions, and gates.

A skill is not necessarily an agent. A workflow may invoke a skill directly,
use one or several agents, or execute deterministic tools without an agent.

`Agent Runtime` is the normative technical term. `AI Crew` may be explored as
future product language but is not an architecture component or fixed roster.

## Provider independence

Roles are not providers:

```text
Director Agent
      |
Agent Provider Adapter
      +-- Claude Code
      +-- Codex
      +-- local model
      +-- future provider
```

Changing provider assignment must not alter filmmaking workflow semantics.
Provider adapters translate messages, tool calls, sessions, cancellation,
usage, and provider errors into Agent Runtime contracts.

Provider-specific session IDs and transcripts are operational application state
keyed by project ID. A useful conclusion becomes production knowledge only when
an explicit command records it as a decision, note, prompt, gate outcome, or
other canonical concept.

Cine Toaster owns the logical `AgentThread`; a provider-owned session ID is an
opaque, replaceable `AgentSessionBinding` attached to that thread. This preserves
conversation continuity across session rotation or provider replacement without
making a provider handle the identity of an agent. The normative lifecycle,
scope, resume, fork, isolation, and security contract is defined in
[`SPEC-0001`](specs/SPEC-0001-agent-session-binding.md).

## Tool boundary

Agent tools expose Cine Toaster vocabulary such as:

```text
read_scene
focus_shot
compare_takes
select_take
request_approval
start_render
show_render_job
```

They do not expose arbitrary filesystem writes, raw provider payloads, or raw
FFmpeg/ComfyUI execution as domain operations. Tools declare input and output
schemas, permissions, side effects, project scope, idempotency expectations,
and approval requirements.

Creative human gates are not substitutes for security authorization. Filesystem
scope, process spawning, network access, secrets, and destructive operations use
application security policy even when a creative gate has been approved.

## Sessions and multi-project behavior

- Every run, session, tool call, and event carries `project_id`.
- Switching the visible project does not implicitly terminate other projects'
  runs.
- Resource policy may pause, queue, or terminate a run, but this is an explicit
  Application Layer decision.
- An agent cannot act on the active UI project by implicit global state.
- Provider context must be rebuilt from the addressed project and authorized
  operational session, not whichever project was opened most recently.
- A thread's root project/scene/shot/workflow/task scope is immutable. Changing
  it creates a new thread so an already-contextualized provider is never treated
  as if it had forgotten broader context.
- Resuming a session always re-evaluates current permissions and project
  revision; a provider session is neither an authority nor a permission grant.

## UI interaction

Agents may converse, stream progress, request tools, present alternatives, and
suggest navigation. UI actions are typed intentions such as `show_scene` or
`focus_shot`, not direct component manipulation.

`Follow Agent` is a user preference:

- when enabled, accepted navigation intentions may change the visible resource;
- when disabled, agents continue while the current view remains unchanged;
- the user can always override navigation;
- navigation does not grant additional project permissions.

## AG-UI and application events

AG-UI is a candidate protocol adapter for agent interaction: run lifecycle,
messages, tool calls, agent state, and agent-driven UI actions. CopilotKit is a
candidate UI/runtime integration and requires a spike before adoption.

AG-UI is not the Cine Toaster application bus. Filesystem changes, background
jobs, renders, assets, and worker health use application event contracts. An
agent may observe or explain those events through an adapter without owning the
underlying stream.

## Orchestration

Start with a small built-in explicit state machine. Orchestrator adapters may be
evaluated when real workflows need persistent graphs, branching, retries,
parallel execution, delegation, resumability, or complex human-in-the-loop
behavior.

LangGraph, ADK, or another framework must not become part of the Project Core.
Adoption requires a spike that proves value over the built-in workflow and
documents persistence, recovery, cancellation, observability, and migration.

## Runtime skill location

A future location such as `packages/runtime-skills/` may contain filmmaking
skills. The exact packaging language and directory remain undecided. Do not
create placeholder skill trees before a real runtime skill and loader contract
exist.

Development procedures, if added under `.agents/skills/`, follow the coding
agent's skill format and are not distributed to production agents.
