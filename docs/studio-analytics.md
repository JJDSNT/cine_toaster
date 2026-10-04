# Studio Analytics and usage telemetry

Status: **architectural proposal / pending implementation**

Cine Toaster should be able to observe not only what it costs and what its
digital workforce does, but **how the studio is actually being used**.

This document proposes a provider-neutral, local-first Studio Analytics layer.
Its purpose is operational learning: understand production profiles, capability
adoption, resource usage, outcomes and efficiency so architecture and production
decisions can be based on evidence rather than assumptions.

## Three complementary perspectives

The analytics surfaces answer different questions:

- **Studio Analytics / Usage** -- how is Cine Toaster actually being used?
- **FinOps / Finance** -- what does that usage cost and how can compute be used
  economically?
- **Digital Workforce Console** -- how are agents and roles performing and
  collaborating?

They should share telemetry rather than create independent tracking systems.

## Common telemetry model

Runtime activity should emit structured events that can support multiple views:

```text
Cine Toaster Runtime
        |
        +-- production events
        +-- agent events
        +-- capability events
        +-- job events
        +-- resource events
        +-- artifact events
        +-- decision/outcome events
                 |
                 v
          Usage Telemetry
                 |
          Studio Analytics
          /       |       \
       Usage    FinOps   Workforce
          \       |       /
        Meta-Agent / Studio Engineering
```

The filesystem/project state remains authoritative for production. Analytics is
a rebuildable observation/projection layer, not a second source of truth.

## Usage dimensions

Where evidence exists, usage should be explorable by dimensions such as:

- production/project type: feature, short, trailer, commercial, music video,
  test/R&D and future types;
- genre/style where explicitly declared;
- production stage: screenplay, breakdown, storyboard/previs, generation,
  review, edit, VFX, sound, finishing and delivery;
- capability: image/video generation, 3D previs, matting, restoration, HDR,
  detail refinement and future capabilities;
- resource: GPU, CPU, storage and network;
- tool: Blender, ComfyUI, FFmpeg, Ardour and future tools;
- provider and execution environment: local, Runpod and future providers;
- model/workflow;
- digital-workforce role/agent;
- artifact type: image, video, audio, 3D, matte, EXR and future formats;
- outcome: generated, selected, approved, rejected, regenerated, failed,
  superseded or pending;
- time: execution, queue, cold start, model loading, waiting and human
  intervention;
- cost, through the shared FinOps model.

Taxonomies should be extensible and should not force every project into a film
feature schema.

## Studio Analytics workspace

A dedicated **Studio Analytics** workspace should provide a usage-oriented view
of the studio.

An illustrative overview:

```text
STUDIO ANALYTICS — last 30 days

Production profile
Feature film                         72%
Tests / R&D                          18%
Short form                           10%

Production activity
Video generation                     38%
3D previs                            21%
Image generation                     16%
VFX / finishing                      11%
Sound                                 8%
Other                                 6%

Resources
GPU                                  84%
CPU                                  11%
Other                                 5%

Outcomes
Approved                             31%
Rejected                             42%
Pending                              12%
Technical failure                     4%
Other                                11%
```

Values are illustrative only.

Useful navigation should allow dimensions to be crossed rather than only viewed
as isolated totals. For example:

```text
Feature film
  -> video generation
    -> provider
      -> model/workflow
        -> resource/GPU
          -> outcome
```

## Capability adoption

Studio Analytics should show which Cine Toaster capabilities are actually being
used and in what production contexts.

Examples include adoption rate, frequency, recency, productions using the
capability, downstream outcomes and maintenance/operational burden where known.

This gives Studio Engineering evidence for questions such as whether a rarely
used capability remains worth maintaining or whether a heavily used workflow
deserves deeper product support.

Low usage alone is **not** sufficient reason to remove a capability. Some
capabilities are rare but strategically or technically necessary.

## Outcome and effectiveness analysis

Usage becomes especially valuable when correlated with outcomes.

For example, once samples are comparable the system may investigate whether
shots using 3D previs require fewer generation attempts, whether continuity
checks reduce rework, or whether a particular workflow improves approval rate.

