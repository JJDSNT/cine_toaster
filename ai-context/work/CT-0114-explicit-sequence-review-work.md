---
id: CT-0114
title: Explicit agent-owned sequence review work
type: work
status: doing
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
---

# What

Record the authorised Inception -> screenplay/storyboard sequence validation as
durable production work, visible in the existing inbox and production-agent
context. Preserve exact requested scope, source preconditions, ownership and
actionable gaps without creating a second scheduler or a human approval.

# Why

The director asked whether this pending validation was visible to GUI/agents.
It was only development memory and a general runtime instruction; `/api/decisions`
showed one local SC-010 direction request and no agent work. The director now
authorises making the missing work explicit.

# Done

- Inspected existing Creation journal, shared commands, inbox projection and
  CoAgent context. Production workflows remain on the built-in engine; this
  record is production intent, not job/running state.
- Added the shared request command, optional journal validation, idempotent
  source-pinned lineage, query and HTTP/MCP access. No-op/task publication does
  not change existing Inception source hashes or approve a gate.
- Existing inbox now has separate human and AI counts, canonical whole-sequence
  scope, Coordinator ownership, drawing-record presence and agent-owned gaps.
  It explicitly reports not dispatched and the missing full validator; no forms.
- Coordinator and specialists receive current canonical work before asset
  summaries. Fresh visual/continuity reviewers also receive the retained work
  context. External MCP clients can read/register authorised review work.

# To do

1. Shared revision/source-checked request command and read-only current-work
   projection, preserving old journals and source digests.
2. Automatic canonical work context for the existing roles, explicit MCP query,
   GUI AI-work counts and sequence scope/gaps, separate from human decisions.
3. Test disposable films/HTTP/browser, run full regression, activate once and
   record the real authorised Demo request through the shared command.

# Decisions

- Narrow `sequence_review_requests` in Creation, not a generic task platform.
  Requests are retained intent with a fixed Coordinator owner and independent
  review responsibilities. A query exposes current blockers; no executor,
  arbitrary complete status, fabricated review or automatic approval is added.
- Current scope is canonical sequence membership/order, never a scene-only gate.
  Source/scope changes remain visible and require refreshed evidence.
- The full adherence package/validator remains CT-0113. Its missing capability
  must itself be visible; pending is not a claim that the agent is running.
- Preserve every image, source, assessment and human decision. Singular remains
  read-only. Only the explicitly authorised Demo work request is materialised.

# Validation

- First focused regression passed: 100 tests, 83.0 s. Expanded work/MCP tests
  passed separately: 21 tests, 28.8 s, including automatic specialist context.
- Initial sandbox run passed eight non-socket cases, then correctly failed at
  the HTTP socket restriction; reran the integration tests outside the sandbox.
- All six frontend test files passed; TypeScript/Vite client and sidecar builds
  passed (existing chunk-size/deprecated-option warnings remain).
- `git diff --check` passed. Full regression and disposable real-CoAgent GUI
  walkthrough running; no real production mutation yet.
