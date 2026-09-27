---
id: CT-0020
title: Evaluate Okay Wannabe UI and a visual transition graph
type: work
status: ready
owner: unassigned
created_at: 2026-09-27
updated_at: 2026-09-27
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
- Treat ComfyUI as an interaction analogy for nodes, not as the editor's required
  engine or file format.
- Defer implementation and schema choices until a focused prototype is reviewed.

# Validation

- Documentation-only change; checked the reference site and existing frontend,
  roadmap, transition specification, and interface work record.
