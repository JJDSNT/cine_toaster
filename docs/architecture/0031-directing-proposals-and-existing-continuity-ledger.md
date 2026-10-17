# 0031 — Shot-planning proposals and the existing continuity ledger

Status: accepted · 2026-10-16 · CT-0111 / SPEC-0017

The existing Production Coordinator delegates to Directing/Shot Planning or
Script Supervisor/Continuity in the same public LangGraph CoAgent. Do not add
another coordinator, Producer, queue, model binding or production scheduler.

Direction plans and continuity reports are append-only Creation records with
revision/source preconditions. Plan IDs and coverage are local to a retained
proposal and pinned screenplay units, not canonical shot-manifest edits.
Optional canonical-shot associations and art-brief hashes establish inputs.

Continuity reuses `continuity.ledger`, canonical scene declarations and existing
computed geometry/coverage findings. A separate fresh reviewer call receives
records and the exact plan, not the creator's conversation. Evidence is labelled
authored/computed/inferred/unknown with registered source IDs. Deterministic
proposal coverage/state checks remain outside model opinion. Standalone
canonical audits do not require an artificial new shot proposal. Neither mode
claims pixel inspection or approval authority.

The shared human direction gate can pin a current successful proposal review.
New versions/reports or changed screenplay/geometry/continuity invalidate that
request. Exact canonical decisions can resume the same role graph; approval
does not promote shots, approve storyboards or authorise generation. Missing
downstream implementation is reported honestly. Preproduction displays records
and decisions without authoring forms and refreshes after agent writes.

This first slice is bounded and interaction-driven: eight reasoning steps,
two independent reviews and a bounded disclosed context. Persistent autonomous
continuation and canonical proposal promotion require their own contracts.
