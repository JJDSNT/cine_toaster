---
id: CT-0020
title: Evaluate Okay Wannabe UI and a visual transition graph
type: work
status: ready
owner: unassigned
created_at: 2026-09-27
updated_at: 2026-09-29
tags:
  - interface
  - editing
  - transitions
---

# What

Evaluate [Okay Wannabe](https://okaywannabe.com/) as a UI reference for Cine
Toaster's production rooms. Explore a node-based visual editor, inspired by
ComfyUI's interaction style, for expressing and previewing transitions between
clips. This is a future design evaluation, not an adopted UI or data contract.

# Why

The reference presents filmmaking as a progression through writing, casting,
creating, directing, editing, and composing. That may help make Cine Toaster's
existing rooms and their next actions easier to understand. A visual graph may
make relationships between clips and transitions easier to inspect and adjust
than a list of settings.

# Done

- Recorded the user's reference and transition-graph idea.
- Inspected the public Okay Wannabe landing page on 2026-09-27. Its visible
  Write, Cast, Create, Direct, Edit, and Compose sections support evaluating its
  production-stage navigation. The authenticated editor was not assessed.
- On 2026-09-29, read the client-side HTML and JavaScript of the signed-in web
  studio, pasted by the user. It is closed source, so it is a reference only and
  none of it is copied (ADR 0011). What it shows:
  - **Navigation.** The primary workflow tabs are Write, Create, and Film. Scenes
    and Videos form a secondary row. The Film tab has three columns: Production
    Style, Director's Monitor, and Scenes. Takes are listed under the monitor.
  - **A per-scene checklist in the side panel.** Engine choice comes first
    (Kling 3, with Seedance 2.5 marked "soon"). The steps are:
    1. Location;
    2. Cast, with roles detected from the script and an add/remove override
       stored as `{added, removed, images}`;
    3. Opening Frame, composed from the Location and Cast images with an image
       edit model;
    4. Storyboard & Blocking, under construction;
    5. Give Direction, under construction.

    Every slot holds a durable image id, and users set it by generating,
    uploading, picking, or dragging and dropping.
  - **Auto-fill on ACTION.** Blank slots are filled in dependency order:
    Location → Cast → Opening Frame. Filling stops if the fuel balance runs out.
  - **Cost before every render.** The server quotes the price, and a confirmation
    shows the cost and the balance afterwards.
  - **Chunked rendering.** A scene longer than 15 s renders as chunks that are
    then stitched ("chunk n of m", "stitching the film"). The "Cinematic"
    quality re-feeds cast references so faces hold across chunks. The visible
    client shows no end-frame → start-frame chaining between chunks. That is
    the cut problem of `CT-0022`, solved only by identity references.
  - **Screenplay editor.** It uses ProseMirror and saves lossless JSON, and it
    serialises to tagged text (`[ACTION:]`, `[SHOT:]`, `[TRANSITION:]`) as the
    render contract. Multi-line pastes are classified by an LLM, with a regex
    fallback.
- A second, complete copy of the page added:
  - **Full desktop tab set.** The Mac app's tabs are Write, Cast, Create,
    Direct, Edit, and Compose. Direct sets cinematography style, lighting, grade,
    and **camera movement as a film-level look**, then generates storyboards.
    Edit rates every take green, yellow, or red before assembly. The web studio
    reduces this to Write, Create, and Film, and camera intent appears only as
    free "directing style" text. Camera movement is therefore a style setting,
    not a per-shot record. This confirms the gap `CT-0022` addresses.
  - **Server-side render stages.** The stages are reading, parsing, planning the
    shot, submitting, rendering (Kling 3.0 Pro), and locking the final cut. The
    same server request generates missing key frames and plans the shots.
  - **Model limits surfaced as choices.** Aspect ratios limited by the model
    were removed from the interface: 2.39:1 and 1.85:1 "would silently fall
    back to 16:9". This is the case for the measured provider capability claims
    in `CT-0012`: an unsupported request must be refused visibly, never degraded
    silently.
  - **An Assistant Director agent.** It writes, casts, and "films on command".
    It is the product equivalent of our Agent Runtime, and it uses the same
    commands as the interface.
- On 2026-09-29, fetched the live page and its app scripts (`projects.js`,
  `projects-render.js`, `projects-scenes.js`). The live page matches the pasted
  copies, and the asset versions are unchanged. The scripts show:
  - **Scenes are never joined.** Each scene renders as its own clip of up to
    15 s. The app says "Stitching them into one video is coming soon." The
    client has no logic that carries frames or state from one scene to the
    next. Chunking within a scene happens on the server and cannot be seen
    from the client.
  - **The look is a style preset, not a prompt.** Twenty house "recipes" are
    sent as `custom_text` and merged server-side with the subject description.
    They are never sent as a finished prompt. This matches our `looks`
    cascade (SPEC-0004).
- Worth testing against our rooms: the ordered per-scene checklist
  (location → cast → opening frame → blocking → direction) as a view of
  readiness. The opening frame composed from project references matches
  SceneFlow's S₀ and our SPEC-0003 references. Quoting cost before any
  execution is also worth testing.

# To do

- Review the actual editor experience and identify specific interactions worth
  testing against Cine Toaster's Script, Storyboard, Cut, and Transitions rooms.
- Prototype a small graph using real clips and catalog transitions. Test whether
  it improves transition choice, ordering, preview, and revision over the
  existing rooms and a conventional timeline.
- Define how graph edits map to project-owned production records and shared
  application commands before choosing a graph library or changing the schema.
- Keep ComfyUI generation workflows separate from any Cine Toaster editorial
  graph; evaluate whether they need any connection through an adapter.

# Decisions

- Treat Okay Wannabe as a UX reference, not an architectural dependency.
- ~~Treat ComfyUI as an interaction analogy for nodes.~~ Superseded on
  2026-09-29: the graph follows Arcads.ai's production canvas, where cards
  are shots, takes, and cuts, instead of ComfyUI parameter wiring. See
  `CT-0022` and `references.md`.
- Defer implementation and schema choices until a focused prototype is reviewed.

# Validation

- Documentation-only change; checked the reference site and existing frontend,
  roadmap, transition specification, and interface work record.
