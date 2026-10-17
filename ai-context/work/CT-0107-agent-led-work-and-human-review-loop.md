---
id: CT-0107
title: Close the agent work, human review and continuation loop
type: work
status: review
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
tags: [agent-runtime, workflow, human-gates, gui, demo-01]
---

# What

Make the director's agent-led workflow executable, not merely visible. For
authorised active work, the agent must either proceed toward a complete scoped
deliverable or raise a concrete human decision/request. The human GUI explains
the situation and supports review, rejection and direction; it is not a form
surface for doing the agent's work.

# Why

The director identified a third invalid state after CT-0106: artifacts exist,
but neither agent work nor a review request exists. Removing forms and showing
three storyboard drawings did not close the production loop. Do not present
that read-only slice as a functioning agent-led workflow.

# Done

- Director simplified and authorised the first slice: Inception assesses
  sufficiency separately for the next steps, explains gaps and recommends a
  scoped direction with Approve / Request changes. Implement that concrete
  assessment/decision boundary first, not a new generic orchestration framework.
- Implemented retained agent assessments and human direction decisions in the
  existing Creation journal, shared Core/CLI/HTTP operations, MCP assessment
  authoring and bounded assistant reads. No agent approval tool is exposed.
- The Inception panel now shows sufficiency per destination, actionable gaps,
  a scoped recommendation and Approve / Request changes. Human guidance is
  shown only when requesting changes; no authoring forms return.
- Demo 01 assessment `assessment_ae93080d82564323` is retained at Creation
  revision 6, pinning 13 references, the screenplay and three drawings. It
  recommends developing the opening, while masters need identity/composition
  work. No human decision, image generation or scene-gate change was performed.
- Final director constraint: the intended executors are runtime CoAgents.
  Reuse/extend the existing LangGraph Agent Runtime and built-in production
  workflows; no parallel executor, queue, scheduler or workflow engine.
  Inspection found one registered `assistant` graph; specialised roles in
  `docs/production-agents.md` remain documented as pending implementation.
- Nine focused review tests and all 14 Creation regression tests passed:
  human/agent authority, guided reassessment, conflicts, drift, corruption,
  failed commits, HTTP and CLI. Frontend build, full regression and real-film /
  disposable browser acceptance passed; see validation below.
- Read the built-in workflow/gate contract and inspected the Agent Runtime.
  Existing block workflows advance on job completion and gate decisions, but
  cover picture/video/take production, not concept/storyboard draft review.
- The embedded assistant's ACTIONS currently contain start/resume workflow and
  cut proposals; it can read Creation/storyboard, but cannot independently
  execute their full authoring/review/continuation lifecycle. MCP write tools
  do not establish an autonomous embedded-copilot workflow by their existence.
- Live read-only audit of Demo 01: zero queued/running jobs, three storyboard
  candidates; SC-010 is fitting, has no gates and no open decision questions.
  The absence of an active job alone is not proof of agent idleness, but this
  audit plus the unsupported authoring loop confirms the missing handoff.
- Recorded the director's production requirement and prioritised this loop
  ahead of more gallery polish or generating the other 21 shots.

# To do

1. Obtain the director's review of the implemented readiness/decision slice.
2. Connect authorised continuation to the existing Agent Runtime/CoAgents and
   built-in workflows. Extend missing role/tool capabilities there, not through
   a second executor. Retained next-agent instructions are not dispatched jobs.
3. Give actual runtime tasks scope, ownership, completion criteria, exact inputs
   and observable transitions; retain permission/quota gates and disclose an
   unavailable capability instead of inventing running work.
4. Extend cross-module visibility from these same production records, keeping
   direction decisions distinct from final storyboard/master approvals.
5. Validate actual CoAgent continuation separately: scoped work -> human
   decision -> authorised next work, or guided revision -> new request,
   including restart/failure. Current acceptance does not prove autonomous work.

# Decisions

- Store agent-authored readiness judgments and human decisions as retained
  records in the existing Creation journal. Pin the production material used
  for the assessment and refuse stale approval. Human direction approval is
  not a final storyboard/cast-master approval, a generation permission or proof
  of a running agent. No new model/provider call is needed for this slice.
- The operating rule applies to active authorised work. Completion, explicit
  user pause/cancellation and a concrete permission/capability failure are
  legitimate visible stops, not permission for infinite work or invented jobs.
- Ask the human only for a real creative decision, necessary direction or
  authority the agent lacks. Missing outputs or fixable technical warnings
  are work for the agent, not automatically human decision requests.
- Completeness is scoped: a reviewable opening sequence can be a delivery
  without finishing the whole film. The approval must say what it authorises;
  three draft previews do not imply approval of all 24 plans or finished masters.
- The director explicitly does not require generating all 24 drawings now.
  Do not launch additional generation to hide the workflow gap.
- Only the first assessment/direction-decision slice is delivered. No autonomous
  continuation, new execution mechanism or specialised runtime workforce is
  claimed. No production gate, approval, human rejection or run is fabricated.

# Validation

- Full regression passed: 1079 tests in 635 s, including heavy adapters;
  `PYTHONPATH=src .venv/bin/python tests/run.py -j 4`.
- Nine new review tests, 14 Creation tests and nine MCP tests passed. Five
  frontend test files and production build passed; pre-existing large-chunk /
  inlineDynamicImports warnings remain. `git diff --check` passed.
- Disposable browser acceptance passed: approval, mandatory change guidance,
  conflict with retained text, changed-material reassessment, reload, history,
  assistant disabled and mobile layout:
  `/tmp/cine-toaster-inception-review-fbdsdhxq/`.
- Real Demo 01 read-only readiness inspection passed:
  `/tmp/cine-toaster-inception-review-znplbk2q/`; screenshot visually inspected.
  Earlier attempts raced frontend rebuild/cold load and were not successful
  checks; reran after the build with an explicit loading wait.
- Existing 13-reference/round/chat-context inspection passed:
  `/tmp/cine-toaster-creation-live-ms62rqf5/`. Storyboard/input/navigation
  regression passed: `/tmp/cine-toaster-storyboard-review-et5rzgp1/`.
- No browser test decided the real film or called a model. The only production
  write appended the assessment to the existing Creation journal; previous
  records/images are preserved. Automatic dispatch was not implemented/tested.
  Server remains at `http://127.0.0.1:8787` with the existing assistant enabled.
