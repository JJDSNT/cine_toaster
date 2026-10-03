---
id: CT-0024
title: Spike — how the reference repositories and Arcads build a node canvas
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-10-03
tags:
  - interface
  - nodes
  - react-flow
  - copilotkit
  - evaluation
---

# What

Read how the node canvases in the reference repositories actually work, and
compare them with Arcads. The goal is to settle two things before building
anything: the canvas model (CT-0023) and the interface stack. The stack
decision includes CopilotKit, which only runs on React.

# Why

The user listed several open questions, the biggest being that adopting
CopilotKit implies choosing a UI stack. A canvas decision made without looking
at working implementations would repeat known mistakes. This spike reads the
code, not the READMEs.

# Done

The six repositories were shallow-cloned into a session scratch directory on
2026-09-29. No code was copied into this repository (ADR 0011: SPITE is AGPL
and AI Video Production Editor is GPL; CineGen has no licence).

| Repository | Stack | Canvas library | What a node is | Where the graph lives | How agents or AI enter |
| --- | --- | --- | --- | --- | --- |
| Noder `520b15b` (MIT) | React 18, Vite, Tauri 2, zustand | `reactflow` 11 | An operation or a medium: text, image, video, audio, upscaler, chip, group | JSON workflow files in app data | OpenRouter assistant panel |
| Node Banana `65746ad` (MIT) | React 19, Next 16, zustand, Vercel `ai` | `@xyflow/react` 12 | An **operation**: 29 types, including generate image/video/audio, trim, stitch, router, switch, and a `comfyApp` node | Portable JSON workflows | Prompt-to-workflow through an LLM |
| CineGen `769f148` (none) | React 19, Vite, Electron, SQLite | `@xyflow/react` 12 | **One node type per model** from a catalog, plus utilities | Project SQLite database; execution in topological order | An LLM chat, and an MCP build |
| SPITE `35ae9b1` (AGPL) | React 19, Next 16, Postgres | `@xyflow/react` 12 | A few media nodes (prompt, reference, image, video, comment, sticker), each **tagged with `sceneId`/`shotId`** | `canvas_nodes`/`canvas_edges` tables | An LLM assistant for prompts |
| AI Video Prod. Editor `07ae563` (GPL) | React 18, Vite, Electron, Supabase | `reactflow` 11 | ComfyUI-style operations: prompt, model, sampler, upscale, openpose, depth… | Node graph state inside the project | A studio agent that runs production phases |
| BeatDesign `d2ef270` (Apache-2.0) | React 19, Vite, SQLite (drizzle) | `@xyflow/react` 12 | **Three card types**: an asset card, a generation card, and a workflow group, joined by **reference edges** | A project snapshot changed only through typed canvas commands | An **MCP server that writes through the same command kernel** |

## Findings

1. **React Flow is the consensus.** All six use it: four on `@xyflow/react`
   12 and two on the older `reactflow` 11. None built its own canvas engine.
2. **No repository uses CopilotKit.** Their AI entry points are an LLM chat
   panel (Noder, CineGen, SPITE), the Vercel `ai` SDK (Node Banana), or MCP
   tools (BeatDesign, CineGen). CopilotKit is therefore *our* bet to prove,
   not an observed practice. Its alternative for agent access is MCP, which
   BeatDesign shows working well.
3. **Two families of canvas exist, and the split matches CT-0023.**
   - **Execution graphs.** Node Banana, CineGen, Noder, and AI Video
     Production Editor are ComfyUI in spirit: a node is a step, and edges
     carry data between steps. AI Video Production Editor keeps this graph
     in a separate "node workspace", away from its production phases. That
     supports keeping the two graphs apart.
   - **Object canvases.** BeatDesign is Arcads-like: a card is a produced
     thing (an asset or a generation), and an edge means "was made from".
     SPITE sits between the two families: a media node is tagged with a
     scene and shot, and the shot list is *derived from the tags*.
4. **BeatDesign is the closest to our architecture, not only visually.**
   - Canvas changes are typed operations (`upsert_card`, `set_references`,
     `move_card`, `upsert_timeline_node`…).
   - Operations run through a command kernel with conflict retry and
     receipts.
   - Its MCP server persists through the same kernel.

   That is our rule that the GUI, the CLI, and agents share one command
   path, and here it has been implemented and tested by someone else. Its
   **lineage focus** is worth reimplementing: selecting a card highlights
   what it came from and what came from it, and dims the rest. That is how a
   large canvas stays readable.
5. **In every repository, the canvas is the store.** In BeatDesign and SPITE,
   node positions, and even shots, exist only as canvas data. Our position
   differs: the film lives in project files, and the canvas projects them.
   That leaves one question the references do not answer: **where card
   positions live.** Options:
   - always auto-layout: sequence lanes, cut order, no stored positions;
   - disposable operational state per project, the same class as window
     layout;
   - an optional authored layout file.

   The first two respect the invariants. The third makes layout a production
   record and should need a reason.
6. **SPITE's tagging is the anti-pattern for us.** Deriving shots from tags
   on canvas nodes makes the canvas the authority on what a shot is. We have
   shot records; cards must render them, never define them.

