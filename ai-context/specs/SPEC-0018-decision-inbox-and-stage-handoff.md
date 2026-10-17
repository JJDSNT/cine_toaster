---
id: SPEC-0018
title: Decision inbox and approved stage inputs
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
---

# Contract

Director clarification: the work/human review unit is the sequence. The narrow
existing-shot input/publication mechanism below does not satisfy sequence-level
Inception -> storyboard acceptance. A future review package must expose exact
Inception inputs -> screenplay beats -> ordered drawings and an independent
narrative-adherence/continuity review, with explicit gaps. Individual scene
images and visual prevalidation against a creator-authored brief are insufficient
evidence. Keep incomplete sequence work agent-owned; do not invent an approval
request merely because one scene has pictures.

The inbox is a read-only projection of current canonical direction requests and
waiting scene/workflow gates, with question, scope, evidence and an origin link.
Missing artifacts, warnings and unresolved choices without a saved request are
not invented human gates. Read failures are visible, never a false zero count.
Main workspaces link to it. Approved handoffs show outputs or a truthful
not-yet-produced state, never an invented running status.

Human direction approval may atomically retain a `stage_handoffs` record in the
Creation journal, pinning the decision, assessment, destination, target and
source snapshot. Promotion means approved input for scoped development, not
rewriting canonical screenplay/shot manifests or approving final images.
The GUI shows exact canonical scene/shot targets before approval. Legacy prose
can suggest uniquely named canonical IDs, but this interpretation is displayed
and fingerprinted in the human's explicit advance request. Ambiguous/missing
scope requires a new scoped proposal; the model cannot broaden it silently.

Input freshness verifies pinned records/media and canonical story context while
allowing additive downstream work (new briefs/references/drawings). A handoff
does not become stale merely because its consumer produced an output. Deleted
or changed sources, changed canonical intent or superseding upstream proposals
refuse consumption. Replay may not duplicate the same handoff/output.

The existing public CoAgent can resume the exact decision and route storyboard
development to Art Direction. That role can retain a storyboard candidate from
a project-registered reference through the existing storyboard import command,
linking decision/handoff/reference hashes and preserving all previous drawings.
It cannot use arbitrary file paths, approve gates or claim generation provenance
for reused images. Actual image generation remains behind the existing jobs,
exact quota confirmation and non-overwriting adoption; no new executor.

Closing a page/service failure can prevent a conversational run. Saved handoff
and output records survive; the GUI offers continuation through the same
CoAgent, and makes incomplete/blocked next work visible. No durable autonomous
worker is implied. Tests use disposable films, never Demo 01 approvals.

## Amendment (ADR 0035, 2026-10-17): sequence targets and batch consent

A storyboard proposal may name `sequence`; its handoff target is the canonical
sequence `{sequence, label, scenes: [{scene, shots}]}` in declared order, valid
only while equal to the current declaration. Publication accepts any shot of
the target. The handoff view adds `coverage` {shots, drawn}, `missing` and
`superseded` (a newer assessment exists); superseded handoffs leave the inbox's
AI work. Art Direction's `plan_batch` + one `generate` consent send every
planned drawing together; Generation Operations continues each job. The review
request needs a drawing for every target shot and current visual reviews that
together inspected every current drawing.
