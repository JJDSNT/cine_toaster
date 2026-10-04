# FinOps and provider cost integration

Status: **architectural proposal / pending implementation**

Cine Toaster should treat cost as production telemetry. The goal is not to
rebuild the billing consoles of Runpod or future providers, but to combine
Cine Toaster's knowledge of **what production work was requested** with the
provider's authoritative knowledge of **what infrastructure/account usage was
billed**.

This document proposes a provider-neutral FinOps layer that uses native
provider cost/billing data whenever it is available.

## Principle: reconcile, do not duplicate

Cine Toaster knows semantic attribution:

- production, sequence, scene and shot;
- take / generation / derived artifact;
- agent and task that requested the work;
- capability and provider adapter;
- job timestamps, parameters and execution identifiers.

A provider such as Runpod knows infrastructure/account billing:

- resource/product used;
- provider execution/resource identifiers;
- runtime/usage;
- provider prices and billed amounts;
- account/project/billing-period totals;
- credits/discounts where exposed.

Neither side alone is sufficient. FinOps should correlate the two.

```text
Cine Toaster job/provenance             Provider billing/cost centre
production / shot / take                authoritative billed usage
agent / task / capability               resource / runtime / price
provider execution ID  <------------->  provider execution ID
             \                           /
              \                         /
               +---- Cost Reconciliation
                          |
                    Cost Ledger
                          |
                Digital Workforce Console
                Producer / Studio Engineering
```

## Provider cost adapters

Introduce a provider-neutral **Cost Provider Adapter** (name provisional).
Runpod is the first candidate, not a special case in Project Core.

An adapter may expose only what the upstream provider actually supports:

- current/recent usage;
- itemised costs;
- billing-period totals;
- resource/execution metadata;
- pricing/rate information;
- account credits/balance/budget information;
- native project/tag/label/cost-allocation dimensions;
- export/report links or identifiers.

Future adapters may cover other GPU/model/cloud providers without changing the
production cost model.

Provider APIs and native cost centres should be preferred over scraping UI.
If a provider exposes useful billing data only through exports or reports, the
adapter may ingest those explicitly. Browser automation should not become a
billing dependency.

## Runpod integration investigation

Runpod should be investigated as the first implementation because Cine Toaster
already intends to use remote ComfyUI/GPU execution there.

Before implementation, verify the current Runpod API/console capabilities and
document which are available to the account/product being used:

- [ ] usage/billing API or supported billing export;
- [ ] itemisation granularity for Pods, Serverless and other products;
- [ ] stable execution/resource IDs suitable for reconciliation;
- [ ] timestamps and runtime/usage units;
- [ ] price/rate and final billed-cost fields;
- [ ] credits, discounts and balance data;
- [ ] native projects/tags/labels or equivalent cost-allocation metadata;
- [ ] billing period/timezone/currency semantics;
- [ ] API retention/history limits;
- [ ] rate limits and permissions required for read-only FinOps access.

### Verified on 2026-10-04 (CT-0058, read-only, this account)

Read through the Runpod v2 REST billing surface (the Runpod MCP tools
`list-billing`, `list-serverless-billing`, `list-endpoints`):

- **Billing API**: yes, read-only, aggregated by time bucket (`hour`, `day`,
  `week`, `month`, `year`; RFC 3339 UTC boundaries).
- **Granularity**: serverless spend is itemised **per endpoint per bucket**,
  split into `gpuAmount`, `diskAmount`, `cpuAmount`, `feeAmount`. The account
  total adds pods, storage (standard and high-performance), public endpoints
  and clusters. **No per-job line exists.**
- **IDs**: billing carries the endpoint id (`serverlessId`) only. The job id,
  `workerId`, `delayTime` and `executionTime` (milliseconds) come from the job's
  own `/run` and `/status` responses. Cine Toaster already keeps those beside
  each take (`<take>.job.json`) and in the spend ledger (`remote`).
- **Units and rates**: amounts only, with no usage seconds and no price per
  hour in the billing records. The currency field is absent (the console uses
  USD).
- **Not verified**: credits, discounts and balance; native tags or labels (none
  appear in the records); retention beyond the 30 days read; rate limits.

