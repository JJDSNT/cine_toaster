# FinOps investigation: Runpod Batch Inference

Status: research / not approved for implementation  
Priority: medium-high for evaluation; implementation evidence-gated  
Date: 2026-11-04  
Scope: production operations, generation jobs, provider billing

## Why this matters

Cine Toaster already executes generation jobs (including LTX, ComfyUI and Qwen Edit) on Runpod, with budget controls and billing-based cost reconciliation. Runpod's generally available Batch Inference is therefore primarily a **FinOps opportunity**, not a proposal for a new provider or a second job orchestrator.

Official announcement: https://www.runpod.io/blog/batch-inference-is-now-generally-available-on-runpod

Runpod advertises discounted asynchronous serverless inference (discount varies by GPU; the announcement cites up to 30%), in exchange for flexible start times and potentially long queue delays. These figures, quotas, API semantics and eligibility must be checked against current Runpod documentation and our account before implementation. Do not assume every existing Runpod workload can use the batch endpoint.

## Existing boundaries to preserve

- Reuse the durable Job Manager, project-scoped job identity, recovery/reconciliation, provider job IDs, result staging and adoption defined by `ai-context/architecture.md` and `specs/SPEC-0008-jobs.md`.
- Keep the Project Core independent of Runpod and preserve canonical asset/take provenance.
- Reuse existing budgets, billing reconciliation and cost visibility; do not introduce an independent FinOps ledger or a parallel queue.
- No silent migration of interactive requests, approvals, or latency-sensitive production work to batch.
- Do not assume that GPU render jobs, long-running ComfyUI workflows or all video generation workloads qualify as Runpod Batch Inference.

## Investigation backlog (in priority order)

### P0 — Inventory and feasibility (no production changes)

1. Locate the existing Runpod adapter(s), job submission path, provider billing ingestion, budget enforcement and cost reporting; document actual code paths and current behavior.
2. Inventory workloads by model, endpoint type, container/worker, input/output contract, latency sensitivity, typical runtime, retry behavior and batch compatibility.
3. Validate Runpod's current batch API, worker/endpoint requirements, quota, supported GPU pricing, queue delay, cancellation, expiration, results retrieval and billing behavior using official docs. Record evidence and date.
4. Check whether existing endpoints can be reused without duplicating deployment/configuration. Identify unsupported cases explicitly.

**Deliverable:** capability matrix and an integration recommendation grounded in the current codebase.

### P1 — FinOps measurement design

5. Define a comparable baseline: provider-reported cost per successful output (image/frame/take/job), elapsed time, queue delay, throughput, failed/retried requests and operator overhead.
6. Distinguish nominal GPU discount from **net cost per accepted artifact**, accounting for retries, failed generations, storage/transfer if applicable, and human review/rejection.
7. Define budget safeguards: forecast before submission where possible, explicit cap, maximum queue wait/deadline, concurrency limits, cost attribution to project/shot/job, and no automatic spend escalation.
8. Define observability for submitted/queued/running/completed/failed/cancelled batch jobs and reconciliation after application restart.

**Deliverable:** benchmark protocol, acceptance thresholds and reporting fields; no fabricated savings claims.

### P2 — Bounded proof of concept

9. Choose one genuinely eligible, non-interactive workload and run the same representative inputs via existing Runpod execution and batch, with identical model/configuration and quality checks.
10. Compare cost, wall-clock completion, success rate, operational complexity and provenance; record the exact GPU/price/date.
11. Decide: adopt, defer, or reject. Adoption requires measured net savings, acceptable deadlines, correct billing and recovery, and no architectural duplication.

### P3 — Conditional integration (only after P2 approval)

12. Add a provider-specific batch submission/status/results capability behind existing generation/job interfaces, not a new global orchestration layer.
13. Add explicit execution-policy selection (interactive vs economical batch) with user-visible estimated trade-offs and deadlines; preserve opt-in until validated.
14. Test partial failures, duplicate callbacks/polls, retries/idempotency, cancellations, restart reconciliation, budget exhaustion and staged-result adoption.
15. Document operations, pricing caveats, fallback behavior and production acceptance tests.

## Non-goals

- Replacing Runpod or committing to it as the permanent provider.
- Introducing a generic distributed rendering platform.
- Moving all background jobs to batch automatically.
- Claiming savings from headline discounts without real workload measurements.

## Agent handoff

Start at P0. Inspect current implementation and related FinOps documents before proposing code. Prefer updating the existing FinOps roadmap/backlog if one exists; cross-link this investigation rather than duplicating it. Report exact files, gaps, and eligibility evidence. Do not deploy GPUs, submit paid jobs, or change production configuration without explicit authorization.
