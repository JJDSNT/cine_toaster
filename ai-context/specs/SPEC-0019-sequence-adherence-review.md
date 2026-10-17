---
id: SPEC-0019
title: Sequence Inception to screenplay and storyboard adherence review
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
---

# Contract

## Explicit pending work (CT-0114 / ADR 0033)

The first operational slice retains `sequence_review_requests` in the existing
Creation journal through a shared revision/source-checked command. It records
authorised intent, full canonical ordered scene scope, rationale, actor and a
fixed Coordinator owner. Current duplicate requests are idempotent; changed
sources can create a retained superseding request. Queries expose source/scope
changes, drawing-record coverage, agent-owned next steps and the currently
missing complete-review capability. Nothing infers a human gate or live run.

The existing inbox exposes separate AI-work counts, scope/owner/gaps and links
to the existing copilot. Implemented roles get current canonical work before
asset dumps; MCP exposes the same read/command. No generic queue, scheduler,
arbitrary completion command or automatic human approval is added. The actual
sequence package/independent validator described below remains unimplemented;
the request stays pending with that capability blocker visible.

## Full sequence comparison (remaining CT-0113 work)

ADR 0008's canonical sequence membership/order is the review scope. A sequence
package pins original Inception sources (declared intention, concept/reference
versions and explicitly scoped assessments), agent-interpreted criteria and
their exact screenplay-unit mappings, plus ordered shots and exact retained
storyboard candidates. A local scene study never substitutes for this package.
Unassigned scenes are not silently bundled into a new sequence.

Shared Core/HTTP commands retain `sequence_packages` and `sequence_reviews` in
the Creation journal, with actors, revision/source checks and immutable lineage.
The sequence remains a projection over existing scenes, not a duplicate manifest.
The package digest includes membership/order, original inputs, screenplay,
selected drawing records/bytes and existing continuity evidence. Changed input
or selected evidence makes reviews stale. Missing drawings, intent mapping or
image inspection prevents a human readiness request regardless of model opinion.

The same public CoAgent has bounded package-preparation tools. Its independent
review call(s) see ORIGINAL source text/images, screenplay, ordered drawings and
computed gaps, not only the creator's art brief or conversation. Image batches
retain exact evidence IDs/hashes and their observations before a sequence-wide
synthesis. The first slice bounds four batches of eight rasters; larger work
reports an agent-owned inspection gap, never narrows the human unit silently.
Unsupported visual transport does not claim pixel inspection.

The sequence-first GUI exposes original intention/references beside the ordered
script/drawing comparison, mapped criteria, available versus missing evidence,
independent findings, limitations and version provenance. Legacy production
stills/takes remain separately labelled, not fabricated Inception or storyboard.
Readiness is sequence-scoped; the existing human direction command can request
changes/accept only a current successful package review. It does not approve
individual masters, rewrite shots or start generation/3D. Incomplete work stays
agent-owned with explicit next corrections, not an empty approval gate.

Inspect Singular read-only using its existing Genebra grouping (1-01..1-04,
including intermediate scene subdivisions). Keep Demo 01's LAN project and
images intact. Tests/fixture decisions never mutate either real production.