Consequence for reconciliation: a job's provider-authoritative cost can only be
**allocated**, not read. The billed amount of an endpoint for one hour is shared
among the Cine Toaster jobs that ran on it in that hour, in proportion to their
`delayTime + executionTime`. The remainder (idle workers inside
`idleTimeout`, cold starts not seen by a job, disk) stays **unattributed**
and is reported as such, never spread silently. On this account, September
billed US$36.44 serverless over 8 endpoints, while the Cine Toaster ledger
recorded about US$0.58: most spend came from tools outside Cine Toaster.
Reconciliation must expect spend that has no Cine Toaster job. October so far
is US$0.89, all standard storage (a network volume) and no job's cost.

### Implemented (CT-0061): read-only observation and allocation

```text
toast finops [--days 30] [--project <film>] [--env-file ~/confyui/.env] [--json]
```

- **Reading:** `providers/runpod_billing.py` reads `GET
  https://api.runpod.io/v2/billing/serverless` (hourly buckets) and turns each
  record into a provider-neutral observation `{provider, resource, start, end,
  usd, components}`. Cloudflare refuses Python's default User-Agent (error
  1010), so the adapter sends its own.
- **Allocation:** `finops.reconcile` gives each known job a share of its
  endpoint's billed hour, in proportion to its billed seconds (`allocated`).
  The job's own seconds at the assumed rate stay beside it (`measured`), so
  the difference shows the idle and cold-start overhead in that hour. A
  billed hour with no known job is `unattributed`, listed, and never spread.
  A job that cannot be placed is `unobserved`, with the reason.
- **Known jobs:**
  - the spend ledger, which now records `endpoint` and `seconds`;
  - with `--project`, the job records the film keeps beside its takes,
    archived ones included and each job counted once, whoever ran them.
    Their time is `finished_at` (recorded since CT-0061) or else the file's
    time, and the row says which (`at_source`).
- The report is cached as operational state (`finops/runpod-latest.json`) and
  can always be rebuilt from the provider.

First reading, on 2026-10-04 (30 days, SINGULAR):
- Billed: US$ 36.44.
- Attributed to the film's 138 job records (LTX): US$ 9.79 (27%).
- Unattributed: US$ 26.65. These are the other endpoints SINGULAR's tools used
  without keeping job records (Krea, Qwen, Wan, lip-sync, music) and LTX
  hours with no record.
- Over the 138 LTX jobs: 5.11 h of job time cost US$ 9.79 billed, an
  effective US$ 1.92/h against the assumed US$ 1.75/h. Estimates run about
  10% low; the gap is idle tail and cold starts.
- One job alone misleads. On 2026-09-29 an LTX block measured at US$ 0.557 was
  billed US$ 0.217 for its whole hour. Its `delayTime` included time waiting
  in the queue with no worker running, which Runpod does not bill. So
  `delayTime + executionTime` overstates a single job when the queue is long.
  The rate should be read over many hours, never from one job.

Do not infer a Runpod feature from this proposal. The adapter should expose only
capabilities verified against the provider.

## Cost ledger

Cine Toaster should keep a rebuildable FinOps ledger/cache derived from its own
job/provenance records plus provider observations. It must not pretend an
estimate is a bill.

A cost record should be able to distinguish:

- **estimated** -- predicted before execution;
- **metered** -- measured usage multiplied by a known rate;
- **provider-reported** -- amount returned by provider billing data;
- **reconciled** -- Cine Toaster work correlated with provider-reported cost;
- **unattributed** -- provider cost that cannot yet be mapped to Cine Toaster;
- **external/untracked** -- Cine Toaster knows the work occurred but lacks
  provider billing visibility.

Illustrative record:

```yaml
cost:
  status: reconciled
  amount: 0.84
  currency: USD
  provider: runpod
  provider_resource_id: ...
  provider_execution_id: ...
  production: singular
  sequence: boreal-arrival
  scene: SC-120
  shot: P07
  take: T03
  agent: generation
  capability: video-generation
  job_id: ...
  started_at: ...
  ended_at: ...
  source: provider-reported
```

The schema is illustrative and should not enter Project Core unchanged before
real provider data has been examined.

## Allocation dimensions

When evidence permits, costs should roll up across both production and digital
workforce dimensions:

```text
account
├── production
│   ├── sequence
│   │   ├── scene
│   │   │   └── shot / take / derivative
│   └── delivery / shared work
└── studio engineering
    ├── development
    ├── tests / benchmarks
    └── research / evaluation
```

