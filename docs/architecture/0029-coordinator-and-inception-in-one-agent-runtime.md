# ADR 0029: Coordinator and Inception share the existing Agent Runtime

Status: accepted · 2026-10-16 · CT-0108 / SPEC-0015

## Decision

Extend the existing `assistant` CoAgent graph with a Production Coordinator
entry and Inception context, reasoning and tool nodes. One conversation remains
the public entry. Inception is a specialist invocation with its own mission,
bounded context, tool allowlist and completion/review contract, not a new
provider session, process, scheduler or production-workflow engine.

The Coordinator uses current production state and the request to route work.
Blank films, including `toast new`'s title-only screenplay, enter Inception;
an imported screenplay is not forced through another gate. Existing production
queries/navigation and human-confirmed cut/workflow actions remain available.
Model adapters are injected independently of roles.

The agent event loop is reasoning -> application tool -> checked receipt ->
reasoning, ending with a delivery, a real human request, an explicit capability
failure or a resource limit. It is not an always-running polling loop. Writes
append Creation candidates/assessments through the same application operations
as CLI/MCP/GUI, with actor attribution, revision and source-digest preconditions.
They cannot approve human decisions, delete material or imply paid-generation
permission. A screenplay candidate is not canonical screenplay promotion.

The human GUI reads saved artifacts and decisions. A saved direction can
initiate a new turn through the existing CopilotKit client, using the canonical
decision ID, which the graph rechecks. AG-UI shared state reports role/run state
and successful-write refresh hints, not a second authoritative application bus.

## Limits and consequences

- Only Inception is a new implemented specialist. External reference research,
  image generation and other specialised stage executors are not invented.
- Built-in production workflows and durable jobs remain on SPEC-0009/0008.
- Human-triggered CoAgents interaction does not establish durable background
  continuation. Browser/service absence, restart or disconnection can interrupt
  this handoff; saved decisions/artifacts remain available for explicit resume.
- Checkpoints and conversations are still in memory. Full scoped thread/provider
  binding, durable event dispatch and recovery are not implemented by this ADR.
- The retained `next_agent_action.status=not_dispatched` is a production
  instruction, not a live runtime-state flag. The GUI must not mistake it for
  evidence that an agent is running or that work completed.
- Same completed input replay is guarded within the live checkpoint; no
  exactly-once guarantee across runtime loss is claimed.
