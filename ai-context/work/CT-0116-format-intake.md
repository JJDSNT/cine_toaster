---
id: CT-0116
title: Format intake -- agents ask before advancing
type: work
status: review
owner: claude
created_at: 2026-10-17
updated_at: 2026-10-17
tags:
  - agents
  - inception
  - intake
  - decision-inbox
---

# What

SPEC-0020: a format's intake sheet, agent questions, human answers, the
inbox answer box, `toast intake`, MCP read/ask, and Inception's interview.

# Why

The author (2026-10-17): "Os agentes têm capacidade de perguntar quando lhes
faltar algum tipo de informação? (se você escolher fazer um videoclipe ele
lhe faz um questionário antes de avançar)". They could only stop with
`needs_direction` in chat; nothing knew what a format needs and nothing kept
the answer (CT-0112's informal-question gap). Model: KDP Studio's interviewer.

# Done

- `intake.py`: sheet resolution (declared style, else an answer naming a
  format, else the `format` question), `ask_intake` (agent, at most five open,
  one per item, re-ask names the answer), `answer_intake` (human, one per
  question), `intake_view`, `inbox_items`; validated in `load_creation`.
- `[[intake]]` sheets in seven format styles; `styles.py` keeps them.
- HTTP endpoints, `creation.intake`, decision-inbox `question` items, CLI
  `toast intake`, MCP `read_intake` / `ask_intake_questions`.
- Inception: `ask_questions` tool, interview instruction, sheet in its digest.
- GUI: `IntakeAnswer` in the decision inbox; the last answer continues the
  conversation with `resume: {intake, message}`; the Coordinator routes it to
  Inception (`resumed_intake`).
- `tests/test_intake.py` (11), MCP tool assertions.

# To do

1. Real-model interview on a disposable film (paid model call: ask first).
2. Sheets for films without a format style (short, feature) if Demo 01 shows
   the need; today they get the `format` question only.

# Decisions

- The sheet lives in the format style, beside the format's other rules: one
  owner per format; the production's free-text `format:` is evidence only.
- An answer is never written by an agent (no MCP answering tool); the CLI
  user and the inbox are the person.
- An answer naming a format does not edit `style:`; declaring it is separate.

# Validation

- `tests/test_intake.py`, `test_mcp.py`, the agent modules: OK.