And independently:

```text
provider -> capability -> agent -> task/job
```

This enables questions such as:

- How much has Singular cost?
- What is the cost of the Boreal sequence?
- How much GPU spend was rejected versus approved?
- Which capability/model/provider is driving cost?
- How much does the digital workforce cost by role?
- How much spend belongs to production versus Cine Toaster development?
- What provider charges remain unattributed?

Shared infrastructure must not be assigned to a shot through invented
precision. Keep it shared/unallocated or use an explicit documented allocation
rule.

## Native provider cost-centre integration

Where a provider offers its own cost-centre/project/tagging facilities, Cine
Toaster should use them where practical rather than merely reading totals after
the fact.

The ideal integration is bidirectional at the metadata level:

1. Cine Toaster creates/schedules a job with stable production/workforce
   correlation identifiers where the provider permits metadata/tags;
2. the provider meters and bills execution using its native infrastructure;
3. Cine Toaster reads supported billing/cost-centre data;
4. reconciliation maps provider charges back to the originating job;
5. the Digital Workforce Console exposes provider-authoritative cost beside
   Cine Toaster production context.

Cine Toaster must not attempt to modify provider invoices or replace their
billing records.

## Estimates and budgets

Before execution, an adapter may estimate cost from expected duration,
resolution, model, GPU/rate and known provider pricing. The estimate should
carry its assumptions.

Budgets can exist at multiple scopes:

- project/production;
- sequence/scene/shot;
- agent/workforce;
- capability/provider/model;
- Studio Engineering research/benchmark activity.

Possible policy actions:

```text
under budget       -> proceed under normal policy
near threshold     -> warn / request cheaper alternative
over soft budget   -> require explicit approval
over hard budget   -> do not schedule without authorised override
```

A budget is a production policy, not a guarantee that provider billing will
stop. Native provider spending limits/alerts should be used when available and
remain the stronger account-level guardrail.

## FinOps / Finance Console

Cine Toaster should have a dedicated **FinOps / Finance** workspace. The
Digital Workforce Console still exposes cost in the context of evaluating the
workforce; the FinOps Console owns the financial perspective across production,
Studio Engineering and infrastructure/providers.

The two surfaces should deep-link to each other. A cost on an agent can open
its financial breakdown; a charge can lead back to the responsible job, agent,
shot, take or engineering task.

### Overview

The landing view should answer quickly:

- current period spend and budget consumption;
- production versus Studio Engineering spend;
- provider-reported, reconciled and unattributed totals;
- recent cost trend and forecast;
- active budget warnings;
- freshness/coverage of provider reconciliation.

Illustrative layout:

```text
FINOPS / FINANCE
────────────────────────────────────────────────────
Spend this month       $286.40     Budget used   43%
Production             $218.70     Engineering   $67.70
Reconciled             $282.19     Unattributed   $4.21

Productions             Providers             Workforce
Singular  $204.32       Runpod  $181.20        Generation $91.32
  Boreal   $38.14       ...                    Continuity  $ 3.17
    SC-120 $16.72                              ...
      P07  $ 3.84
```

Values are illustrative, not target costs.

### Production economics

The console should drill down through:

```text
production -> sequence -> scene -> shot -> take / derivative -> job
```

Where data permits, derive meaningful production metrics such as:

- average cost per generated take;
- cost per approved take;
- generated/rejected/approved spend;
- retake cost;
- VFX/finishing cost;
- cost per finished minute;
- remaining budget and projected completion cost.

A metric such as cost per finished minute must identify its scope and maturity;
it is misleading early in production if very little footage has reached final
approval.

### Providers and reconciliation

A dedicated provider view should complement, not replace, the provider's native
cost centre:

```text
RUNPOD
Provider reported        $181.20
Reconciled               $176.99
Unattributed               $4.21
Coverage                    97.7%
Last successful sync       4 min ago

[Provider billing/cost centre]   [Investigate unattributed]
```

It should expose provider/product/resource breakdowns when supported, sync
health, reconciliation coverage and unmatched charges. A direct reference/link
to native billing evidence should be retained where possible.

### Budgets and policies

The Finance workspace should manage Cine Toaster budget policy at scopes such
as production, sequence, Studio Engineering, provider, capability or agent.

