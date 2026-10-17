---
id: SPEC-0017
title: Directing shot proposals and independent continuity review
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
---

# Contract

Extend the existing Coordinator/CoAgent graph (SPEC-0015/0016), not its
orchestration topology. Directing/Shot Planning converts linked screenplay scenes
and optional pinned art briefs into immutable shot-plan proposals. Each proposal
specifies intention, ordered local shot IDs, optional canonical-shot association,
action, framing/camera intent, proposed duration, exact screenplay unit indices,
proposed entry/exit facts and transition intent. These are proposals, not edits
to canonical shots, numeric geometry, rendered boards or creative approvals.

Store `direction_plans` and `continuity_reviews` in the existing Creation journal
with actors, lineage, revision checks and a planning-source digest covering the
canonical screenplay, full relevant production context and existing continuity
ledger/geometry. Existing journals and their Inception material hashes remain
compatible when no directing records exist.

Script Supervisor/Continuity is a separate fresh model call using canonical
scene/film context, the existing ledger and deterministic coverage/state checks.
It does not create another ledger or inspect pixels from metadata. Retain
structured advisory findings with traceable source IDs, basis, severity,
uncertainty and corrections; keep computed checks independently from model
claims. Invalid source citations, missing script units and stale sources refuse
publication. Unresolved blocking checks cannot be reported ready for human review.
The same role can publish a standalone canonical scene/film audit without a
proposal. Proposal readiness checks its proposed coverage/joins; existing
canonical findings are retained separately, not silently erased or treated as
proof that a new textual proposal fixes measured geometry. Canonical audits
cannot claim readiness while their computed warnings/errors remain.

Bound the feedback loop. Directing can correct a proposal using exact review
findings; versions remain. A current successful review supports a human direction
request in the existing production gate, visible in preproduction and Creation.
Human direction resumes the same role graph with exact decision/material checks.
Human approval is not canonical shot promotion or storyboard/master approval;
unsupported downstream actions stop honestly rather than fabricate completion.

The GUI shows proposals, comparisons to existing shots, evidence, limitations
and approval scope. Agent writes refresh it without reload. No new authoring
forms, provider hardcoding, generation quotas or production mutations in tests.

Implemented limits: eight reasoning steps and two independent review attempts
per turn; 48,000-character planning/review contexts. A scoped context keeps the
full addressed scene, neighbouring declarations and the existing ledger, and
discloses its scope. Explicit reads refresh conflicts; failures do not silently
refresh publication tokens. A human decision is checked once before resuming;
subsequent retained corrections can supersede its old proposal within that turn.
Canonical shot promotion, image generation from these plans, durable autonomous
continuation and a wider DoP/Editor workforce remain outside this slice.
