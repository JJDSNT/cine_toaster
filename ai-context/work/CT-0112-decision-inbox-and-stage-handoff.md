---
id: CT-0112
title: Human decision visibility and executable approved stage handoff
type: work
status: doing
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
tags: [human-gates, gui, agent-runtime, storyboard]
---

# What

Expose canonical pending decisions across workspaces and connect approved
Inception direction to an explicit, versioned next-stage input consumed by the
existing CoAgent. Let Art Direction publish retained storyboard candidates from
registered reference images through the existing storyboard command.

# Why

The director could not find the pending Demo 01 question or advance approved
material. A gallery and a chat instruction alone do not constitute a handoff.

# Done

- Read current architecture/specifications and audited the pending assessment,
  same-CoAgent continuation, reference generation and storyboard registration.
- Added SPEC-0018 / ADR 0032 and shared Core/HTTP operations. GUI approval
  atomically adopts exact displayed development targets and input snapshots.
- Added a derived inbox and links from Creation, preproduction, canvas,
  screenplay editor and the existing control room. Read errors are explicit.
- Existing Art Direction can publish real retained storyboard images from
  registered references, link exact handoff/decision/source hashes, preserve
  earlier versions and refuse publication outside approved scope.
- Fixed a browser-discovered continuation race: a fresh drawer must wait for
  the connected CoAgent, not run on its provisional client. Explicit retries
  have distinct human intent IDs; replay cannot duplicate work.
- Read-only Demo 01 check: revision 6/source digest unchanged; preview resolves
  SC-010 / P1,P2,P3 and displays that target before human approval.
- Browser acceptance passed through the real GUI, CoAgent and HTTP commands:
  inbox -> explicit human approval -> retained storyboard -> independent visual
  precheck -> next human gate, with reload/mobile and unavailable-read feedback.
- Activated with one announced graceful restart after confirming no active jobs;
  same `codex-cli`, `0.0.0.0:8787` and Windows LAN URL. No OS networking change.
- Read-only live LAN API/browser checks passed: one real pending request,
  exact SC-010 / P1,P2,P3 target, Approve & advance and mobile layout. No model
  message or human decision was sent. Screenshots:
  `/tmp/cine-toaster-ct0112-live-pending.png` and
  `/tmp/cine-toaster-ct0112-live-mobile.png`.
- Doctor now includes the decision-inbox build entry in GUI readiness, with
  the existing `make ui` remedy for an older/incomplete build.

# To do

1. Sequence-level acceptance continues in CT-0113; scoped mechanism regression
   and read-only live checks passed, without approving the real proposal.
2. Human review of the actual pending SC-010 / Wake P1-P3 proposal. Development
   approval is deliberately not performed by repository agents.
3. Canonical promotion of local proposed-shot IDs, final storyboard-to-3D/master
   workflow, informal-question capture and durable autonomous recovery remain
   separate gaps, not claims of this existing-shot development slice.

# Decisions

- Director correction during implementation: the human review/work unit is a
  **sequence**, not an isolated scene. The existing-shot handoff and visual
  precheck do not establish Inception -> storyboard narrative adherence. Do not
  present this slice as completion of that transition. The real Demo 01 has no
  visual/continuity reviews, decisions or handoffs at revision 6; its only
  pending request is the earlier SC-010 P1-P3 development direction.
- Required next acceptance: a sequence package connects exact Inception
  intention/reference versions to ordered screenplay beats and storyboard
  drawings, with independent adherence/continuity findings and explicit missing
  material. The human reviews that comparison and disposition, not a scene
  image alone. Missing shots remain agent-owned gaps, not approval requests.
- Demo 01 currently declares sequence `the-ascent` across SC-010..SC-070
  (103 seconds). Do not silently redefine it as the three shots of Wake.
- Promotion here adopts exact material as input for the approved development
  scope, not canonical shot-manifest rewriting or final storyboard approval.
- Reuse Creation journal, existing human command, CoAgent and job engine.
- New images still require their own generation quota consent. Registering an
  existing reference as a storyboard candidate does not manufacture generation
  provenance or claim visual quality approval.
- Inbox derives real saved gates, never infers that every missing artifact is
  a human request. No model approves Demo 01 or writes fixture material there.

# Validation

- Integrated focused regression: 85 tests passed in 70.4 s.
- Frontend five test files and TypeScript/Vite builds passed (existing large
  chunk/deprecated build-option warnings remain).
- First browser attempt exposed the provisional-agent race; second proved real
  HTTP publication/review but exposed a duplicate-heading assertion. Removed
  the redundant UI question and rerunning acceptance.
- Full regression passed: **1186 tests in 685.8 seconds**. No real production
  decision or generation made. Sequence acceptance remains open under CT-0113.
- Browser evidence inspected: `/tmp/cine-toaster-stage-handoff-_ijh3lr5`.
  Under simultaneous heavy rendering, the initial 30-second acceptance limit
  was insufficient; a 120-second bounded wait completed. Disconnected browser
  requests produced BrokenPipe diagnostics during fixture navigation/teardown.
- Distinct explicit continuation/replay regression passed separately (9.9 s).
- Final focused regression: **89 tests passed in 226.1 seconds**, including all
  15 handoff tests. Doctor's nine tests passed separately. All five frontend
  test files and the final build passed.
- Existing Inception GUI regression passed on the final bundle: real public
  CoAgent saves work, accepts human changes, retains a new version/review,
  reload/mobile; no model call or mutation of the real production. Evidence:
  `/tmp/cine-toaster-inception-agent-3d_bj0q6`.