Illustrative policies:

```text
Singular GPU budget             $2,000
Boreal sequence                   $120
Technology R&D / month            $100
Warning threshold                   80%
Human approval above             $20/job
```

These policies govern Cine Toaster scheduling/approval behaviour. Provider-side
spending controls remain separate and should be used as stronger account-level
guardrails when available.

### Forecast

Forecasting should combine completed/reconciled work with the known production
plan and clearly state assumptions. It should support questions such as:

- At the current approved-shot cost, what is the projected cost to finish the
  production?
- What changes if a sequence needs one additional take per shot?
- Which provider/model/capability is driving the forecast?
- How much budget remains for production versus Studio Engineering?

Forecast values must always be labelled as estimates and remain distinct from
provider-reported spend.

### Efficiency and comparison

When samples are comparable, the Finance workspace can compare models,
providers and workflows by both cost and outcome: cost per attempt, approval
rate, cost per approved output, runtime and rework. It should not rank a cheaper
provider as "better" without accounting for quality/acceptance and workload
differences.

### Digital Workforce integration

The Digital Workforce Console keeps a compact financial lens: cost by agent,
role, task, capability and workforce lifecycle. Detailed budgets,
reconciliation, provider spend and forecasting live in FinOps / Finance.

Both surfaces read the same FinOps records; they must not maintain independent
cost ledgers.

The Finance console must always show currency, period, source/status and data
freshness for financial values.

## Compute economics and adaptive capacity

FinOps must optimise **total compute economics**, not minimise idle time in
isolation. An aggressively small worker pool or idle timeout can cost more
through repeated cold starts, model loading, transfers, retries and production
delay.

A useful decision model considers:

```text
total economic cost =
    execution compute
  + warm idle
  + cold start / provisioning
  + model and asset loading / transfer
  + retries / failures
  + production delay
```

The last term may not appear on a provider invoice, but it matters to production
economics and should be reported separately rather than silently converted into
a fictitious provider charge.

### Capacity Optimizer

Introduce a deterministic **Capacity Optimizer** below the agent layer. It
executes auditable scaling policy; it is not itself an LLM agent.

It should eventually use observed provider/workload telemetry such as cold-start
latency, model-load time, job duration, arrival rate, warm-idle rate, failure
rate and known queued/planned work.

The FinOps Agent can recommend or select an authorised policy. The Capacity
Optimizer applies it.

```text
Production plan / job queue
            |
            v
       FinOps Agent
  economic analysis/policy
            |
            v
     Capacity Optimizer
   deterministic control
            |
            v
     Runpod / providers
            |
      telemetry + billing
            |
            v
 reconciliation / learning
            +-----------------> FinOps Agent
```

### Economic idle timeout

Idle timeout should be based on break-even economics where sufficient data
exists, not a fixed assumption that idle is waste.

The system should estimate whether the expected cost of keeping capacity warm
for a period is lower than the expected cost and delay of terminating it and
later paying for another cold start.

Profiles should be learned separately where economics differ by provider,
resource/GPU, model/workflow and capability.

### Production-aware pre-warming

Cine Toaster has information an infrastructure autoscaler may not have: future
work already implied by the production state. An approved sequence containing
many shots can justify pre-warming capacity before all jobs have entered the
provider queue.

Likewise, as a batch approaches completion the optimizer can drain burst
workers gradually rather than collapsing the whole pool and immediately paying
another cold start.

A possible pattern is:

```text
known batch -> pre-warm -> baseline + burst workers
                         -> drain burst capacity
                         -> retain economical warm baseline
                         -> cooldown/shutdown
```

### Policy modes

High-level modes may provide understandable intent while adaptive logic chooses
actual parameters:

- **Economy** -- favour lower infrastructure spend and tolerate more startup
  latency;
- **Balanced** -- optimise observed total cost against production delay;
- **Production** -- favour continuity of an active production session and use
  pre-warming/burst capacity more readily.

Modes must not hide the resulting budget implications.

### Compute-efficiency analytics

The Finance Console should expose, where measurable:

- useful execution compute;
- useful versus excess warm idle;
- cold-start count, latency and estimated/provider cost;
- model/asset loading time;
- retries/failures;
- production wait attributable to capacity;
- baseline and burst worker utilisation;
- current versus simulated/recommended policy cost;
- estimated savings and assumptions.

