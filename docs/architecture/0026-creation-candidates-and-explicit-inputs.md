# ADR 0026: Creation candidates preserve their inputs independently of chat

Status: accepted for the CT-0105 implementation.

Creation / Inception precedes screenplay development. Brainstorm conclusions
and rough references need durable versions and explicit handoffs rather than
provider sessions or browser state as their authority.

Store candidate concepts and screenplay drafts in `creation/state.json` in
the production. This is runtime-owned serialization of explicitly submitted
text, not permission to rewrite authored `project.yaml`, scene breakdowns or
the current screenplay. Every save appends a complete immutable candidate,
including actor, rationale, predecessor and pinned inputs. One root-directory
lock, required expected revision and atomic replace serialize updates.

The same journal retains explicitly recorded exploration rounds: title,
selected reference versions, rationale, statement source, predecessor round and
specific previous/current artifact corrections. A corrective pass is a
creative revision even when no older image was supplied to its generator.
These relationships never imply provider inputs, a successful correction or
human approval. Never infer them from a filename, shared cast/style or time.
Record the author of the journal entry separately from the source of the
creative observation; an agent can document a director's explicit statement
without impersonating the director or approving a result.

Rounds are filmmaker-defined groups, not a fixed taxonomy or a prescribed
number of passes. Revising a round appends a version with the same `round_id`
and a `based_on` predecessor; the earlier record stays intact. The read view
lists the latest version of each group in its `follows` order and refuses
cyclical ordering. That changes the round's description/grouping, not the
versions or approvals of its images. Unassigned new references remain visible.
The primary gallery groups images by these rounds; dense provenance is
available on demand rather than becoming a second production dashboard.

A screenplay candidate names a saved concept and selected reference records,
with their content digests. Revising a concept or generating a new reference
does not change an older candidate's inputs. Missing/changed references are
reported instead of silently substituted. The existing editor retains authority
over explicit human edits to the canonical screenplay; candidate promotion is
not implemented by this first slice.

Reference images retain the existing `references/<id>/reference.yaml` format.
GUI generation runs as a job with pinned inputs, stages its new reference and
adopts it explicitly without allowing overwrite. Provider details stay in the
existing adapter and provenance, not in the creation candidate model.

The first API, CLI and MCP tools invoke the same operations. Agent tools may
save candidates but may not convert them into a human approval or overwrite
the canonical screenplay. Operational events can be discarded while all draft
versions and their input relationships remain recoverable from the film.
