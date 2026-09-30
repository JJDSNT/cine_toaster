# ADR 0020: Claude Code works on a film through an MCP server of Cine Toaster

Status: accepted (2026-09-30, CT-0045, the user's choice of MCP as the next step).

## Context

SINGULAR was made by letting Claude Code do the work: write breakdowns,
build tools, run generations, all as file edits and ad hoc scripts. The
in-product assistant (ADR 0017, 0018) reads everything but changes the film
only after a yes. The user wanted Claude Code to keep working the way it
did, but inside the product's records.

## Decision

- `toast mcp <project>` serves one project over MCP (stdio, the official
  Python SDK, the optional `mcp` extra). Claude Code connects with
  `claude mcp add cine-toaster -- toast mcp <project>`.
- Every tool is a query or an existing application command, run in the
  server's process, with the actor `claude-code` of kind `agent`. It is one
  more interface beside the control room, the CLI and the assistant, held by
  the same scene lock (ADR 0006 amendment) and revisions.
- Offered: reads (the film, a scene, a shot, cast, screenplay search,
  budget, checks, locations, camera moves, generation and picture plans);
  decisions over the breakdown (cuts, cut sets, references, voices in the
  cut); workflows; jobs (assemble, slice, revoice) followed by
  `wait_for_job`, which adopts what a job made.
- Paid generation (`generate`, `make_picture`) needs `max_usd` at or above
  the plan's estimate; the budget ceiling still holds.
- Not offered: deciding gates, choosing a take, approving the storyboard
  (SPEC-0009), and any write to authored files. A refusal is returned as an
  answer (`refused`), not an error, so the model can act on it.

## Consequences

- What Claude Code does lands with history, lineage, budget and revisions,
  and a person can see and undo it in the control room.
- The server runs its own job manager: a job it starts runs while the
  server runs. A workflow started there moves on when its jobs finish.
- Changing breakdowns or the screenplay through Claude Code still means
  editing files; a reviewed-diff tool is a later decision (CT-0045 option 2).
