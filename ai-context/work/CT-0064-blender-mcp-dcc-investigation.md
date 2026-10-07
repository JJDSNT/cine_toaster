---
id: CT-0064
title: Investigate Blender MCP and DCC-MCP as an agent-operated DCC interface
type: work
status: backlog
owner: unassigned
created_at: 2026-10-07
updated_at: 2026-10-07
tags:
  - blender
  - mcp
  - dcc
  - agents
  - previs
  - storyboard
  - research
---

# What

Investigate, evaluate and, if the evaluation supports it, prototype an MCP
interface for agent-operated Blender workflows in Cine Toaster.

The candidates to study include **Blender MCP implementations** and the broader
**DCC-MCP** approach. This item records an investigation, not an architectural
commitment and not a dependency decision.

The question is not whether Blender belongs in Cine Toaster: it already does.
The question is whether MCP is a useful **agent-facing control surface** over
Blender and, potentially, other Digital Content Creation (DCC) applications.

# Context

Cine Toaster already has deterministic Blender-based paths:

- CT-0029 defines 3D previs derived from Cine Toaster records;
- CT-0049 implements Blender-rendered 3D storyboards, depth output and animatics;
- USD is already an interchange boundary for planned scene geometry;
- camera, blocking, storyboard, VFX and spatial-media work already depend on
  structured Cine Toaster records rather than on an opaque Blender scene.

Those properties must not be lost merely to make Blender agent-operable.

The promising architectural distinction is:

```text
                         Cine Toaster
                              |
                     production/project model
                              |
             +----------------+----------------+
             |                                 |
    deterministic adapters             agent / assistant
             |                                 |
             |                          semantic capability
             |                                 |
             |                              MCP / DCC
             |                                 |
             +-------------> Blender <---------+
                              |
                  previs / board / camera /
                  set / lighting / render
```

MCP would therefore be an additional interaction path, not automatically the
replacement for existing adapters.

# Hypothesis

MCP may be valuable where an agent must **inspect, reason about and iteratively
modify** a DCC scene: for example, trying alternative framing, arranging a
blockout, placing set pieces, adjusting lighting for a previs, or producing
several composition candidates.

A deterministic adapter remains preferable when the desired operation is
already completely specified by Cine Toaster records and must be reproducible,
testable and cheap to replay.

A useful long-term boundary may be:

```text
Cine Toaster semantic intent
        -> DCC capability interface
        -> MCP implementation / deterministic adapter
        -> Blender (and potentially another DCC)
```

Agents should ideally reason in production vocabulary such as
`place_subject`, `set_camera`, `set_lens`, `frame_subject`,
`inspect_scene`, `render_board` and `render_preview`, rather than depend
directly on Blender Python details.

# Architectural constraints to preserve

1. **Cine Toaster remains the source of truth.** A `.blend` file must not
   silently become the canonical project model.
2. **Structured decisions return to the project.** An agent-originated camera,
   blocking or composition change that is accepted must be representable in
   Cine Toaster records and lineage where applicable.
3. **Determinism remains available.** Existing reproducible paths should not be
   replaced merely because an MCP tool can perform the same action.
4. **MCP is a capability boundary, not business semantics.** Cine Toaster owns
   filmmaking concepts; an MCP server exposes operations on a DCC.
5. **Human gates still apply.** Agent exploration must not bypass established
   approval/adoption semantics.
6. **Arbitrary code execution is not the default production interface.** If a
   candidate exposes unrestricted Blender Python execution, treat that as a
   privileged development/debug capability and evaluate its security and
   reproducibility implications separately.
7. **Do not make Blender-specific assumptions unnecessarily.** Evaluate whether
   a semantic DCC layer can leave room for Unreal, Unity or another tool
   without pretending that all DCCs have identical capabilities.

# Candidates and questions to investigate

Evaluate at least:

- one established Blender-specific MCP implementation;
- **DCC-MCP / its Blender integration**, especially whether its abstraction and
  typed tools are suitable for a production agent rather than only an
  interactive coding assistant;
- the current deterministic Blender/CLI/USD path as the baseline.

For every candidate, record:

- license, maintenance activity and project maturity;
- supported Blender versions and installation model;
- transport and deployment topology (local Blender, remote worker, container,
  RunPod or workstation);
- tool discovery and typed schemas;
- scene inspection/read capabilities;
- object, collection, camera, lens, light and material operations;
- import/export, especially USD/glTF and project assets;
- render and viewport capture capabilities;
- whether tools return enough structured state for an agent to verify actions;
- transaction/undo/recovery behaviour;
- concurrency and session ownership;
- headless support;
- arbitrary-code-execution surface;
- authentication/network exposure;
- observability, timeout and cancellation behaviour;
- suitability for Cine Toaster's job runtime and FinOps accounting;
- how changes can be translated back into canonical Cine Toaster records.

# First spike

Do not begin by replacing the board renderer.

Use a disposable copy of a small existing Cine Toaster scene and test an
agent-operated composition loop:

1. materialize/open the scene from canonical Cine Toaster records;
2. inspect the scene through MCP;
3. select an existing shot;
4. create two or three camera/framing alternatives using semantic instructions;
5. render inexpensive previews;
6. inspect the resulting camera state;
7. translate the selected alternative back into Cine Toaster camera records;
8. regenerate the deterministic board from those records;
9. compare the MCP-created preview with the deterministic regeneration.

Success is not merely "the agent controlled Blender". The important result is
that an exploratory agent action can round-trip through the canonical model
without losing provenance or reproducibility.

# Evaluation outcome

After the spike, choose explicitly among:

- **adopt**: MCP becomes a supported agent-facing DCC capability;
- **adopt narrowly**: use it only for exploratory/interactive operations while
  deterministic adapters remain the production execution path;
- **learn and wrap**: retain useful protocol/tool ideas but implement a
  Cine-Toaster-owned DCC capability server/adapter;
- **defer**: promising but operationally immature;
- **reject**: complexity, security, fidelity or state-management costs exceed
  the benefit.

If adoption changes a durable architectural boundary, write a separate ADR at
that point. This work item deliberately does not make that decision in advance.

# Relationship to existing work

- CT-0029 — previs and Blender as a later 3D stage.
- CT-0049 — engines, USD and the implemented Blender 3D storyboard.
- CT-0044 / CT-0045 — assistant and external agent interaction.
- Existing MCP support and tests provide the natural protocol context, but a
  Blender/DCC server must not be confused with Cine Toaster's own MCP surface.

# Done when

This investigation is complete when:

- the candidate implementations have been compared against the baseline;
- one end-to-end spike has exercised inspect -> modify -> preview -> read back;
- security and remote-worker implications are recorded;
- round-trip behaviour into Cine Toaster's canonical records is demonstrated
  or its failure is explained;
- an explicit adopt/narrow-adopt/wrap/defer/reject recommendation is recorded;
- an ADR is created only if a durable architecture decision is actually made.
