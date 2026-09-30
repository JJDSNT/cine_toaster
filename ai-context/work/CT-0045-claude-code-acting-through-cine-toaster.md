---
id: CT-0045
title: Letting Claude Code do the work through Cine Toaster, as in SINGULAR (later)
type: work
status: doing
owner: unassigned
created_at: 2026-09-30
updated_at: 2026-09-30
tags:
  - agents
  - mcp
  - claude-code
  - future
---

# What

The user made SINGULAR by letting Claude Code do the work: write the
breakdowns, build tools, run generations. They asked (2026-09-30) whether the
assistant can do the same. It cannot, by design. It reads everything, points
and navigates, and changes the film only by starting or resuming a workflow
after a yes (ADR 0017, 0018). This record keeps the options for later, as
the user asked.

# Options, in the recommended order

1. **Claude Code through an MCP server of Cine Toaster.** The person keeps
   working with Claude Code as in SINGULAR. Instead of loose file edits and
   ad hoc scripts, it calls Cine Toaster's commands and queries as MCP tools:
   - generate a picture or a block, within the budget;
   - start or resume a workflow;
   - revoice, slice, assemble;
   - read the production, the scenes and the knowledge.

   Everything then lands with records, lineage and budget, and gates stay
   the person's. Almost everything exists in `toast` already; what is
   missing is the MCP surface. This is the recommended first step.
2. **More assistant actions, one at a time,** each a command confirmed in
   the chat:
   - proposing breakdown or screenplay changes as diffs the person accepts
     (ADR 0016);
   - generating a picture or a block;
   - proposing (never selecting) a take.
3. **The assistant delegating long tasks to Claude Code** in the
   background, for example "redo 1-02B's breakdown with geography". It would
   run headless, with permissions limited to Cine Toaster's commands, and
   the person would follow it and approve. This is the most powerful option
   and needs a careful spike: permissions, authored files (ADR 0006/0016),
   and cost.

# Constraints

- Development-agent guidance (`AGENTS.md`, `ai-context/`) and production
  agents stay separate. A Claude Code session working on a film uses the
  product's commands, not the repository's memory.
- Authored files are changed by a person, or accepted by a person as a
  diff.
- Gates are never decided by an agent (SPEC-0009).

# Done (2026-09-30): option 1, the MCP server

- `src/cine_toaster/mcp_server.py`: `MCPServer` (mcp 2.2, the optional
  `mcp` extra, `make install-mcp`) with 27 tools over a `LocalRuntime` that
  gives the assistant's reads (`agents/reads.py`) the same surface as its
  HTTP client, and runs commands through `dispatch` with the actor
  `claude-code` (agent). Tools carry MCP annotations (read-only, paid as
  open-world). Refusals return `{"refused": message}`.
- `toast mcp <project> [--env-file]`; `toast doctor` reports "MCP server";
  ADR 0020; `docs/mcp.md`.
- Paid tools need `max_usd` covering the plan's estimate, checked before
  anything is submitted.
- Not offered, by design: gates, take selection, storyboard approval,
  authored-file writes.
- Found while testing: the control room's `runCommand` sent no actor, so
  take selections and the voice switch were recorded as `unknown`; it now
  defaults to `control-room` (human).

Validation:

- `tests/test_mcp.py` (5): the tool list and what is excluded; reads; a
  decision recorded as claude-code and refusals as answers; the paid cap
  refusing before any submit; an assembly job followed and adopted.
- Real run: Claude Code 2.1.285, `claude -p --mcp-config ... --strict-mcp-config
  --allowedTools "mcp__cine-toaster__*"` on the SINGULAR scratch copy (the
  user's configuration untouched). Asked, in Portuguese, to read the film
  and 3-01, summarise its findings, decide the cut into P2 as a match with a
  reason, and assemble a version: all four done in 1 min 42 s. `state.json`
  holds the cut with `decided_by: claude-code (agent)` and version v2 with
  its summary.

Remaining: option 2 (reviewed diffs for breakdowns and the screenplay) and
option 3 (the assistant delegating to Claude Code) stay for later.
