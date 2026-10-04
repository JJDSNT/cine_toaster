# Deployment topology — early discussion

Status: **embryonic exploration / discussion starter**

This document intentionally does **not** define a target deployment architecture,
cloud commitment, implementation roadmap or ADR. It exists to start a technical
conversation about how Cine Toaster might eventually operate beyond a single
workstation.

The examples use **Google Cloud Platform (GCP)** only to make the discussion
concrete. GCP is not selected here as the preferred cloud, and the concepts
should remain applicable to other providers and to self-hosted infrastructure.

## Why discuss deployment now

Cine Toaster is local-first today, but several architectural concepts already
raise deployment questions:

- long-running and asynchronous media jobs;
- local and remote GPU execution;
- provider adapters;
- Digital Workforce and agent orchestration;
- production artifacts and provenance;
- FinOps and provider reconciliation;
- adaptive compute capacity;
- Studio Analytics;
- possible future collaboration.

The purpose of this exploration is to identify boundaries worth preserving
before deployment concerns accidentally become coupled to one provider.

## Working hypothesis: three topologies

A useful starting vocabulary is:

### Local Studio

The workstation owns the production environment and executes available
capabilities locally.

```text
Cine Toaster
  -> local project/filesystem
  -> local application runtime
  -> Blender / FFmpeg / other tools
  -> local GPU where available
```

This remains a first-class topology rather than a development-only mode.

### Hybrid Studio

The workstation remains an important production surface while selected jobs
execute remotely.

```text
local Cine Toaster
       |
       +--> local Blender / FFmpeg / editing
       |
       +--> remote job runtime
                 |
                 +--> Runpod
                 +--> GCP GPU
                 +--> other providers
```

This may be particularly appropriate for large media files, interactive local
tools and expensive GPU workloads.

### Cloud Studio

A future topology could place persistent control-plane services, shared
production storage, orchestration and analytics in cloud infrastructure while
compute remains independently schedulable.

```text
Web / Desktop clients
        |
        v
Cine Toaster control plane
        |
   +----+-------------------+
   |        |        |      |
project    jobs    agents  analytics
state
   |
   v
production storage
        |
        v
compute scheduler
   /        |         \
local    cloud GPU   external provider
```

These topologies should not imply three different products or project formats.

## A possible GCP mapping

The following is an **illustrative mapping**, not a recommendation or committed
design.

```text
Clients
   |
HTTPS / events
   |
Cloud Run
  Application API / runtime
  orchestration / agent services
   |
   +--> Cloud SQL / PostgreSQL
   +--> Pub/Sub / Cloud Tasks
   +--> Cloud Storage
   +--> Secret Manager
   |
   +--> Compute scheduler
            |
            +--> GCP GPU workers
            +--> Runpod
            +--> future providers

Operational telemetry
   |
   +--> Cloud Logging / Monitoring
   +--> BigQuery (possible historical analytics)
   |
   +--> Studio Analytics
   +--> FinOps
   +--> Digital Workforce views
```

Possible service relationships include:

| Cine Toaster concern | Illustrative GCP service |
| --- | --- |
| Application API / control plane | Cloud Run |
| Agent services | Cloud Run |
| Asynchronous jobs/events | Pub/Sub / Cloud Tasks |
| Operational/query state | Cloud SQL PostgreSQL |
| Temporary coordination/cache | Memorystore, if justified |
| Production media/artifacts | Cloud Storage |
| Secrets | Secret Manager |
| Container images | Artifact Registry |
| GPU execution | Compute Engine or GKE GPU workers |
| Historical analytics | BigQuery |
| Logs/metrics | Cloud Logging / Monitoring |
| Identity | Identity Platform / IAM, depending on boundary |
| CI/CD | GitHub Actions + GCP deployment services |

The table is deliberately provisional. Service choice should follow measured
requirements rather than becoming architecture by documentation.

## Control plane and compute plane

One potentially durable distinction is between the **studio control plane** and
the **compute plane**.

The control plane understands production semantics: productions, sequences,
scenes, shots, takes, artifacts, agents, decisions, gates, jobs, provenance and
budgets.

The compute plane performs work: generation, rendering, transcoding,
restoration, VFX, upscaling or other resource-intensive operations.

```text
production intent
      |
      v
Cine Toaster control plane
      |
      v
capability / job request
      |
      v
scheduler + provider adapter
   /       |        \
local    GCP       Runpod / other
```

A video model, GPU provider or cloud service should therefore remain a resource
available to the studio rather than becoming the architecture of the studio.

## Storage and filesystem authority

Cine Toaster currently treats the filesystem/project files as canonical
production state. Moving toward cloud operation should not casually replace
that model with a generic CRUD database.

A possible direction is to distinguish:

