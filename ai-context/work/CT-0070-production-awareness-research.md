---
id: CT-0070
title: Production Awareness — human situation awareness and explainable status
type: work
status: proposed
owner: unassigned
created_at: 2026-10-08
updated_at: 2026-10-08
tags:
  - ux
  - human-factors
  - situation-awareness
  - production
  - research
---

# Research question

How can Cine Toaster communicate **what is happening, why it matters, what changes next, and which human decision is needed**, without requiring a filmmaker to reconstruct the state of the production from unrelated dashboards?

This is a research direction called **Production Awareness**, not a committed fourth workspace, separate agent, new source of truth or permanent dashboard. It extends [CT-0068](CT-0068-human-centered-information-visibility.md) and [CT-0069](CT-0069-production-information-priority-matrix.md).

## Five research lenses

| Lens | Practical question | UX hypothesis to evaluate |
| --- | --- | --- |
| Situation awareness (Endsley) | Can the user perceive, comprehend and anticipate the relevant state? | Present **state + consequence + next possible action** together |
| Ecological Interface Design (Rasmussen/Vicente) | Can the interface expose meaningful constraints and relationships, not just isolated metrics? | Show dependencies among shot, selected take, assembly and approval |
| Distributed cognition (Hutchins) | How do humans, agents and external representations share memory and reasoning? | Stable identifiers, visible decisions and shared visual context reduce reconstructive effort |
| Attention management / alert fatigue | Which changes merit interruption? | Escalate blocked work and consequential approvals; aggregate routine progress |
| Human–AI interaction | Can the user understand what an agent proposes and safely control it? | Show scope, evidence, uncertainty, preview, cost and reversible outcome |

**Caution:** These theories inform hypotheses; they do not demonstrate that a specific UI is usable. Distinguish academic theory, heuristics and product tests.

## Existing Cine Toaster capabilities to reuse

Code/documentation audit on 2026-10-08:

- **CT-0057 Producer status**: `producer.py` exposes scene/sequence status, chosen/unchosen/missing takes, latest and approved assembly versions, blockers, human gates and next decisions; `toast status`, `GET /api/status`, MCP `production_status`, and an existing Sequences-room status panel. It deliberately **does not rank** decisions, leaving priorities to the author.
- **CT-0059 Continuity ledger**: `continuity.py` tracks **declared** continuity facts, provenance, and differentiated warning/advice/error findings. Inferred information is a question, not a proven contradiction; `GET /api/continuity`.
- **CT-0061 FinOps observation**: `finops.py` reconciles Runpod billed hours to known jobs with explicit allocated, measured, unattributed and unobserved amounts; do not present allocated cost as a direct provider per-job charge.
- **frontend/src/App.tsx**: React Flow production canvas already limits initial focus for large productions.
- **frontend/src/Assistant.tsx**: assistant receives `room/scene/focus/selected/details`, can navigate, and uses interrupt confirmation.
- **frontend/src/navigation.ts**: existing deep-link routes; cross-workspace context preservation still needs validation.

**Implication:** Prefer a **read-only, explainable projection of existing status, decisions, lineage and job events** over a second inference or analytics subsystem.

## Candidate awareness contract (research sketch, NOT a finalized API)

An awareness item should be traceable and answer:
- **subject**: project / sequence / scene / shot / take / assembly version
- **observation**: what changed or is waiting; timestamp and source
- **meaning**: consequence for the film, expressed without inventing facts
- **evidence**: exact existing record(s), finding(s), job(s), revision(s)
- **uncertainty**: declared / computed / inferred / unknown, including freshness
- **attention**: background / informative / action-needed / blocking; policy and author override
- **next actions**: supported Core commands or navigation targets; no action invented from UI text
- **reversibility**: approval gate, expected revision, side effects, undo path where supported

An item can summarize several low-level events into a human-readable consequence. The source records remain authoritative.

### Example (illustrative, not a claim of implemented dependency tracking)

**Observation:** A new take is approved for shot P03.
**Consequence:** An earlier approved assembly may still reference a previous take; *check actual references before asserting it is stale*.
**Next action:** Compare the assembly's referenced take against the selected take, then offer to retain or reconform using supported commands.
**Evidence:** shot/take selection decision + assembly version's actual take reference.
**Human control:** never silently replace timeline media or discard editorial choices.

## Screen placement hypothesis

- **Persistent, compact orientation**: current film / scene / shot, plus unobtrusive count of items genuinely requiring human attention.
- **Contextual awareness**: show a consequence directly beside the selected take, timeline clip, storyboard card or agent proposal.
- **On-demand explanation**: expand to evidence, dependencies, affected revisions, cost and full activity.
- **Interruptions**: reserve for blocking errors, approvals with consequential side effects or explicitly configured thresholds. Routine job completion should not repeatedly steal focus.
- **Across all three workspaces**: awareness follows the same object identity; the displayed explanation changes with the current task.

## Theoretical sources to verify in the evidence review

- Endsley, M. R. (1995), *Toward a Theory of Situation Awareness in Dynamic Systems*, Human Factors, 37(1), 32–64. DOI: 10.1518/001872095779049543.
- Vicente, K. J. & Rasmussen, J. (1992), *Ecological Interface Design: Theoretical Foundations*, IEEE Transactions on Systems, Man, and Cybernetics, 22(4), 589–606. DOI: 10.1109/21.156574.
- Hutchins, E. (1995), *Cognition in the Wild*, MIT Press.
- Amershi et al. (2019), *Guidelines for Human-AI Interaction*, CHI 2019. DOI: 10.1145/3290605.3300233.
- Nielsen Norman Group, usability heuristics: https://www.nngroup.com/articles/ten-usability-heuristics/
- W3C WCAG 2.2: https://www.w3.org/TR/WCAG22/

References are **starting points**, not a claim that each full paper was retrieved and critically assessed in this iteration.

## Evaluation tasks and success criteria

1. **Five-second comprehension:** show a realistic Production screen briefly; ask what is happening, what is blocked and what needs a decision. Compare status-only versus state+consequence views.
2. **Changed take / existing cut:** after a take-selection change, ask whether the current assembly uses it. The interface must inspect actual references and never falsely claim a stale edit.
3. **Continuity finding:** ask users to distinguish declared contradiction from unconfirmed inference; measure false certainty and wrong approvals.
4. **Cost and failure:** test whether users distinguish estimated, measured and allocated cost; can locate the failed job and recover without scanning logs.
5. **Agent proposal:** show before/after and affected scope; ask users to approve, reject or inspect evidence without losing context.

Track correctness, time-to-find, false alarms, missed blockers, wrong-target actions, interruption recovery and perceived workload. Include laptop and large-display layouts.

## Implementation sequence — only after validation

- [ ] Verify research sources and record what is theory, heuristic or measured evidence.
- [ ] Audit actual `/api/status`, continuity, jobs, assembly references, agent gates and FinOps schemas; map source fields precisely.
- [ ] Prototype **read-only awareness items** from deterministic records; avoid LLM-generated claims of stale dependencies.
- [ ] Test a compact status-only variant against a state+consequence+action variant on real workflows.
- [ ] Define attention rules, grouping and freshness; permit users to defer nonblocking notifications.
- [ ] Test with representative filmmakers and record rejected patterns, not only successes.
- [ ] Update CT-0067/0068/0069 and roadmap; create implementation work and ADRs only if results warrant.

## Explicit non-goals

- No autonomous re-editing of the film.
- No automatic priority ranking of the author's creative decisions.
- No invented continuity evidence, stale assembly claims or per-job provider billing.
- No fourth top-level workspace.
- No permanent all-knowing dashboard that competes with task-focused workspaces.