## Arcads (secondary source)

Source: a summary of Arcads' public documentation, made with ChatGPT and
supplied by the user on 2026-09-29. It has not been verified first-hand; the
summary's own citations were not preserved.

- **The Workflow is an executable DAG.** Nodes fall into three groups:
  **inputs** (product image, script, actor or reference), **models**
  (generate image, generate video, talking actor, B-roll), and **tools**.
  Pressing Run executes the graph in order. Workflows are built once and
  reused at scale.
- **The connections are semantic, not technical.** The chain is
  Reference → Image → *Start Frame* / *End Frame* → Video; there is no
  LATENT → KSampler → VAE. Models accept references and start and end
  frames.
- **Fan-out produces variations.** One asset feeds many nodes. The official
  example takes a product, a script, and ten actors, and produces two
  talking-head versions per actor, including translations: 20 videos.
- **"Clothing Brand Film"** uses storyboard images as the start and end frames
  of each transition. **Storyboard 02 is the end of shot 1 and the start of
  shot 2**, so the shared frame *is* the cut. This is CT-0022's cut strategy
  (a), made visible as a graph.
- **Tools** exist in the platform: extend video, extract frame, camera angle,
  edit, translate, upscale, camera movement, and stitch. Which of them are
  Workflow nodes is not established.
- **The graph can be suggested by the product.** The user describes the goal,
  and Arcads proposes the nodes.

### What this corrects

CT-0022 and CT-0023 described "Arcads-style" as *objects, not execution*.
That was wrong. **Arcads is an execution graph.** What separates it from
ComfyUI is the **level of abstraction**: its nodes are creative operations on
creative assets, never model internals. The corrected position:

- **One canvas, two kinds of node.**
  - **Entity nodes** are persistent project records: cast, locations,
    props, and shots. Changing Kael's reference visibly marks every
    dependent shot as stale. This is SPEC-0003 lineage.
  - **Step nodes** are creative operations: master image, camera and
    motion, image → video, voice, composite, and timeline. They are
    instances of workflow templates.
- **Steps run in the orchestration layer, not in the canvas.** The canvas
  shows them and starts them through commands. Their outputs land as takes
  with lineage. A step's definition (the template) is application or
  project data, never canvas-only state.
- **Providers stay below the step.** A "Generate Video" step resolves
  through the provider adapter to ComfyUI, fal.ai, RunPod, or anything
  else. The user sees Arcads-level nodes; ComfyUI stays hidden.
- **Agents can propose graphs.** This is a natural Agent Runtime task, and
  it goes through the same commands.

## Arcads (earlier note, superseded)

The web tools were unavailable during this session because of a transient
permission-check failure, so Arcads' canvas was not examined first-hand. What
is recorded so far comes from secondary public descriptions gathered earlier
(`references.md`): an infinite canvas "for connecting assets and generation
steps across a team", holding scripts, actors, edits, and ad workflows, with
variations, an API, and MCP. Those words describe **both** families. It is
not yet established whether an Arcads card is a thing or a step, or where
execution is triggered. To do: examine the product or its help pages
directly before treating Arcads as the model.

# To do

1. Verify Arcads first-hand: what a card is, what an edge means, whether a
   card runs anything, and how variations and batches appear.
2. Decide where card positions live, using the three options in finding 5.
3. Decide the stack. The evidence points to React 19 + Vite +
   `@xyflow/react` 12 as the lowest-risk choice (four of six), with Tauri 2
   as the desktop shell already preferred. Next.js is not needed: the Python
   runtime is the server. Before committing to CopilotKit, spike it on this
   stack against AG-UI and compare it with an MCP-only agent path
   (BeatDesign's model).
4. Then run the canvas spike from CT-0023 (step 2) on one real sequence.

# Decisions

- The reference implementations confirm the CT-0023 split: object canvas
  versus execution graph. Cine Toaster's canvas is the object kind, and it
  projects project records.
- Shots are never derived from canvas data (the SPITE anti-pattern).
- BeatDesign (Apache-2.0) is the primary reference for the canvas command
  model and lineage focus. Its code *may* be reused with attribution after a
  spike. Nothing has been reused yet.

# Validation

- `package.json` files read for stack and library versions.
- Node registries read: `noder/src/nodes/index.tsx`,
  `node-banana/src/components/WorkflowCanvas.tsx` and `components/nodes/`,
  `CineGen/src/components/create/nodes/index.ts`,
  `SPITE/components/canvas/nodes/` and `use-scene-shots.ts`,
  `ai-video-production-editor/src/workspaces/NodeWorkspace.tsx`, and
  BeatDesign's `react-flow-editor.tsx`, `canvas-projection.ts`,
  `core/commands/canvas-commands.ts`, and `mcp/server.ts` imports.
- Arcads was not verified; see above.

# Closed (2026-10-03, close-out pass)

Superseded: the stack was decided (ADR 0015), the canvas built read-only (CT-0034) and editable (CT-0046), positions computed.

What remains moved to the backlog (`development/roadmap.md` § Backlog): First-hand verification of Arcads, if still wanted.
