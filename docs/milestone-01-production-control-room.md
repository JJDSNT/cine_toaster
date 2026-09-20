# Milestone 01: Production Control Room

Status: implemented baseline

The first Cine Toaster milestone answers an operational question: **where is
the production, what needs attention, and what should happen next?**

It does not use the filesystem tree as the product's main navigation. Files
remain open and accessible, but scenes, workflow gates, iterations, decisions,
and review queues are the primary objects shown to the filmmaker.

## User outcome

From one production overview, a filmmaker can:

1. see progress across production phases;
2. identify the active scene and current gate;
3. scan all scenes by status, iteration, and progress;
4. open a scene workspace containing its workflow, shots, decisions, blockers,
   and iteration history;
5. enter a review room containing work that needs a human choice;
6. search and preview the underlying project files when needed.

This is deliberately read-only. The current milestone proves that the project
model and navigation are useful before adding commands that mutate production
state.

## Small project format

An operational project has a `project.toml` at its root:

```text
production/
├── project.toml
├── story/
│   └── screenplay.fountain
├── world/
│   ├── characters/
│   └── locations/
└── scenes/
    └── 030-echo-chamber/
        ├── scene.toml
        ├── references/
        ├── shots/
        └── iterations/
```

The project manifest stores identity, paths, the current focus, and high-level
production phases. Each scene owns a `scene.toml` with its workflow state,
shots, creative decisions, blockers, and iteration summaries. Heavy media stays
as ordinary files next to the scene that owns it.

One file per scene keeps a 120-scene production understandable, reduces merge
conflicts, and prevents a single central manifest from becoming a fragile
database substitute.

## Demo productions

`examples/demo-project` is an English-language source template named **The Last
Signal**. It contains six scenes at intentionally different stages: approved,
in review, blocked, in breakdown, and not started.

`examples/amiga-demo-reel` is a second independent source template named
**Amiga Demo Reel**. It contains five scenes with distinct creative content and
workflow state. Its stable project ID differs from The Last Signal and makes the
pair suitable for Project Manager and multi-project isolation tests.

List templates and create distinct working projects with:

```bash
toast demo --list
toast demo ~/cine-toaster-projects/the-last-signal
toast demo ~/cine-toaster-projects/amiga-demo-reel --template amiga-demo-reel
toast serve ~/cine-toaster-projects/the-last-signal
```

The checked-in directories are fixtures and distributable templates. Runtime
projects remain external to the Cine Toaster repository. Two fixtures do not by
themselves implement a multi-project runtime; they provide reproducible inputs
for that work.

## Rooms, not one generic interface

The original Video Toaster combined specialized production modules in one
system. Cine Toaster follows that useful part of the metaphor: Overview,
Scenes, Review, Library, and future Story, World, Edit, and Jobs rooms share one
project core, while each room can develop controls appropriate to its phase.

The Library is the fallback for files that do not yet participate in the
operational model. It is not the center of the application.

## Explicitly deferred

- editing project state from the interface;
- generation providers and job execution;
- model-specific prompts or ComfyUI workflow formats;
- a final schema for every production department;
- multi-user writes, locks, and synchronization;
- timeline editing and final delivery.

The first write operation should be a small, real creative decision—most
likely selecting a take during review—not a general-purpose metadata editor.

That follow-up is specified in
[`milestone-02-canonical-take-selection.md`](milestone-02-canonical-take-selection.md).
