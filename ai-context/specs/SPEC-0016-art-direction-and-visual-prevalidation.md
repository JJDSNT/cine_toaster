---
id: SPEC-0016
title: Art Direction and visual prevalidation
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
---

# Contract

Extend SPEC-0015's public assistant graph with Art Direction and a separate
Visual Prevalidation role. Coordinator/Inception can delegate; all roles use
the injected model adapter and shared application operations. No second engine.

Art Direction records immutable briefs in the Creation journal: intention,
visual language, checkable criteria, pinned concept/reference inputs and revision
lineage. Optional generation reuses `generate_reference` jobs and non-overwriting
adoption. Each job requires explicit interactive quota consent over the exact
plan; source changes invalidate that plan. Retaining a candidate is not approval.

Prevalidation receives actual, bounded, project-scoped raster attachments through
an optional visual model capability. Unsupported providers stop visibly before
claiming inspection. A fresh reviewer call sees the brief, source images and
current film context, not the creator's claim of quality. It records evidence
per criterion, uncertainty, actionable corrections and an advisory disposition:
`ready_for_human`, `needs_changes`, or `inconclusive`. It never approves a gate.
Changed briefs/inputs/materials refuse publication and make retained reviews
stale. A review cannot claim readiness with failed/uncertain criteria.

Bound correction attempts; preserve failed alternatives. A successful precheck
can create the existing human readiness request with exact brief/review linkage.
Generation continues under existing jobs if a bounded wait expires; report the
actual job and require another CoAgent interaction for later reasoning. This
slice is not durable automatic resume after completion/restart.

The GUI shows briefs, evidence, stale status and human review separately, with
no new authoring forms. Model/provider failure, conflicts, quota refusal and
resource limits stop truthfully. Tests use disposable films, not Demo 01 gates.
