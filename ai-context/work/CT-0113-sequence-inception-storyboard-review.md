---
id: CT-0113
title: Sequence-level Inception to storyboard comparison and review
type: work
status: doing
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
tags: [sequence, human-review, inception, storyboard, agent-runtime]
---

# What

Make the sequence the work/review unit: expose original Inception inputs,
ordered screenplay/shot/drawing evidence, explicit gaps and a separate agent's
adherence/continuity findings. Reuse the current CoAgent and shared commands.

# Why

The director cannot judge narrative adherence from an isolated scene image.
ADR 0008 already establishes sequence review; recent scene-level handoffs did
not implement it. The director authorised advancement and inspection of Singular.

# Done

- Read current boundaries/specifications and ADR 0008. Confirmed the first
  Singular sequence is Genebra, 1-01 through 1-04 including 1-02A/B/C, not
  independent scene deliveries. Demo 01 declares The Ascent across seven scenes.
- Inspected Singular read-only: nine scenes, 242 shots, no retained Inception
  drafts/references or storyboard-candidate journal. Existing production media
  must not be relabelled as reviewed storyboard evidence.
- Prior CT-0112 full regression completed: 1186 tests, 685.8 s, OK; the final
  focused run separately includes the later explicit-continuation test.
- Director clarification: production agents, not only development memory, must
  know this work structure. Added a shared product work contract and read-only
  canonical sequence projection to Coordinator/Inception/Art context and to
  Directing/Continuity, including the fresh independent reviewer. A focused
  scene never removes the complete parent sequence membership. An explicit
  `work_structure` read accepts canonical sequence/scene IDs and rereads the
  addressed production. No Singular-specific range is hardcoded.
- Updated the product-facing filmmaking guide (also served as the existing
  MCP `how_to_make_a_film` resource) and assistant guide with the same scope and
  flow, rather than requiring an external production agent to read development
  memory. Clearly distinguish this context slice from an executed review.
- The existing MCP server also exposes the same read-only `read_work_structure`
  projection, and its startup instructions carry the shared contract. This
  gives external production agents executable canonical scope, not only a guide.
- Removed a premature import of the not-yet-implemented sequence record reader;
  no empty persistence implementation is substituted for the missing review.

# To do

1. Investigate Singular preproduction startup/read performance before claiming
   its full GUI walkthrough passed; sequence room inspection succeeded.
2. Implement original-source/beat/drawing comparison and independent review,
   source freshness, incomplete-work ownership and sequence-first GUI.
3. Validate disposable films and read-only real productions, then full regression
   and one announced Demo server activation. Preserve all images and human gates.

# Decisions

- Sequences come from the production's existing manifest, never inferred from
  scene titles or truncated to what currently has pictures.
- No production writes or project switch for inspecting Singular. Use a local
  read-only inspection server; Demo 01's LAN URL remains its own project.
- Original Inception sources, not only a creator-authored art brief, anchor
  independent criticism. Missing intent/mapping/drawings/inspection means no
  readiness approval request. Partial scene studies remain useful internal work.
- No new provider, scheduler, invented image inspection or human approval.

# Validation

- Ten new deterministic context tests and four focused graph cases passed
  (14 tests, 3.4 s). They cover exact subdivision/order, focused/unknown scopes,
  unassigned/ambiguous membership, cross-project rereads, truncation and no
  mutations/inferred approvals. Graph assertions inspect actual Coordinator,
  Inception and fresh Continuity/Visual-review inputs, not merely prompt constants.
- A first graph assertion incorrectly expected the generic fixture's sequence
  in the separate Shapes film. Corrected it to inspect Shapes' actual identity
  and explicitly empty grouping; the focused rerun passed.
- The broad sandboxed focused run was interrupted after read waits; the full
  suite is running outside the sandbox (local sockets/renderers). Its Inception
  module (24 tests), Directing graph (10) and handoff module (15) already passed.
- Actual Demo read through RuntimeClient + `work_structure` returned project
  demo-01, focused SC-010, parent the-ascent with all seven scenes / 24 shots.
  No model invocation or production mutation.
- Read-only Singular browser reached its real sequence room and confirmed all
  seven Genebra scene entries, with screenshot
  `/tmp/cine-toaster-singular-sequence-lzdu4rlt/01-canonical-sequences.png`.
  A redundant subsequent production query timed out under concurrent heavy
  rendering; the full preproduction walkthrough is not yet passed. The temporary
  server rejects all mutation methods and does not replace Demo's LAN server.
- Compile check and `git diff --check` passed.
- MCP regression passed separately (10 tests, 45.1 s); the full suite also
  passed this module after the tool addition. It checks read-only annotations,
  exact scene membership and the guide, without adding creative decision tools.
- Full regression passed: **1199 tests in 653.9 seconds**, including heavy
  adapters. No frontend code changed in this context slice.
- Final Singular inspection captured the actual sequence response: Genebra
  contains 202 shots in its seven canonical scene entries, screenshot in
  `/tmp/cine-toaster-singular-sequence-l_abi0b2`. The scene-first preproduction
  page stayed at "Opening the production" beyond 120 s under concurrent heavy
  testing. Record this limitation rather than claim a passed full walkthrough.
  Temporary inspection servers stopped; no mutation API was enabled.
- After confirming zero jobs and announcing the activation, performed one
  graceful Demo restart with the same LAN bind and `codex-cli` adapter. New
  host session: 86552. Demo identity and assistant discovery responded; LAN
  `http://192.168.100.179:8787/app/creation.html` returned 200. No Windows rules
  were changed and phone reachability itself was not retested.
