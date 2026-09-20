# Cine Toaster

**An open production environment for AI filmmaking.**

Cine Toaster aims to provide an integrated workspace for creating AI-assisted films, from screenplay and visual development to shot generation, review, editing, and delivery.

Inspired by the pioneering spirit of the **Amiga Video Toaster**, the project brings together modern generative tools, production automation, visual decision-making, and traditional filmmaking workflows into a single open environment.

## Goals

- Manage films as projects composed of scripts, characters, locations, scenes, shots, and assets.
- Support AI-assisted screenplay analysis, directing, storyboarding, and shot planning.
- Provide visual tools for camera composition, blocking, and previs.
- Provide visual browsing, comparison, and preview tools for artistic decisions.
- Support typography, titles, credits, subtitles, and other text elements with real-time visual previews.
- Integrate **ComfyUI** workflows and local or remote GPU infrastructure.
- Generate and manage multiple takes for each shot.
- Support side-by-side comparison and selection of generated alternatives.
- Support AI-assisted review, continuity checking, retakes, and re-generation.
- Provide human-in-the-loop approval checkpoints throughout the production pipeline.
- Support persistent and resumable production workflows.
- Provide GUI, CLI, API, and agent access to the same project state.
- Keep projects open, portable, and accessible outside the GUI.
- Integrate existing tools such as **FFmpeg**, **MLT/Kdenlive**, and other filmmaking software where appropriate.
- Remain independent of any specific AI model, provider, or generation backend.

## Architecture

Cine Toaster is built around a shared **Project Core**. The GUI, CLI, API, and
production agents use the same application commands and canonical project
state. Long-lived jobs, project registration, resources, and agent sessions
belong to a headless Application Runtime rather than the visible UI.

~~~
 GUI │ CLI │ API │ Production Agents
              │
       Application API
 commands │ queries │ subscriptions
              │
      Application Runtime
 projects │ jobs │ processes │ agent runtime
              │
         Project Core
 scenes │ shots │ takes │ decisions │ human gates
              │
           Adapters
 agents │ orchestration │ generation │ media │ UI protocols
              │
 Claude/Codex │ ComfyUI │ FFmpeg │ future systems
~~~

Projects are intended to remain filesystem-based and human-readable whenever possible. Databases may be used for indexing or caching, but should not become the exclusive source of project state.

Generation and production services are exposed through distinct replaceable
adapter categories, allowing models, providers, GPU infrastructure, and
external filmmaking tools to evolve independently from the Core.

The current headless runtime and CLI are implemented in Python. React/Vite and
Tauri are strong incremental UI and desktop-shell candidates; they are not a
reason to duplicate or rewrite Project Core behavior. See
[`ai-context/architecture.md`](ai-context/architecture.md) and the accepted
decisions in [`docs/architecture/`](docs/architecture/).

## Project Model

A Cine Toaster project is a self-contained, filesystem-based production.

~~~
project/
├── project.toml
├── story/
│   └── screenplay.fountain
├── world/
│   ├── characters/
│   └── locations/
├── scenes/
│   └── 010-scene-name/
│       ├── scene.toml
│       ├── shots/
│       └── iterations/
├── assets/
├── typography/
├── subtitles/
├── workflows/
├── renders/
└── edit/
~~~

Human-readable project files describe the production state, while media and generated artifacts remain ordinary files.

The filesystem is the canonical source of truth. GUI, CLI, API, and agents operate on this same state. Databases may be used for indexes and caches, but must be rebuildable from the project itself.

This keeps projects portable, versionable, scriptable, and independent of the GUI.

## Visual Decision-Making

Cine Toaster is intended to make artistic choices visual whenever possible.

Instead of relying only on textual selectors and configuration panels, the interface should allow alternatives to be previewed and compared directly in the context of the film.

This includes:

- characters and casting references;
- locations and production design;
- costumes and visual assets;
- storyboards and shot alternatives;
- camera composition and lenses;
- generated takes;
- lighting and look variations;
- fonts and typography;
- titles and credits;
- subtitle styles and positioning;
- LUTs and other visual treatments.

Fonts, titles, and subtitles should be previewable directly over actual frames or shots, allowing typography, size, spacing, placement, styling, and animation to be evaluated in context.

Generated alternatives should support contact sheets, side-by-side comparison, A/B review, and direct selection wherever appropriate.

