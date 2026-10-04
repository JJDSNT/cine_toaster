# Production validation targets

Status: **product validation strategy**

Cine Toaster should be validated by producing real audiovisual work with the
same system it intends to offer. Individual capability demos are useful, but
they are not sufficient evidence that the studio works as an integrated
production environment.

Two complementary validation targets are defined here.

## Target A — Singular: Prologue to Title

The primary narrative vertical slice is the opening of **Singular**, from the
prologue through the appearance of the film title.

This supersedes the Boreal Station sequence as the primary Singular validation
target. The Boreal Station remains a useful later benchmark, especially for
spatial continuity, 3D blocking and layout-guided generation.

### Why this sequence

The opening deliberately stresses different forms of filmmaking in one
continuous production:

- conceptual/abstract audiovisual language in the prologue;
- transition from abstraction into narrative;
- character and environment continuity;
- hospital-room and corridor staging;
- ATLAS drones and world-building;
- exterior/city cinematography;
- camera/blocking/previsualisation decisions;
- generative character performance rather than Blender-controlled final
  character animation;
- sound, music, edit, VFX/finishing and title design.

The current narrative validation span is:

```text
Prologue
  patterns -> prediction -> learning -> creation
  -> AGI / Metropolis
  -> sentience / Maria
  -> singularity / black
        |
        v
Claire / hospital
        |
        v
corridor / ATLAS
        |
        v
hospital exit / Kael
        |
        v
Geneva / drones / panorama
        |
        v
SINGULAR title
```

The exact screenplay remains production content outside the generic Cine
Toaster architecture. This document records the validation boundary, not a
hard-coded product workflow.

### What it should prove

The target is complete when this sequence can travel coherently through the
production system rather than being assembled through undocumented parallel
processes:

```text
screenplay
 -> breakdown / directing decisions
 -> shot planning
 -> storyboard / 3D previs where useful
 -> reference/master imagery
 -> generation and takes
 -> review / selection
 -> continuity
 -> edit
 -> VFX / finishing / titles
 -> sound / music
 -> delivery
```

The same run should provide enough operational evidence to exercise job
provenance, Digital Workforce decisions/handoffs, provider execution, FinOps
attribution and Studio Analytics.

Success is not merely that every subsystem was invoked. The resulting sequence
must work as cinema.

## Target B — Cine Toaster self-demo / advertisement

A second validation target should prevent the product from being shaped only
around the needs of Singular.

Cine Toaster should eventually **produce its own demonstration/advertisement
using Cine Toaster**.

The conceptual reference is the classic style of Video Toaster product
demonstration: first establish what the system can do, then demonstrate those
capabilities in actual use. The goal is not to reproduce a historical video
shot-for-shot, but to adopt that two-act communication structure.

### Act I — What Cine Toaster can do

The first movement presents the product proposition and major production
capabilities. Depending on the maturity of the product at production time this
may include screenplay intelligence, directing/shot planning, storyboard and
3D previs, generative production, takes and continuity, editing, VFX/titles,
sound, finishing, Digital Workforce, FinOps and Studio Analytics.

Only capabilities that can actually be demonstrated should be claimed.

### Act II — Cine Toaster doing it

The second movement reveals those capabilities through the production of the
advertisement itself.

The demonstration should expose enough of the real workflow to make the claim
self-evident:

```text
describe capability
       |
       v
show Cine Toaster using capability
       |
       v
show resulting audiovisual artifact
       |
       v
show how it participates in the finished advertisement
```

This creates a recursive proof:

> Cine Toaster is capable of producing this kind of audiovisual work, and the
> advertisement making that claim was itself produced by Cine Toaster.

### Why this is a separate validation target

Singular stresses **long-form narrative filmmaking, continuity and cinematic
quality**.

The self-demo stresses a different profile:

- short-form/commercial communication;
- product storytelling;
- interface/product capture;
- graphics, titles and motion design;
- fast editorial rhythm;
- deliberate demonstration of capabilities;
- potentially different generation, sound and finishing patterns.

Together they reduce the risk that Cine Toaster becomes a bespoke Singular
production pipeline disguised as a general product.

## Validation matrix

The two targets should overlap where appropriate but need not exercise every
capability equally.

```text
                         Singular opening       Cine Toaster self-demo
Narrative continuity          primary                 secondary
Character consistency         primary                 optional
Abstract imagery              primary                 useful
3D previs / blocking          primary                 demonstrable
Generation / takes            primary                 primary
VFX / titles                  primary                 primary
Sound / music                 primary                 primary
Product/UI storytelling       low                     primary
Digital Workforce             observed                demonstrated
FinOps                        observed                demonstrable
Studio Analytics              observed                demonstrable
Long-form readiness           proxy                   low
Short-form/commercial         low                     primary
```

## Product principle

These targets are **reference productions, not special cases in code**.

No Project Core concept should depend on Singular, on the self-demo, or on a
specific provider/model. When either target exposes a missing capability, the
solution should be expressed as a reusable production concept when justified.

A capability should not be added merely to satisfy a checklist. The validation
productions exist to discover real production walls and to test whether Cine
Toaster can solve them coherently.

## Evidence of progress

Progress should increasingly be reported in terms of production evidence:

- how much of each target can pass end to end;
- where manual or undocumented workarounds remain;
- which human gates and agent decisions are durable;
- how many attempts/takes are required;
- continuity and approval outcomes;
- execution time and bottlenecks;
- provider/resource profile;
- reconciled cost and compute efficiency;
- capability adoption/effectiveness visible in Studio Analytics.

This makes the validation productions shared benchmarks for Production,
Digital Workforce, Studio Engineering, FinOps and Studio Analytics.
