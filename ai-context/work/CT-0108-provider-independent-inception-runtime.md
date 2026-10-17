---
id: CT-0108
title: Provider-independent Inception and production coordination
type: work
status: review
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
tags: [agent-runtime, inception, providers, coordination]
---

# What

Implement the Inception role inside the existing LangGraph / CoAgents Agent
Runtime, with whole-film context and selective specialist consultation. A
Production Coordinator should route a new film to Inception and an existing
film to the relevant stage. First remove the implicit Claude CLI assignment.

# Why

The director wants conversation-led creative development, agent-authored work
and concrete human review, not manual authoring forms or another executor.
Roles must not depend on the provider running a session. The present CLI
adapter starts independent headless requests; it does not attach to an open
Claude session. Treating its presence as a session assignment is incorrect.

# Done

- Implemented Coordinator entry/routing, Inception context/reason/tool nodes and
  bounded feedback inside the existing public `assistant` LangGraph CoAgent.
  The first specialist has real concept/screenplay/assessment application tools,
  not only a role prompt. Human gates and paid image generation are absent from
  its tool allowlist. Coordinator retains existing confirmed production tools.
- Added revision + whole-source-digest preconditions to agent publications,
  fixed agent attribution on the draft HTTP transport, current source refresh
  after successful work and explicit conflict receipts. Thread project mismatch
  and same-input completed-turn replay are refused without executing more work.
- GUI shows active role/stop state and rereads canonical records after writes.
  A saved human direction can initiate the next turn through the same CoAgents
  client; canonical decision identity/material is rechecked before reasoning.
  This is a human interaction handoff, not a persistent background dispatcher.
- Browser acceptance passed on a disposable film through the real Python /
  Node Copilot topology: chat -> actual draft/assessment -> human changes ->
  automatic same-CoAgent retained revision -> new review -> reload/mobile.
  Evidence: `/tmp/cine-toaster-inception-agent-h7nudkqk/`; screenshot inspected.
  Model answers were deterministic; no Demo 01 decisions or model quota used.
- Director authorised implementation of the Coordinator/event loop and first
  Inception specialist using the existing LangGraph/CoAgents runtime. Added
  SPEC-0015 before implementation; bounded reasoning/tool loop, shared writes,
  current material preconditions and human-only decisions are the first scope.
- Inspected the existing single `assistant` graph, model adapters, CoAgents
  transport and production-agent guidance. Provider independence and session
  binding already have architectural direction in SPEC-0001; concrete Inception
  tools/routing still need implementation.
- Removed the implicit Claude CLI default. Added per-host `--agent-provider`
  selection, preserving explicit environment configuration and injected Model
  adapters, with no process-wide environment change. Updated
  startup preflight, doctor guidance and assistant documentation.
- Director refined the policy during implementation: explicit host configuration
  takes precedence, but absent configuration should fall back to the current
  CLI. Implemented best-effort `CODEX_THREAD_ID` / `CLAUDECODE=1` detection,
  with conflicting signals requiring explicit selection. No executable/key scan.
- Added a Codex CLI adapter with isolated ephemeral requests, structured output,
  disabled shell/plugins/apps and no development working directory/instructions.
  Local 0.162.0 help and official non-interactive docs checked; no live inference
  or external session resumption has been claimed/tested.
- Added missing Inception mission/context/tool/human-gate direction and
  new-film versus existing-film routing policy to `docs/production-agents.md`;
  explicitly labelled execution/routing as pending rather than integrated.
- Corrected documentation: headless Claude CLI requests are not attachment to
  an already-open Claude session. No Codex/Claude session binding is claimed.

# To do

1. Director review of the conversational experience on Demo 01. Its pending
   real assessment/decisions are not to be approved by development tests.
2. Separate follow-ups: durable background dispatch/restart recovery and full
   SPEC-0001 thread/provider bindings; external reference research, image
   generation and additional specialised stage executors as needed.
3. Keep the earlier intermittent storyboard reopening failure visible until
   independently explained, even if this run passes.

# Decisions