Transition banks should preview both live GLSL effects and WebM references,
with semantic guidance that filmmakers and AI agents can use when choosing
editorial punctuation.

AI may propose or generate alternatives, but the filmmaker remains responsible for the artistic choice.

## Current Scope

The initial scope is the **production layer**, not the development of new generative models or a replacement for a mature non-linear editor.

The first milestones focus on:

- the filesystem-based Project Core;
- GUI, CLI, API, and agent access to the same project state;
- screenplay, character, location, scene, shot, and asset management;
- visual browsing, preview, comparison, and selection tools;
- typography, titles, subtitles, and related visual elements;
- ComfyUI integration, including remote GPU execution;
- persistent job orchestration and resumable automation;
- storyboard and shot generation;
- multiple takes, review, selection, and retakes;
- AI-assisted continuity and production review;
- human-in-the-loop checkpoints.

Professional timeline editing, advanced compositing, audio mixing, color grading, and final delivery should initially rely on integration with established tools such as **FFmpeg** and **MLT/Kdenlive** rather than being reimplemented inside Cine Toaster.

Cine Toaster should nevertheless manage the production decisions and assets involved in these stages and provide previews and comparison tools where they improve the filmmaking workflow.

The scope may expand as real production requirements emerge.

## CLI

The Cine Toaster command-line interface is:

~~~
toast
~~~

Commands available in the current milestone:

~~~
toast demo --list
toast demo ~/cine-toaster-projects/the-last-signal
toast demo ~/cine-toaster-projects/amiga-demo-reel --template amiga-demo-reel
toast serve ~/cine-toaster-projects/the-last-signal
toast index ~/cine-toaster-projects/the-last-signal
toast find ~/cine-toaster-projects/the-last-signal "continuity"
~~~

`toast demo DESTINATION` creates The Last Signal by default. Demo templates are
independent productions with stable project IDs; list them with `toast demo
--list` and select another with `--template`.

The intended operational vocabulary will grow from the same project core:

~~~
toast status
toast scene show 4
toast shot generate 4.3

toast storyboard approve 4.3

toast take select 4.3 T02

toast render
~~~

The CLI, GUI, API, and agents are intended to expose the same underlying project operations.

## Status

Early development.

The initial focus is the Project Core, production workflow, visual decision tools, ComfyUI integration, automation, and human-in-the-loop review.

## Development Status

The current codebase implements the first executable milestone: a read-only
**Production Control Room**. It
opens an external project and makes its creative and operational state
navigable: production phases, scene progress, workflow gates, iterations,
decisions, blockers, shots, and work waiting for human review.

The file library remains available for search and preview, but it is a support
tool rather than the primary interface. Cine Toaster navigation follows the
film's production logic instead of mirroring its directory tree.

Development commands:

~~~bash
uv run toast demo ~/cine-toaster-projects/the-last-signal
uv run toast serve ~/cine-toaster-projects/the-last-signal
~~~

The demo command creates a separate English-language production from a
versioned template. The repository currently includes The Last Signal and
Amiga Demo Reel, providing independent projects for multi-project development.
The control room listens on `http://127.0.0.1:8787` by default. See
[`docs/milestone-01-production-control-room.md`](docs/milestone-01-production-control-room.md)
for the scope and project format.

The next milestone is the first canonical write: selecting a take through one
shared domain command, with atomic filesystem persistence, revision conflicts,
decision history, CLI/HTTP parity, and UI support. See
[`docs/milestone-02-canonical-take-selection.md`](docs/milestone-02-canonical-take-selection.md).

Current status, active work, next actions, risks, and validation are tracked in
[`ai-context/project-status.md`](ai-context/project-status.md). The
`ai-context/` directory is development memory for building Cine Toaster; it is
separate from the runtime context and skills used by production agents to make
films.

The **Transitions** room provides an application-level effect bank with live
GLSL previews, WebM references, provenance, and AI-facing editorial guidance.
See [`docs/transition-library.md`](docs/transition-library.md) for its open
manifest and extension path.

## Inspiration

Cine Toaster is inspired by the **Amiga Video Toaster** and by modern open-source AI filmmaking projects exploring generative production, visual directing, workflow orchestration, and automated film pipelines.

https://github.com/LudwigKienle/ai-video-production-editor

https://github.com/vladimirvalcourt/kupkaprod-cinema-pipeline

https://github.com/benjiyaya/Calliope

https://github.com/Heroesjouney/AIMovieStudiov2
