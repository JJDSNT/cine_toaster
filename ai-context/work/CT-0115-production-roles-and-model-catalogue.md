---
id: CT-0115
title: Production roles as declarations, a model catalogue, and generation operations
type: work
status: doing
owner: claude
created_at: 2026-10-17
updated_at: 2026-10-17
tags:
  - agents
  - agent-runtime
  - models
  - runpod
  - comfyui
---

# What

Review of the agent work of CT-0108..CT-0114 and the structure for the roles
that follow, ADR 0034. In this record:

1. Model capabilities declared by adapters, image input on every adapter that
   can carry it, a model catalogue, optional per-role model binding.
2. Role declarations and one per-role `work` map in the CoAgent state instead
   of ~35 prefixed fields, with behaviour unchanged.
3. Roadmap entries for every limitation found, with how to solve it.

# Why

The author asked for a review "mainly of the agents" and a plan for which
agents exist and how they are structured, including whether a RunPod/ComfyUI
agent makes sense. Second instruction (2026-10-17): Cine Toaster stays
model-agnostic and uses the model the person supplies; it may keep a table of
models, their capabilities and strengths. Look at KDP Studio for insight.

# Review findings (2026-10-17)

Good: commands only, human gates untouched, revision/source-digest
preconditions, fresh reviewer calls, honest limits. Fast suite 1169 OK.

1. One graph with one state of ~35 role-prefixed fields; the Coordinator
   resets all of them; each role edits state, reset, routing and edges.
2. Decision resume is encoded in a human message id
   (`decision-<id>-<attempt>`) cross-checked with page-context strings.
3. Each reasoning step re-serialises the whole context, truncated mid-JSON by
   `bounded()`; each is a fresh CLI subprocess (up to 8 x 180 s per turn).
4. Only the Codex CLI adapter carried images, detected by duck typing.
5. One model for every role; the "independent" reviewer is the same model.
6. The Art Direction wait is 25 s; a RunPod cold start is minutes, so work
   stops until the next human message.
7. Minor: duplicate `scene` key in the Inception schema; prompts spend many
   words forbidding what the code already prevents.

KDP Studio insight (its ADR 0018-0020): agents as manifests (role, fixed
readers, report-or-edits output landing through one command); one flow for
every agent (draft -> named deterministic checks -> land -> hold with
critique/redo/done); the wait checkpointed beside the job store and
survivable across restarts; an unattended critique loop of eight minutes was
judged wrong by the author -- nothing is redone unasked; images travel inside
the message for both Claude adapters.

# Done

- ADR 0034 written; `agent-architecture.md`, `project-status.md` and the
  roadmap (§ Agent Runtime structure) updated with every limitation found.
- `agents/models.py`: `capabilities` per adapter, `supports()`; images on
  Claude CLI (stream-json, as KDP Studio) and Claude API; one shared bound
  check for every adapter (checked before anything is sent); optional
  `model` for both CLIs (`--model`).
- `agents/roles.py`: role declarations; the `Assistant` state and the
  Coordinator's reset derive from them; module budgets read from them; the
  delegation enum from `DELEGATIONS`. Duplicate `scene` key removed.
- `agents/catalog.py`, `agents/model_catalog.yaml`: the catalogue, the
  person's file on top, role bindings (`adapter[:model]`).
- Art Direction takes a `reviewer` model for Visual Prevalidation; Directing
  takes `auditor` and `reviewer`; `build(..., models=)`; the server binds
  roles through the catalogue; a broken binding file is reported by
  `unavailable_reason()`.
- `toast doctor`: "Agent roles" replaces "Visual prevalidation" and names the
  roles the supplied model serves or cannot serve.
- Tests: `tests/test_agent_roles.py` (15), and a role-bound reviewer case in
  `test_art_direction.py`.
- Typed resume (step 1): agent state `resume` = {decision, message} set by
  `Assistant.tsx` with the continuation message; `assistant.resumed()`
  accepts it only for that message; consumed by the Coordinator each turn.
  The page-context entries "Inception decision id" / "Direction continuation
  attempt" are gone. Tests moved to the typed input; one AG-UI-level test
  proves the state reaches the graph through `ag_ui_langgraph`. `make ui` rebuilt.
- One reasoning step (`agents/loop.py`): the three roles' copies of
  budget/ask/validate/delegate/respond replaced by a declared `Loop` each;
  failure messages unified ("Não consegui avançar este trabalho: ...");
  `LoopTests` added.

# To do

0. Format intake / interviewer (the author's question, 2026-10-17): agents can
   stop with `needs_direction` but no format sheet says what a music video
   needs, and questions live only in chat. Roadmap entry written.
1. ~~Typed resume~~ done.
2. Role-specific digests instead of truncated JSON; native tool calling where
   an adapter supports it (finding 3).
3. Generation recipes; Generation Operations role; continuation on job
   completion with a checkpointed wait (findings 6, ADR 0034 point 5).
4. Development skill `.agents/skills/runpod-comfyui/`.
5. Sequence Adherence reviewer (SPEC-0019); further authors as Demo 01 needs.

# Decisions

- No "RunPod agent": infrastructure provisioning stays outside the product;
  generation operations is a production role with Cine Toaster tools.
- Cine Toaster never selects a model; the catalogue describes, a person binds
  (the author, 2026-10-17: agnostic, uses the model the user makes available).
- Roles keep their prefixed scratch fields for now, declared with the role,
  rather than one nested `work` map: same decoupling, no reducer, behaviour
  and tests unchanged. The single role loop is the next structural step.
- Behaviour-preserving refactor first, guarded by the existing agent tests.

# Validation

- Before the change: `tests/run.py fast`, 1169 tests OK.
- After: agent modules (145 tests) OK; `tests/run.py fast`, 1184 tests OK
  in 204 s. `toast doctor` under Claude Code: "Agent roles ok (claude-cli;
  serves all seven roles; inference and login not verified)".
- Not done: heavy suite; a real-model image call on Claude CLI/API (scripted
  only; roadmap entry).
