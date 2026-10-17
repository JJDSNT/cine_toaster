---
id: CT-0111
title: Directing, shot planning and continuity agents
type: work
status: review
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
tags: [agent-runtime, directing, continuity, storyboard]
---

# What

Add Directing/Shot Planning and Script Supervisor/Continuity roles to the
existing Production Coordinator's public CoAgent. Save retained scene shot-plan
proposals and independent evidence-based continuity reports; display and review
them beside the screenplay/storyboard without manual authoring forms.

# Why

The director authorised the next specialists, clarifying that the Production
Coordinator already exists. This closes part of the intention/art -> filmable
shot proposal gap, not another orchestration or Producer agent.

# Done

- Inspected existing continuity ledger, geometry/coverage checks, candidate
  journals, human direction gate, public CoAgent and preproduction GUI.
- Confirmed existing `continuity.py` is authoritative for declared continuity;
  do not duplicate its facts in an agent-owned ledger.
- Added SPEC-0017 / ADR 0031, shared Core/HTTP commands and versioned proposal /
  advisory review records with revision, source, lineage and evidence checks.
- Wired the existing Coordinator/Inception to Directing and canonical Continuity;
  a separate fresh reviewer receives records, not creator conversation.
- Added preproduction read-only proposal/report display, canonical human gate
  continuation and production-update refresh without interrupting the iframe.
- Real public CoAgents/HTTP/browser acceptance passed on a disposable film:
  saved proposal -> independent review -> human changes -> retained second
  version -> new review, reload/mobile, no manual authorship form or film writes.
- Checked Demo 01 read-only: revision 6, original source digest
  `bf256fe23c37e42403aa62041b4af86f99da0dd123b67b8d69d270cfb529dfc2`,
  zero direction proposals/reports. Its selected opening context fits the
  bounded model input (22,439 characters), while whole-film context is larger.
- Activated with one announced graceful restart after confirming no jobs:
  same `codex-cli`, bind `0.0.0.0:8787`, Windows LAN GUI HTTP 200. No Windows
  network rules or production files changed. Session chat memory is disposable.

# Remaining

1. Director review of actual film proposals remains open; no claim of artistic
   acceptance, canonical promotion or a complete generated storyboard.
2. Specify the proposal -> canonical shot/image handoff before implementing it;
   do not treat scoped proposal approval as an implicit promotion command.

# Decisions

- Reuse the Coordinator, model adapter, Creation journal and existing ledger.
- First scope: linked existing screenplay scenes, including those without
  canonical shots. Proposal IDs/coverage are pinned to their script version;
  proposal approval does not rewrite shot manifests or approve a storyboard.
- Textual/canonical continuity review is not pixel inspection. Preserve
  authored facts, computed checks, inference, uncertainty and human exceptions.
- No new scheduler, image-generation path, authority to approve gates or
  automatic canonical shot/screenplay promotion.

# Validation

- First focused regression: 60 agent tests passed (40.3 s).
- Frontend: all five test files passed; TypeScript/Vite builds passed, with
  existing bundle-size/deprecated-build-option warnings.
- Browser evidence: `/tmp/cine-toaster-directing-agents-h5z1vmb1`;
  screenshot inspected. Canonical decisions were made only on the fixture.
- Expanded directing suite: 23 tests passed (29.6 s), including existing-ledger
  exceptions, declared source changes, scenes without canonical shots,
  independent corrections, scoped review, approval boundaries and replay limits.
- Art browser regression passed: retained briefs/reviews, actual raster input,
  public CoAgent, gate, reload/mobile. Evidence:
  `/tmp/cine-toaster-art-agents-pnfij3fs`.
- Explicit Inception -> selected-scene handoff test passed after adding the
  scoped delegation field. The old sandbox-only run was interrupted after
  restricted HTTP caused a hang; the equivalent external regression passed.
- Live HTTP readback confirms the unchanged Demo 01 revision/source digest
  and zero directing test records.
- Final complete regression: **1172 tests in 583.3 seconds, OK**, including
  heavy adapters and all 23 directing tests. `git diff --check` passed.
- Read-only live LAN browser walkthrough passed: screenplay/shot navigation,
  composition studies, second scene, reload/back, actual assistant availability,
  mocked off/unavailable feedback and mobile overflow. No model message sent.
  Evidence: `/tmp/cine-toaster-preproduction-review`.
