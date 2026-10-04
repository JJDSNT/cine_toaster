---
id: CT-0057
title: Producer status -- where each sequence stands
type: work
status: done
owner: unassigned
created_at: 2026-10-04
updated_at: 2026-10-04
tags:
  - producer
  - analytics
---

# What

Backlog "Now" item 3: the first slice of the Producer role
(`docs/production-agents.md`). It gives a deterministic status per sequence and
scene, read from the records Cine Toaster already keeps, and it is also the
first seed of Studio Analytics (`docs/studio-analytics.md`). No model is asked,
nothing is written, and nothing is decided.

# Done

- `producer.py`: `scene_status`, `production_status`, `render_text`.
- Shots in the cut are counted as `chosen`, `one_take` (its only take goes to the
  cut), `awaiting_choice` (more than one take, none chosen),
  `awaiting_generation` or `composed` (made at assembly).
- Each scene shows its latest version and verdict and its approved version.
- Blockers are error findings, gates waiting for a person and declared
  blockers.
- The next decisions are: judge the latest version, choose takes, answer open
  questions, generate missing shots.
- A decision is open until its status is settled. A proposal (`proposed` with an
  answer) still waits for the author.
- `toast status <project> [--sequence ID] [--json]`, `GET /api/status`, MCP
  `production_status`, and a "where it stands" panel in the Sequences room.

# Decisions

- Built on the shot `status` that `project.py` already derives, so the report
  and the rooms cannot disagree.
- Out-of-cut shots are not counted.
- A "Next decisions" list reports and never ranks: priority stays the author's.

# Validation

- `tests/test_producer.py` (8 tests).
- Run on the scratch SINGULAR copy:
  - Genebra: 163 shots in the cut, 135 on their only take, 2 waiting for a
    choice, 17 awaiting generation (all in 1-02A, half-generated in SINGULAR
    itself), 0 of 7 scenes approved.
  - Boreal: 3-01 approved at v12 with 11 takes still unchosen; 3-02 not
    generated.
- Full suite before commit.

# Remains

- Cost per sequence once FinOps records reconciled costs (item 4).
- Time in each stage, and history of the status, from `history.jsonl`.