- No parallel queue, scheduler, executor or production-workflow engine.
- Provider selection is operational configuration, not a film record or role.
  Priority: host flag, environment, current CLI signal. The current launcher
  selects only the CLI provider, not its thread/context/tool authority. No
  automatic selection from installed executables or credentials. No fallback
  to another provider on errors or invalid explicit configuration.
- Existing CLI/API adapters remain available when explicitly selected. Real
  attachment to an existing provider session needs an adapter implementing
  SPEC-0001 identity, isolation and resynchronization, not a guessed session ID.

# Validation

- Current implementation: 23 Inception tests passed, including real application
  writes/HTTP/AG-UI, new-film routing, delegation, human approval/guided revision,
  source/revision conflicts, replay/project guards, limits and post-commit read
  failure. An 86-test focused regression passed before the four final edge cases.
- Browser vertical slice passed through the real Copilot sidecar and graph with
  deterministic model responses; no fake graph or GUI-only authoring shortcut.
  Five frontend test files and the production build passed.
- Live provider smoke passed with `codex-cli`: role `inception`, stop
  `needs_direction`, Portuguese response and a question grounded in the disposable
  film's Mara narrative. No draft/assessment write or image generation occurred.
- Full regression passed: 1117 tests in 617.6 s, including heavy adapters and the
  previously intermittent storyboard reopening test. The first 19 Inception
  cases were in that run; four final edge cases and LAN-onboarding coverage were
  added later and verified in the final 97-test focused run (32.2 s).
- Final GUI continuation acceptance passed again after the activity-label /
  decision-handoff refinements: `/tmp/cine-toaster-inception-agent-pzr2v8ew/`.
  Assistant-off human-review regression passed:
  `/tmp/cine-toaster-inception-review-xq_wj0uh/`.
- Reloaded the actual Demo 01 server with `codex-cli` and the new graph; assistant
  info/GUI return HTTP 200. Real-film read-only browser inspection passed:
  `/tmp/cine-toaster-creation-live-f0cw4zbu/`. Creation revision 6, 13 references,
  zero concept drafts, one pending assessment, zero decisions and three drawings
  remain unchanged. Before/after source digest:
  `bf256fe23c37e42403aa62041b4af86f99da0dd123b67b8d69d270cfb529dfc2`.
- The director then requested trusted-LAN onboarding (CT-0109). Server is now
  bound to `0.0.0.0:8787`; WSL NAT/Windows forwarding remains a separate task.
- Earlier provider-only validation below is historical. Current completion
  covers the bounded interactive Coordinator/Inception slice, not the full
  workforce or durable autonomous dispatch.

## Earlier provider-selection validation

- 19 provider/adapter tests passed: precedence, current-CLI fallback, missing /
  ambiguous signals, invalid configuration, no credential/executable guessing,
  host injection, CLI transport, isolation/schema, timeout and redacted failures.
- Final focused regression passed: 48 tests (`test_agent_provider`,
  `test_assistant`, `test_doctor`, `test_cli`), with mocked model responses.
- Local fallback resolves to `codex-cli`; `codex exec --help`, feature listing
  and `toast serve --help` checked without inference. `git diff --check` passed.
- Full regression ran 1088 tests in 592.6 s with one failure: the existing
  `test_cut_decisions.StoryboardPhaseTests` final assertion after reopening the
  storyboard saw `production` instead of `fitting` (line 135, not the initial
  phase read). Isolated rerun passed all seven cut/phase
  tests together with all 19 final provider tests (26 total). No production or
  unrelated test code was changed to mask it; do not report the full run green.
  The full run's provider module executed before the fallback refinement, so
  the final focused reruns supplement it.
- Final fast regression passed: 1057 tests in 219.5 s, including all 19 final
  provider tests, assistant, doctor, CLI and the storyboard reopening test.
  `PYTHONPATH=src .venv/bin/python tests/run.py fast -j 4`.
- An initial focused run stalled inside the sandbox and was terminated; the
  authorised outside-sandbox rerun above passed. No production write, running
  server restart or real model call was performed for this change.
