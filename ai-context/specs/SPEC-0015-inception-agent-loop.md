---
id: SPEC-0015
title: Production Coordinator and Inception agent loop
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
---

# Contract

Extend the existing public `assistant` CoAgent, LangGraph host and injected
Model adapter. The project-scoped Production Coordinator owns the conversation;
Inception is an internal specialist invocation, not a relabelled provider
thread or a second executor. Production workflows/jobs remain on SPEC-0009/0008.

For each human input, read current production state. A blank film without a
screenplay enters Inception; an imported screenplay does not acquire a mandatory
Inception gate. Creation-room requests normally enter Inception. Elsewhere the
Coordinator can delegate creative exploration to Inception or use its existing
read/navigation/confirmed workflow-and-cut tools. Unsupported stage executors
are reported, not fabricated. A reused thread with another project identity is
refused. Current model selection remains independent of filmmaking role.

Inception receives bounded whole-film context, current Creation material,
human decisions/guidance and relevant screenplay/storyboard records. Tools can
read the existing application queries, append concept/screenplay candidates
and author readiness assessments via shared application operations. Candidate
versions and references remain preserved. A screenplay candidate consumes an
exact saved concept; no implicit canonical screenplay promotion occurs.

An assessment uses the Creation revision and material digest actually read.
Changes to the journal or upstream production material refuse publication and
require rereading/reasoning. Tools cannot supply arbitrary actor identity,
approve/reject human gates, edit manifests, delete assets, execute shell or
start unapproved image generation. Image metadata is not visual inspection;
reference advice is not verified external research.

The graph alternates reasoning and tools, with bounded reads, writes and model
calls. Successful receipts feed the next reasoning step; failures are explicit
and do not become success messages. Shared AG-UI state exposes the active role,
routing reason and real stop state. Final review requests must correspond to a
saved current assessment. Canonical records remain available without chat.

This first event loop is invoked through CoAgents interaction, not an always-on
poller. A human GUI direction decision may trigger another CoAgent turn using
its canonical decision ID; the runtime rechecks that record. No second task
queue, background scheduler or claim of dispatch from a chat message is added.
Provider sessions/checkpoints remain disposable; full SPEC-0001 binding and
durable autonomous/background continuation are separate milestones.

# Acceptance

- New film -> Inception; existing/imported film -> context-aware coordination.
- Existing conversation can delegate Inception outside Creation and return to
  existing coordinator tools without changing provider or public CoAgent.
- Specialist reads cross-stage context and saves actual retained candidates /
  readiness; the GUI refreshes authoritative records after work.
- Human changes -> exact decision/guidance read -> a new retained version and
  review request, or a truthful unsupported-capability stop.
- Revision/material conflicts, model failure, invalid tool calls and limits
  stop truthfully; no human gate or generation is decided by the model.
- Existing assistant confirmation, navigation and AG-UI behavior regressions pass.
- Browser/model fixtures use disposable films; no test decides Demo 01 gates.
