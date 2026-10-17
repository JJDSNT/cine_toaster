# ADR 0033: Sequence review requests are production work, not chat or jobs

Status: accepted

## Decision

Retain explicit `sequence_review_requests` in the existing Creation journal,
through one revision/source-checked Core command shared by HTTP and MCP. Each
request pins the canonical sequence order and material digest, its rationale,
actor and Coordinator owner. Identical current requests are idempotent; changed
inputs can create a retained superseding request. Queries derive current scope,
source changes, missing drawing records and remaining review capabilities.

The existing decision inbox separates this agent-owned work from real human
gates. Internal roles receive current work and external agents can read it.
No request is a live run or completed review; absent package/review capability
is explicit. No arbitrary completion operation or human approval is introduced.

## Consequences

Work survives chat/cache deletion and reload, while production jobs/workflows
stay on the existing built-in engine. This is a bounded production-intent record,
not a second queue, scheduler or workforce platform. Source freshness does not
mean narrative/pixel validation. SPEC-0019's actual independent sequence review
and human-ready comparison remain a separate implementation milestone.
