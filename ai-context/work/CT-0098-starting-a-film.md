---
id: CT-0098
title: Starting a film -- `toast new` and a guide a production agent can read
type: work
status: doing
owner: claude-code
created_at: 2026-10-16
updated_at: 2026-10-16
tags:
  - onboarding
  - cli
  - agents
  - mcp
---

# What

A person or an agent can start a film from nothing, or from a screenplay,
and learn how to work on it, without reading this repository's memory:

1. `toast new <dir> --title ... [--screenplay file.fountain|.fdx]`: a new
   production in the native format, outside the checkout. Given a
   screenplay, one breakdown per screenplay scene, linked by heading and
   with no shots yet -- the start of phase 1.
2. `docs/making-a-film.md`: the product guide -- the production's folder,
   the two phases and the gate between them, the commands for each step,
   what is the director's.
3. The guide and the filmmaking practices reachable through the MCP server,
   and the two phases in its instructions.
4. Examples that name no particular film (`docs/mcp.md`, `mcp_server.py`).

# Why

Asked by the user on 2026-10-16: does the repository onboard an agent well
enough to understand the flow and use the tool? For development agents,
mostly yes. For an agent working on a film, no: there was no way to create
a production (only `demo`, `import-fdx`, `migrate singular`), the phases
lived only in `ai-context/production-flow.md` -- which a production agent
must not read -- and the MCP surface assumed a film that already exists.
The examples pointed at SINGULAR, which is one validation case, not the
product's boundary.

# Done

- `toast new <dir> --title [--screenplay] [--id] [--logline]`
  (`new_production.py`): `project.yaml`, `story/screenplay.fountain` (an
  FDX converted, its losses reported), and per screenplay scene a breakdown
  `scenes/NNN-<slug>/scene.yaml` linked by heading (with `occurrence` when a
  heading repeats) and `shots: []`. Refuses a non-empty directory and the
  source checkout.
- `docs/making-a-film.md`: the folder, authored files against decisions,
  phase 1, the storyboard gate, phase 2, what is the director's, working
  with an agent. Packaged in the wheel (`cine_toaster/guide/`).
- MCP: the two phases and "do not spend on a scene whose storyboard is not
  approved without saying so" in the instructions; `how_to_make_a_film`,
  `list_practices`, `read_practice` as reads.
- Generic examples: `docs/mcp.md` and `mcp_server.py` no longer name
  SINGULAR or its folders; README "Get started" shows `toast new`.
- `CLAUDE.md` = `@AGENTS.md`, so Claude Code loads the development guidance
  without being asked.
- A test that every command the guide names exists in the CLI.

# To do

The rest is in the roadmap, § "Starting a film and onboarding a production
agent": a pointer in the film's folder, git for the film's text, the MCP
surface for phase 1, breakdowns for scenes added to the screenplay later.

# Decisions

- Breakdowns created from a screenplay are new authored files written once,
  at creation; the runtime still never rewrites an authored file (ADR 0006).
- Scene ids follow the demo's `SC-010` pattern, ordered by tens, so scenes
  can be inserted between them.

# Validation

- `tests/test_new_production.py` (6): empty production loads; a screenplay's
  three scenes become linked breakdowns, the repeated heading with
  occurrence 2, uncovered dialogue reported; a non-empty directory and the
  checkout refused; the CLI path; the guide's commands exist.
- `tests/test_mcp.py`: the guide, the practices and a refused unknown
  practice, all read-only.
- By hand: `toast new` on The Last Signal's screenplay, then `toast check`,
  `toast script show`, `toast storyboard approve`, `toast status` on it.
- `make test-fast` (2026-10-16): 989 tests, OK, in 2.7 minutes. Run before the
  guide-drift test was added; that test passes on its own. `make test` (the
  heavy part) not run: nothing here touches an adapter.
- The checkout had no `.venv`; `make install` and `make install-mcp` made it.
