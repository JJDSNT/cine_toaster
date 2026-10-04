---
id: CT-0059
title: A minimal continuity ledger -- what holds from scene to scene
type: work
status: done
owner: unassigned
created_at: 2026-10-04
updated_at: 2026-10-04
tags:
  - continuity
  - script-supervisor
---

# What

Backlog "Next": the first slice of the Script Supervisor role
(`docs/production-agents.md`). The geometry checks read one scene. This
ledger reads the film in order and carries forward what a scene leaves behind:
cast variants, declared facts (wardrobe, injuries, carried objects, prop or set
state), time and weather. It answers the open question "What is the minimum
continuity ledger Singular actually needs?" with the least that catches real
breaks and can be declared by hand.

# Done

- `continuity.py`:
  - `parse` reads the scene's `continuity:` block (continues, time, weather,
    facts, changes at a shot, exceptions with a reason).
  - `ledger` walks the film in order.
  - `state_at` gives what holds at a shot; `describe` and `render_text` print
    it.
- Findings in the scene, registered in `CHECK_CODES`:
  - `continuity_break` (warning): a declared continuation contradicts a fact.
  - `continuity_unconfirmed` (advice): inferred only, in the same place with
    nothing said, phrased as a question.
  - `continuity_problem` (error): the block cannot be read.
- Every fact keeps its source: `cast` (the scene's variant) or `declared`.
- The video and picture plans carry `continuity` (what holds when the shot
  begins). The dry runs print it, and it is not sent to the model.
- Access: `toast continuity <project> [--scene S [--shot P]] [--json]`,
  `GET /api/continuity`, MCP `continuity_ledger`.
- `docs/continuity-checks.md` § "What holds from scene to scene".

# Decisions

- **Declared, not extracted.** Wardrobe written in variant prose is not
  parsed: guessing from prose would accuse correct scenes. The cast variant is
  the one fact read automatically.
- **Inference stays a question.** It is an advice finding that disappears once
  `continues` is declared either way, keeping the rule "a checker that guesses
  will eventually accuse a correct scene".
- **Time and weather** compare only with the immediately previous scene, never
  an older one.
- **Not sent to the model.** Continuity facts are not added to the prompt: what
  the prompt says stays the author's. The plan shows the facts beside it.

# Validation

- `tests/test_continuity_ledger.py`: 10 tests, including a production copy
  whose declared continuation breaks. `tests/test_mcp.py` checks the tools.
- On the scratch SINGULAR copy, one real question appears. Kael is `kael` in
  1-02 and `kael_genebra` in 1-02A, in the same room, with no join declared.
  The two variants describe different faces (green eyes and a scar, against
  tired grey-green eyes and a narrow face). That is for the author.

# Remains

- A continuity room in the control room. The text, API and MCP are enough
  until it is used.
- Optionally injecting declared facts into prompts, as an opt-in. That is the
  author's call.
- Continuity from footage (comparing frames) is out of scope: the checks read
  the plan, not the footage.
