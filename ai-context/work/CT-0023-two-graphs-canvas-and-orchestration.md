---
id: CT-0023
title: Two graphs — the production canvas and agent orchestration (LangGraph)
type: work
status: ready
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - interface
  - nodes
  - orchestration
  - langgraph
  - evaluation
---

# What

Decide what the node interface is and where LangGraph could fit, before either
is built. Define the interface that SPEC-0005 (movement within a shot) needs.
The outcome is a position and two spike plans, not an adoption.

# Why

The user asked for a node view in Arcads' style and asked whether LangGraph
could be used. Both are graphs, and the risk is building one graph that
tries to be both. ComfyUI is that single graph: its nodes are the execution
pipeline, which is why CT-0022 rejected it as the model. A canvas whose nodes
run things becomes a second source of truth for the film, and that breaks the
first invariant in `AGENTS.md`.

# The two graphs

| | Production canvas | Orchestration graph |
| --- | --- | --- |
| Answers | What is the film, and how do its parts relate? | How does work get done, and in what order? |
| Nodes | Scenes, shots (with the selected take), cast, looks, locations | Steps: derive brief, generate, check, human gate, select |
| Edges | Cuts, references, and lineage (which take came from which reference) | Control flow: next, retry, branch, wait for a person |
| Source of truth | Project records; the canvas is a projection (CT-0022) | Built-in workflow state; checkpoints are operational state |
| Edits | Application commands (`select_take`, a future `set_cut`) | Never edits the film directly; calls the same commands |
| Library candidate | React Flow (MIT) | Built-in state machine first; LangGraph (MIT) as an adapter candidate |

The two meet on a card. A shot card can show that a job is running, and its
"generate" action issues a command that starts a workflow. The canvas never
defines the pipeline, and the pipeline never owns the film.

# Arcads-style canvas: first version

- **Layout.** Sequences are horizontal lanes and scenes are groups within them.
  Shots are cards in cut order, showing the selected take's still, duration,
  camera and move chips (SPEC-0005), and review status.
- **Edges between shots are cuts.** Each edge shows the cut's findings
  (`cut_screen_flip`, and later the cut record from CT-0022 step 2). Clicking
  an edge opens the cut inspector.
- **Side cards** hold cast and looks, with reference edges to the shots that use
  them (SPEC-0003 lineage). These are hidden by default so the canvas stays
  readable.
- **Actions** on a card are the existing commands, such as choosing a take.
  Later actions such as generate or regenerate appear only when those commands
  exist.

# Interface for SPEC-0005

- **Blockout.** The blockout draws marks, subject paths (start → end arrows,
  numbered by shot), and camera paths with the frustum at the start and at the
  end. Selecting a shot shows the state at its start and end. Findings are
  highlighted on the plan.
- **Cut inspector.** It is shared by the Cut room and a canvas edge. It shows
  the exit state of shot N beside the entry state of shot N+1: the plan, the
  screen side of each subject, and later the last and first frames of the
  selected takes.
- **Brief preview.** This is what SceneFlow teaches. It shows the derived brief
  for a shot or scene, with every slot badged *authored*, *derived*, or
  *missing*, so the gaps are visible before generating.

# LangGraph assessment (from documentation; no spike yet)

**Where it fits.** It fits only in the orchestration graph, behind the
`orchestration/` adapter boundary that `architecture.md` already reserves. It
matches the conditions `agent-architecture.md` sets for considering an
external orchestrator:

- a Python runtime;
- persistent state with checkpoints;
- human-in-the-loop interrupts, which could back our gates;
- retries and branching;
- an AG-UI integration, relevant to Phase 5.

**Where it does not fit.** It is not the canvas and not a file format. It is
not in the Project Core.

**Risks to test before adopting:**

- **Checkpoints as a shadow film.** A decision that lives only in a LangGraph
  checkpoint violates "human gates and creative decisions are production
  records". Every interrupt must resolve through a command that writes the
  record, and the checkpoint store must be disposable.
- **Dependency weight.** Measure what installing it pulls into a
  dependency-free runtime, and whether it can stay an optional extra.
- **Workflows defined in code.** Workflow definitions would be Python code, not
  project data. That is acceptable for application workflows, but a production
  must not need one.
- **Cancellation and recovery** across application exit, per the adoption
  criteria.

**When.** Not before the built-in workflow exists (roadmap Phase 5: "a small
built-in workflow ending at a real human gate"). The spike then runs the same
workflow on LangGraph and compares the two. Adopting it earlier would decide
the orchestration model before there is a workflow to orchestrate.

# To do

1. ~~Blockout paths and marks~~ done with SPEC-0005: marks, subject paths,
   camera paths, and a shot selector showing start and end state. Still to do:
   the brief preview, which needs the brief builder (CT-0022 step 3
   follow-up), and the cut inspector, which needs the cut record (CT-0022
   step 2).
2. **Canvas spike** (CT-0022 step 5). React Flow requires React, and the UI is
   vanilla ES modules (`development/frontend.md`: keep it until a React
   replacement reaches parity for a room). Build the canvas as the first React
   room in a separate Vite package that talks only to the existing HTTP API.
   The decision to recommend: is the node canvas the room that justifies
   adding a Node/Vite toolchain? The alternative is a plain SVG canvas in the
   vanilla UI, which is enough to validate the interaction but not to scale.
3. **LangGraph spike** after Phase 5's built-in workflow: the same workflow,
   the same gate, and a comparison of persistence, recovery, cancellation,
   observability, dependency cost, and how gates become records.

# Decisions

- **Correction, 2026-09-29 (CT-0024).** Arcads' Workflow is an executable DAG,
  so "Arcads-style = objects, not execution" was wrong. The separation that
  still holds is about **authority and abstraction level**, not about
  whether a canvas can run things:
  - One canvas may show entity nodes (project records) and step nodes
    (instances of creative workflow templates).
  - Steps execute in the orchestration layer and write takes with lineage.
    Nothing is canvas-only state.
  - Nodes stay at the level of creative operations. Model internals
    (ComfyUI) stay behind the provider adapter.

  The table above still describes the two *layers* correctly; they may
  share one visual surface.

- The canvas and the orchestration graph are separate. The canvas projects
  records and edits through commands. Orchestration never edits the film
  except through the same commands.
- LangGraph is a candidate for the orchestration adapter only. It is not
  adopted, and it is not considered before the built-in workflow exists.

# Validation

- Design and documentation only. It was checked against `AGENTS.md`
  invariants, `architecture.md`, and `agent-architecture.md` (Orchestration and
  AG-UI sections). LangGraph capabilities are stated from its public
  positioning and not verified by a spike.
