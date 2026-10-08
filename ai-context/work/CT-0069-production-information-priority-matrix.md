---
id: CT-0069
title: Production workspace — task and information priority matrix
type: work
status: proposed
owner: unassigned
created_at: 2026-10-08
updated_at: 2026-10-08
tags:
  - ux
  - production
  - cognitive-ergonomics
  - information-priority
---

# Scope and evidence

First concrete output of [CT-0068](CT-0068-human-centered-information-visibility.md): a task → question → information → Core source → display priority matrix for the **Production** workspace. It is a hypothesis to validate with real users, not a validated cognitive-science result.

A limited code audit on 2026-10-08 found:
- `frontend/src/App.tsx`: React Flow production graph, sequence/scene focus and automatic narrower initial focus for productions with >60 shot nodes.
- `frontend/src/ScriptApp.tsx`: CodeMirror screenplay editor; saves deliberately avoid resetting cursor, scroll and undo.
- `frontend/src/Assistant.tsx`: contextual `Seen` fields (`room`, `scene`, `focus`, `selected`, `details`), shared assistant thread and interrupt-based confirmation.
- `frontend/src/navigation.ts`: existing navigation destinations for canvas, screenplay, overview, scene and comparison. Cross-workspace selection persistence **must still be verified**, not assumed.
- `docs/canvas.md`, CT-0023 and CT-0046: project-state projection and edit commands, distinct from workflow execution graph.

This is not yet an exhaustive inventory of backend endpoints, current control-room templates or status semantics.

## Priority definitions

- **Persistent**: needed to maintain orientation or make the current primary decision.
- **Contextual**: appears for the selected object, task or mode.
- **On demand**: accessible in inspector, expanded panel or drill-down without crowding the default view.
- **Interruptive**: exception or human decision that warrants attention, with severity and recoverable action.
- **Background**: available in activity/history, not foregrounded in routine work.

These are *placement hypotheses*, not fixed universal rules.

## Production information matrix

| Task | Human question | Minimum information | Priority | Likely existing source / validation |
| --- | --- | --- | --- | --- |
| Orient in project | Which scene/shot am I working on? | Project, sequence, scene, selected shot and stable breadcrumb | Persistent | Production graph, navigation; verify preservation across rooms |
| Choose a take | Which alternative is best? | Side-by-side preview, take identity, selected status, review state | Persistent during comparison | Take records, scene/compare rooms; audit actual comparison UI |
| Approve a take | What will become canonical? | Current vs proposed take, affected shot, scope, confirmation/undo path | Contextual; interruptive if consequential | Selection commands and revisions; verify confirmation UX |
| Generate material | What will be made and why? | Target shot, input/reference, intended output, selected provider, expected cost when known | Contextual before submit | Workflow/generation planning; audit API and FinOps integration |
| Monitor generation | Is work progressing? | Running count, blocked/failed count, jobs needing review; selected job state | Persistent compact summary; details on demand | Job runtime and producer status; audit actual event latency |
| Respond to failure | What failed, what is affected, what can I do? | Severity, job/shot, actionable cause, retry/fallback and side effects | Interruptive for blocking failures; background otherwise | Jobs runtime and validation findings |
| Compare reference to output | Does the take match intention? | Reference, storyboard 2D/3D where present, output preview, relevant criteria | Contextual comparison mode | Canvas and shot/take media references |
| Review continuity | Is the inconsistency real? | Affected shot, observed evidence, declared fact, uncertainty, options | Contextual; interrupt only for material blocking conflicts | Continuity ledger CT-0059; visual inference not assumed |
| Inspect lineage | Where did this material come from? | Selected take's source and version; expanded provenance tree | Source badge contextual; full graph on demand | Graph lineage, take provenance |
| Track cost | Are we spending unexpectedly? | Current/estimated spend and threshold exception when available | Background normally; interruptive for threshold breach | FinOps and job costs; thresholds need product policy |
| Handle agent proposal | What would the agent change? | Target, before/after, uncertainty, affected assets, cost, approve/reject | Contextual proposal; explicit approval | Assistant interrupts; command revision semantics |
| Switch to editing | Where will this take be used? | Shot/take identity and deep link to sequence/clip | Contextual navigation | Existing navigation incomplete for a full three-space shell |

## First-glance screen hypothesis

**Default Production mode:**
1. Primary region: selected shot/take preview and comparison or production canvas (depending on mode).
2. Compact orientation: project → sequence → scene → shot.
3. Compact actionable status: pending approvals, blocking failures, active jobs.
4. Inspector only for selection-specific settings and actions.
5. Agent as contextual invocation; open conversation/proposals on demand, with pending approvals surfaced separately.
6. Advanced provider parameters, complete node graph, detailed FinOps, provenance tree and logs remain available but not always open.

Avoid simultaneous permanent presentation of explorer, full graph, large monitor, all take alternatives, inspector, assistant chat, FinOps and logs.

## Research hypotheses and falsification

- H1: Task-specific modes reduce unnecessary visual search versus all-panels-open. Test time-to-find and error rates.
- H2: A compact exception/approval strip conveys situation awareness better than a full job dashboard. Test comprehension after brief exposure.
- H3: An on-demand agent panel reduces distraction without hiding pending approvals. Test discoverability and interruption recovery.
- H4: Persistent context labels reduce wrong-shot actions when switching workspaces. Test mistaken-target rate.
- H5: Comparison mode needs at least two simultaneously visible images/players; single preview with sequential switching may hinder evaluation. Test decision time and confidence.

## Next experiments

- [ ] Inspect server-rendered control-room pages, actual routes, job and take status APIs, and existing FinOps UI; update the source column with precise references.
- [ ] Build **task × information × UI region × urgency × action** matrix for Screenplay & Storyboard and Editing & Post-production.
- [ ] Create two Production layout variants: **Focus** (preview + minimal context + approval status) and **Review/Expert** (comparison + inspector + jobs).
- [ ] Run a five-second state-comprehension test and task walkthrough for take approval, job failure and regeneration; collect errors and perceived workload.
- [ ] Review findings against WCAG 2.2, Nielsen heuristics and situation-awareness literature with source annotations; do not assert validated human comfort without tests.
- [ ] Feed evidence back into CT-0067 wireframe and CT-0066 UX vision; create ADRs only after validation.

## Decision

No permanent panel configuration is approved. This matrix defines **what to test next**, not what must ship.
