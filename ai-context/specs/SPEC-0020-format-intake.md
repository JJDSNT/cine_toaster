---
id: SPEC-0020
title: Format intake -- the agent asks what a format needs, a person answers
type: specification
status: accepted
implementation: complete
owner: project
created_at: 2026-10-17
updated_at: 2026-10-17
---

# Contract

## The sheet

A format style (`style_assets/<id>/style.toml`, `kind = "format"`) may carry
`[[intake]]` items: `id`, `ask`, `why` (what it matters for) and `unlocks`
(one of inception, screenplay, storyboard, masters, clips, assembly, budget);
`required` defaults to true. An item without a reason or a stage is refused.
The format in force is the production's declared `style:` format, else an
answer to the `format` item that names a catalogue format; a film with
neither gets one item, `format`. The production's free-text `format:` is
shown as evidence, never parsed into a style.

## Records

In the Creation journal (`creation/state.json`), validated on every read:

- `intake_questions`: id, item, question, why, format, based_on, agent actor,
  asked_at. Asked through `ask_intake` by an **agent** only; at most five open
  at once; one open question per item; asking an answered item again names
  that answer in `based_on`.
- `intake_answers`: id, question, answer (the person's words, kept as typed),
  **human** actor, answered_at. One per question, through `answer_intake`.

No record edits the production. An answered sheet is not an approval and
creates no gate.

## Surfaces

- HTTP: `POST /api/creation/intake-questions` (agent), `/api/creation/intake-answer`
  (human); the view is `creation.intake`; open questions are decision-inbox items
  of kind `question` with action `answer`.
- CLI: `toast intake PROJECT [--answer QUESTION TEXT] [--json]` (the person).
- MCP: `read_intake`, `ask_intake_questions`; no answering tool.
- Agent Runtime: Inception's `ask_questions` tool and interview instruction;
  the sheet with statuses is in its creation digest. After the last open
  question is answered in the inbox, the page continues the conversation with
  a typed `resume: {intake, message}` that routes the turn to Inception.

# Validation

`tests/test_intake.py`: sheet resolution, agent/human authority, limits,
re-asking lineage, inbox items, forged answers refused on read, CLI answer,
Inception interviewing and continuing after an answer.