This permits the system to detect a policy that appears cheap by idle-time
metrics while being more expensive end to end.

## Agents and FinOps

**Producer / Production Manager** uses FinOps to understand production budget,
expensive blockers and the cost impact of retakes.

**Studio Engineering Agent** uses it to benchmark providers/models/workflows,
track development infrastructure spend and identify cost regressions.

**Meta-agent / Workforce Architect** may use cost as one signal when evaluating
workforce structure, but must not optimise agents solely for cheapness.

**FinOps Agent** is a proposed durable workforce role. It owns economic
analysis and governance across provider reconciliation, budgets, forecasts,
cost allocation, anomaly detection, provider/model/workflow comparisons and
compute-capacity economics.

It should answer questions such as whether a lower idle timeout actually saves
money after cold starts and production delay, or which provider/workflow has
the best cost per approved output rather than merely the cheapest attempt.

The FinOps Agent may recommend capacity policy and authorised budget actions,
but it should **not micromanage workers directly**. Deterministic worker
scaling, warm pools, cooldown and pre-warming belong to the Capacity Optimizer.

**Producer / Production Manager** remains responsible for production
priorities/budget trade-offs; **Studio Engineering Agent** for technical
architecture and operations; **FinOps Agent** for economic efficiency; and
**Meta-agent / Workforce Architect** for whether the digital workforce itself
has the right structure.

## Security and permissions

Billing integrations should default to the least privilege possible:

- read-only billing/usage credentials where providers support them;
- secrets outside project files and provenance;
- no payment-method or invoice mutation capability for ordinary agents;
- explicit human approval for changes to provider spending limits or account
  configuration;
- audit consequential budget-policy changes.

## Reconciliation health

FinOps quality itself needs observability. Track:

- percentage of provider spend reconciled;
- unattributed amount;
- jobs with estimates but no provider observation;
- provider observations with no Cine Toaster job;
- estimate error versus reconciled cost;
- age of last successful billing sync.

A production dashboard should never claim complete cost visibility when the
provider integration is stale or partial.

## Implementation path

1. Define provider-neutral cost observation and attribution concepts.
2. Inspect current Runpod billing/cost-centre/API capabilities with real
   account data and document supported fields.
3. Ensure remote execution records stable provider IDs in job provenance.
4. Implement read-only Runpod cost observation.
5. Reconcile provider observations with Cine Toaster jobs.
6. Expose cost status/source and unattributed spend through API/CLI.
7. Add the dedicated FinOps / Finance Console and Digital Workforce cost lens.
8. Add estimates/budgets only after actual billing reconciliation is reliable.
9. Instrument cold starts, warm idle, model loading and production wait; add the deterministic Capacity Optimizer.
10. Activate the FinOps Agent on top of reconciled cost and compute-economics telemetry.
11. Add future providers behind the same cost adapter boundary.

## Definition of done for a provider FinOps integration

An integration is not complete merely because Cine Toaster can calculate
GPU-rate x runtime. It is complete when it can:

1. identify the upstream source and freshness of cost data;
2. preserve provider execution/resource identifiers;
3. distinguish estimates, metered and provider-reported values;
4. reconcile supported provider charges to Cine Toaster jobs where possible;
5. expose unattributed costs honestly;
6. roll reconciled cost up through production and workforce dimensions;
7. avoid storing billing credentials in production projects;
8. survive missing/stale provider billing APIs without fabricating certainty;
9. test reconciliation and currency/period handling; and
10. provide a path back to the provider's native billing/cost-centre evidence
    where the provider exposes one.

## Open questions

- Which Runpod products expose sufficiently granular billing data today?
- Can Cine Toaster attach correlation metadata/tags to every relevant Runpod
  execution type?
- What provider-side spending controls can be referenced or managed safely?
- What retention period should Cine Toaster keep for cost observations?
- Should cost history live in runtime telemetry, a rebuildable analytics store,
  or exported FinOps records?
- How should shared GPU/Pod idle time be allocated, if at all?
- Which costs belong to a film production versus Studio Engineering?
- Which decisions may the FinOps Agent apply automatically versus only recommend?
- How should production-delay cost be represented without pretending it is a provider charge?
- What confidence/sample threshold is required before adaptive capacity changes a policy?