- **production content and artifacts** — durable object/file storage;
- **operational/query state** — database projections and indexes;
- **analytics state** — rebuildable observations and aggregates.

In a GCP implementation, Cloud Storage could represent durable production
objects while PostgreSQL provides operational indexes and coordination. This is
only a hypothesis: synchronization, versioning, local caching, concurrent
editing and project portability need deeper design before such a mapping can be
accepted.

The cloud database must not silently become a second conflicting authority.

## Asynchronous jobs

Media operations should be assumed to outlive an HTTP request.

```text
request
  -> persist job
  -> queue
  -> schedule
  -> execute
  -> persist artifact + provenance
  -> update outcome
  -> notify interested clients/agents
```

This model fits both local and remote execution and is consistent with the
existing job/provider direction.

## Provider-neutral compute

Cloud deployment should not imply that all media compute moves to the cloud
hosting the control plane.

A GCP-hosted Cine Toaster could still schedule workloads to Runpod or another
provider when appropriate. Conversely, a local Cine Toaster could eventually
schedule a GCP worker.

Provider choice may consider capability, GPU availability, model/workflow,
data locality, latency, queue state, budget and observed economics.

The existing provider/capability boundaries should remain more stable than any
individual provider integration.

## Capacity and FinOps

Cloud deployment makes the relationship between scheduling and economics more
important.

The Capacity Optimizer may eventually reason from observed facts such as warm
idle time, cold starts, model loading, queued and approved future work,
execution duration and provider rates.

FinOps should reconcile Cine Toaster's semantic attribution with
provider-authoritative billing rather than inventing a parallel bill.

This also means that aggressively shutting down workers is not automatically
optimal: total compute economics may favor a warm baseline when another batch
is likely soon.

## Digital Workforce

Agents should not require one permanently running server or container per
cinematic role.

A future agent runtime can activate roles against the Application API and
canonical project state as work requires. Permissions, human gates and durable
decisions remain more important than where the process happens to execute.

The Meta-Agent / Workforce Architect must not receive unrestricted cloud
administration simply because it can design or create workforce roles.
Creating an agent and granting infrastructure authority remain separate
operations.

## Common telemetry

Local, hybrid and cloud operation should ideally emit compatible operational
facts so that Studio Analytics, FinOps and Digital Workforce views do not
become cloud-only concepts.

Useful correlation dimensions may include production/sequence/scene/shot/take,
agent/task, capability/workflow/model, provider/resource, job timestamps,
cold-start/model-load/execution time, outcome and cost status.

The exact event schema is outside the scope of this document.

## Security questions

A cloud topology introduces questions that do not need final answers yet but
should remain visible:

- identity and tenancy boundaries;
- encryption and key ownership;
- signed/temporary media access;
- service-to-service authorization;
- provider credentials and least privilege;
- isolation between productions;
- agent permissions;
- auditability of consequential actions;
- retention and deletion of large media artifacts;
- whether creative material may leave a chosen execution boundary.

These concerns should be designed before multi-user or hosted operation is
treated as production-ready.

## What this document does not decide

This exploration does **not** decide:

- GCP versus AWS, Azure, another provider or self-hosting;
- Kubernetes versus serverless as the global runtime;
- whether Cine Toaster becomes a hosted SaaS;
- a multi-tenant data model;
- the final remote filesystem/storage model;
- collaboration semantics;
- GPU purchasing/reservation strategy;
- a production SLA;
- cloud pricing or subscription model;
- migration of existing local projects;
- whether every local capability must have a cloud equivalent.

In particular, **GKE should not be assumed as the default merely because GPU
workers may eventually use Kubernetes**. A smaller control plane based on
managed/serverless services may be sufficient until measured requirements say
otherwise.

## Questions for the next discussion

Before this becomes an architecture decision, useful questions include:

1. Which parts of Cine Toaster genuinely need to be persistent services?
2. What must remain usable with no cloud account or network connection?
3. How should one project move between Local, Hybrid and Cloud topologies?
4. What remains canonical when project files are cached locally and stored
   remotely?
5. Which jobs benefit from data locality enough to affect provider selection?
6. How should remote workers obtain only the assets and secrets needed for one
   job?
7. What collaboration model, if any, is actually required?
8. At what scale does BigQuery, GKE or another heavier service become
   justified?
9. Which telemetry is required to compare local and remote economics fairly?
10. What is the smallest deployment experiment that could answer these
    questions without committing the architecture prematurely?

## Current position

The useful decision at this stage is not **"deploy Cine Toaster on GCP."**

It is to preserve an architecture in which Cine Toaster can plausibly operate
as a **Local Studio, Hybrid Studio or Cloud Studio**, with production semantics
above provider-specific infrastructure.

GCP provides a concrete example with which to test that idea. The deployment
model remains deliberately embryonic and should evolve through experiments,
production evidence and explicit architecture decisions.