Such observations must distinguish **correlation from causation**. Studio
Analytics should report sample size, scope and time period and avoid presenting
small or heterogeneous samples as proof.

## Usage + FinOps

Studio Analytics and FinOps should be joinable through common job, artifact,
production, capability and provider identifiers.

This enables questions such as:

- Does a capability add compute cost but reduce rejected generations?
- Which workflows have the lowest cost per approved output?
- Which project types dominate GPU consumption?
- How much capacity is consumed by production versus tests/R&D?
- Is previsualisation economically justified by reduced downstream rework?

The financial source/status remains owned by the FinOps model. Usage Analytics
must not manufacture cost estimates independently.

## Usage + Digital Workforce

The same telemetry can reveal which agents/capabilities are used in which
production contexts, handoff frequency, human intervention and outcome patterns.

This evidence may inform the Meta-Agent / Workforce Architect. For example, a
repeated high-volume workflow with no durable specialist competence may justify
a proposed skill or agent.

Conversely, agent creation should never be triggered solely by usage count.
Creation, authority and lifecycle remain governed by Digital Workforce policy.

## Privacy and telemetry boundaries

Studio Analytics is primarily **internal studio telemetry**. A local Cine
Toaster installation should be able to obtain its own analytics without sending
production telemetry to a central service.

If a future distribution chooses to offer optional aggregate product telemetry,
that must be a separate, explicit design with clear consent, data minimisation
and privacy policy. It must not be silently conflated with this operational
analytics layer.

Sensitive screenplay/content data is not required for most usage metrics.
Prefer identifiers, declared classifications and operational metadata over
capturing prompts or creative content merely for analytics.

## Retention and aggregation

Raw events and aggregates have different value and cost. The implementation
should define retention independently for:

- raw operational events;
- per-job/per-artifact observations;
- daily/period aggregates;
- long-term production summaries.

Analytics should preserve enough lineage to explain important metrics without
requiring indefinite retention of every low-level event.

## Consumers

**Producer / Production Manager** can understand production throughput,
rework and bottlenecks.

**Studio Engineering Agent** can use adoption, failures, resource profiles and
workflow outcomes to prioritise engineering and capability investment.

**FinOps Agent** can combine usage with reconciled costs and compute economics.

**Meta-Agent / Workforce Architect** can use usage as one evidence source when
evaluating skills, roles and workforce gaps.

Humans retain the ability to inspect the underlying evidence before
consequential architecture or workforce changes.

## Implementation path

1. Define stable event envelopes and correlation IDs across runtime, jobs,
   artifacts, agents and production hierarchy.
2. Reuse existing job/provenance facts rather than emitting duplicate facts
   where possible.
3. Define extensible production-type, capability, resource and outcome
   dimensions.
4. Build a local rebuildable analytics projection/store.
5. Expose basic usage queries through the Application API/CLI.
6. Add the Studio Analytics workspace with production profile, capability,
   resource and outcome views.
7. Join analytics with FinOps cost records and Digital Workforce records.
8. Add adoption/effectiveness analysis only when sample size and data quality
   support it.
9. Allow Meta-Agent and Studio Engineering recommendations to cite analytics
   evidence.

## Definition of done

The first Studio Analytics implementation should be able to:

1. describe the production/project mix over a selected period;
2. attribute activity to production stages and capabilities;
3. report resource/provider/model/workflow usage where known;
4. distinguish outcomes such as approved, rejected and failed work;
5. drill from aggregate usage to supporting jobs/artifacts;
6. join usage to FinOps without duplicating the cost ledger;
7. join usage to Digital Workforce without creating a second agent registry;
8. report scope, period and data freshness;
9. work locally without requiring external analytics telemetry; and
10. avoid collecting creative content when operational metadata is sufficient.

## Open questions

- Which event/provenance facts already exist and can be projected rather than
  newly instrumented?
- Which project-type taxonomy belongs in core versus project-defined metadata?
- What is the minimum useful raw-event retention?
- Which outcome states are universal enough to standardise?
- How should human work/intervention be represented without invasive tracking?
- Which effectiveness metrics are meaningful enough to influence automated
  recommendations?
