---
id: CT-0045
title: Letting Claude Code do the work through Cine Toaster, as in SINGULAR (later)
type: work
status: proposed
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
