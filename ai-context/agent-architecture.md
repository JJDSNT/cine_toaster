---
id: CTX-AGENT-ARCHITECTURE
title: Agent architecture
type: architecture
status: accepted
owner: project
created_at: 2026-09-20
updated_at: 2026-10-17
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

That spike ran (CT-0043), and ADR 0017 records the outcome:

- **Production workflows** (SPEC-0009) stay on the built-in engine.
- **Agents** run on LangGraph, as an optional extra, served over AG-UI to
  the interface (CopilotKit CoAgents).
- The interface sends what the person is looking at as context with each
  turn.
- An agent acts only through commands, asks the person before
  consequential actions, and never decides a human gate.
- The model sits behind an injected model adapter, independent of role. The
  existing adapters are Codex CLI, Claude Code CLI and Claude API. Precedence
  is explicit host flag (`--agent-provider`), host environment
  (`CINE_TOASTER_MODEL`), then the current CLI's unambiguous inherited signal.
  No installed-executable or credential scan selects a provider. This selection
  does not implement SPEC-0001 session binding: the CLIs make ephemeral requests,
  not attachments to an open conversation. Repository development instructions,
  context and tool authority do not become runtime production-agent context.

## Implemented production-role loop (CT-0108)

ADR 0029 / SPEC-0015 extend the existing public `assistant` CoAgent with a
Production Coordinator and Inception specialist nodes. New/title-only films
enter Inception; other requests can be delegated based on production context.
The specialist has bounded read/candidate/assessment tools through the shared
Application API, not merely a role prompt. It cannot decide human gates or
generate images. Revision and material preconditions protect publication.

The GUI refreshes canonical records after writes and can initiate the next
CoAgent turn after saving a human direction. This is human-interaction-driven
coordination, not durable background dispatch. Model/session bindings remain
separate; in-memory thread replay/project guards do not establish full
SPEC-0001 conformance. Specialist extensions below reuse this topology.

## Art Direction and Visual Prevalidation (CT-0110)

ADR 0030 / SPEC-0016 add internal Art Direction tools and a fresh visual reviewer
call to the same CoAgent. Briefs/reviews are canonical Creation records; visual
inputs are bounded, project-scoped registered raster bytes with pinned hashes.
Generation uses existing jobs, explicit per-plan quota consent and non-overwriting
adoption. The reviewer cannot approve human gates. Codex CLI currently implements
the optional image-input transport; other adapters stop honestly without vision.
Bounded waits can leave a real generation job running; since CT-0115 the role
leaves it to Generation Operations, which continues the work when it ends.

## Directing and canonical continuity (CT-0111)

ADR 0031 / SPEC-0017 add Directing/Shot Planning and Script Supervisor/Continuity
to the existing public graph. The Coordinator already exists; it is reused.
Plans/reports use shared application commands and the Creation journal, with
revision/full planning-source checks. A fresh independent reviewer reuses the
existing continuity ledger and computed checks, distinguishing declarations,
computation, inference and unknowns. Standalone canonical audits need no plan.
Textual camera intent is not measured geometry or pixel inspection.

Preproduction displays versions, evidence and scoped human direction requests.
Exact saved human decisions can initiate a new same-CoAgent turn. Eight-step /
two-review limits do not create autonomous background work. Approval is not
canonical promotion, storyboard approval or generation permission. Existing
canonical findings remain separate from proposed coverage/state checks.

## Approved stage handoffs (CT-0112)

ADR 0032 / SPEC-0018 extend the existing human command and CoAgent, not the
orchestration topology. A GUI approval can atomically adopt source-pinned inputs
for explicitly displayed canonical scene/shot targets. The existing Art Direction
role consumes the exact decision and publishes registered reference images as
retained storyboard candidates through shared Core/HTTP commands. New generation
still requires the existing quota interrupt/jobs. Final storyboard approval,
canonical shot rewrites and automatic 3D/master handoff are separate.

Additive briefs/references/drawings do not invalidate their own handoff; changed
pinned sources do. Outputs are traceable without chat. The inbox derives real
waiting gates and incomplete work, not live-run state. Conversational continuation
waits for a connected agent and uses distinct human intent IDs for explicit retries;
no background scheduler or durable autonomous recovery is added.

## Production work structure (CT-0113)

The Coordinator, Inception, Art Direction and its fresh reviewer receive the
shared product work contract: canonical sequences are the work/human-review
unit; scenes/shots remain internal or explicitly partial work. The film overview
keeps the complete sequence roster outside its truncated scene-detail summary.
Coordinator/Inception can explicitly read `work_structure` by canonical
sequence/scene ID. Directing/Continuity and its fresh reviewer receive the same
projection, preserved before narrowing detailed scene records. Every read uses
the addressed production; no cached chat grouping or Singular-specific range.
External MCP production agents get the same startup contract and a read-only
`read_work_structure` tool, alongside the existing product filmmaking guide.

The policy includes iterative stage flow, source/evidence comparison, independent
review, human-only creative gates, version retention and agent-owned gaps.
This is product code/context, never a runtime import of `ai-context/`. Context
availability does not implement SPEC-0019's remaining comparison/validator or
constitute proof of readiness, review execution or approval.

## Declared roles and the model catalogue (CT-0115)

ADR 0034. A production role is a declaration in `agents/roles.py`: kind
(coordinator, author, reviewer, technical), the model capabilities it needs,
budgets, and its per-turn scratch; the graph's state and the Coordinator's
reset are derived from these. Only implemented roles are declared.

Adapters declare `capabilities` (structured output, vision, web); all three
carry images inside the request. `agents/model_catalog.yaml`, extended by
`$XDG_CONFIG_HOME/cine-toaster/models.yaml`, describes adapters and known
models (strengths, cost class, source); it never selects a model. Every role
uses the model the host was given unless the person binds a role to another
(`roles:` in the same file). `toast doctor` names the roles the supplied model
can and cannot serve. RunPod/ComfyUI is not an infrastructure agent: recipes
(data), a Generation Operations role, and a development skill (ADR 0034).

## Generation Operations (CT-0115)

A deterministic `technical` role (`agents/operations.py`). A role whose job
outlives its turn records a wait (thread, project, job, role) in disposable
operational state; a watcher in the assistant server reads the job through the
runtime and, when it ends, opens one turn on that thread with a Generation
Operations message (never a person's). Success hands the turn to the waiting
role, which keeps and reviews the result but may not generate (no one is there
to consent). Failure is diagnosed from the job error, the recipe's endpoint
health (data plane only) and the measured failures of `knowledge/providers/`,
and ends asking the person. It is not a second scheduler: production jobs
stay on the existing engine; waits survive a restart, conversations do not.

## Runtime skill packaging

A future location such as `packages/runtime-skills/` may contain filmmaking
skills. The exact packaging language and directory remain undecided. Do not
create placeholder skill trees before a real runtime skill and loader contract
exist.

Development procedures live under `.agents/skills/` (the first:
`runpod-comfyui`, CT-0115), in the coding agent's skill format, linked from
`.claude/skills/` for Claude Code. They are not distributed to production
agents; a test keeps the product package from referencing them.
