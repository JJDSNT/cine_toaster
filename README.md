# Cine Toaster

**An open, AI-powered filmmaking studio.**

**From creative vision to final cut.** Cine Toaster is an open production environment for filmmakers to develop, direct, produce, review, and finish cinematic works using generative AI, traditional filmmaking tools, and collaborative agents — while retaining creative control.

Inspired by the pioneering **Amiga Video Toaster**, Cine Toaster brings the instruments of filmmaking into a connected environment. It is not a single video generator, a frontend for one AI provider, or an attempt to replace every professional tool. It is the place where the **film, its creative intent, its production history, and its decisions stay together** as the tools around them change.

> **Project status:** Active, early-stage development. The Project Core, CLI, browser-based production/review capabilities, take decisions, continuity checks, and selected media workflows are executable today. The broader creative studio, visual exploration experience, agent collaboration, and end-to-end integrations are being developed or researched. [See the development status](#what-works-today).

## The filmmaking experience

A film is not just a collection of prompts or rendered clips. It has a screenplay, a cast, places, a visual language, emotional and narrative intentions, and hundreds of decisions that must remain coherent across shots, scenes, sequences, and revisions.

Cine Toaster is designed around that reality:

1. **Develop the film.** Work with screenplays, characters, locations, references, production assets, and the creative intentions behind them.
2. **Explore its visual language.** Compare approaches to composition, lighting, texture, palette, atmosphere, and style before committing the production to a direction.
3. **Plan the scenes.** Break down the screenplay, explore blocking and camera choices, and compare storyboard imagery with spatial previsualization where useful.
4. **Create alternatives.** Use appropriate models, workflows, tools, and infrastructure to produce image masters, shots, sound, and other assets.
5. **Direct through review.** Compare takes, identify failures or discoveries, select results, request revisions, and preserve the reasoning behind each choice.
6. **Maintain continuity.** Track what must remain consistent across characters, environments, story, visual identity, and successive stages of production.
7. **Assemble and finish.** Bring approved material through editing, visual effects, audio, grading, and delivery using integrated production tools.

This is a **target experience**, not a claim that every stage already has a finished interface or automated implementation.

## Creative direction belongs to the filmmaker

Generative models can produce striking images, but an impressive image is not necessarily the right image for a film.

Cine Toaster treats **creative intent, visual identity, and human decisions** as production concerns rather than incidental prompt text. A filmmaker may establish an authorial language for a project, vary the mood of individual scenes, compare different models and workflows, and deliberately depart from an established look when the story requires it.

A candidate image raises more than one question:

- Is it technically and visually usable?
- Does it serve the cinematic intention of this shot?
- Does it fit the film's established visual identity?
- If it does not fit, is it a failed attempt, a justified exception, or an interesting new direction worth exploring?

Those answers should not collapse into an automatic accept/reject score. The filmmaker may approve a result, regenerate it, retain it as a reference, allow an intentional exception, or investigate a new candidate visual identity without silently rewriting the film's existing decisions.

**Visual Lab** is the current research direction for testing visual choices across representative scenes and environments before promoting them into a production-wide visual baseline. Its precise UX and position in the application are **not yet decided**. The intent is to make visual discovery and approval practical, traceable, and reversible — not to impose one model, one aesthetic, or one workflow on every film.

See [Visual Lab research](ai-context/work/CT-0077-visual-lab-core-gap-and-ux-research.md) and [model-dependent mood research](ai-context/work/CT-0076-model-dependent-mood-and-visual-identity.md).

## One film, many production methods

Cine Toaster is designed for a **variable pipeline**. Different scenes and productions may need different techniques, models, and levels of spatial control.

- **Screenwriting and planning:** screenplay context, breakdown, characters, locations, scenes, shots, and editorial intent.
- **Storyboards and previs:** reference images, camera and blocking plans, and optional 3D environments to check spatial coherence before generation.
- **Image and video generation:** interchangeable local or remote models, workflows, and GPU providers, with multiple candidates and recorded provenance.
- **Visual effects and motion graphics:** reusable catalogs, compositing, titles, typography, and transitions.
- **Editing and finishing:** reviewable cuts, audio, grading, subtitles, and delivery through established media tools.
- **Production operations:** jobs, approvals, cost visibility, repeatability, and recovery.

**Blender** can help establish geometry, staging, camera positions, and visual references without requiring character performance to be animated in Blender. **Unreal Engine** and other DCC or real-time tools remain possible avenues of investigation, not mandatory dependencies. **ComfyUI** is an important generation integration direction, not the definition of the product. **FFmpeg**, **Ardour**, and future editorial/compositing integrations serve their own parts of the process.

The guiding principle is simple: **use the right instrument for the cinematic task, and keep the film independent of the instrument.**

## A connected, human-directed workspace

The intended interface follows the filmmaker's tasks and decisions, rather than exposing the production as a directory browser or forcing every activity into a node graph.

A user should be able to move naturally between a film, sequence, scene, shot, character, location, creative reference, generated candidate, approval, and resulting cut. Creative choices should be visual where possible: comparisons, contact sheets, contextual previews, blocking views, and before/after evaluations.

Spatial continuity and cinematic continuity are related but different. A hospital may be one connected physical environment while its room, corridor, and exterior support distinct scene moods and camera decisions. Cine Toaster is investigating how to represent these relationships without confusing the physical place with the dramatic situation or duplicating production state.

Agents are intended to collaborate on research, planning, production, review, and operations through the same application boundaries used by people. They may propose actions or execute authorized workflows, but **artistic authority and approval remain with the filmmaker**. The multiagent experience and its UX are evolving; they are not presented here as completed features.

## Why we are building it

Cine Toaster is being developed alongside **Singular**, a feature film made with generative models. A feature exposes problems that short prompt-to-video demonstrations can hide: a character must remain recognizable, a location must remain spatially coherent, a shot must cut with its neighbors, and a creative decision made weeks earlier must still be understandable.

The project has already learned from real production constraints: measured sets, camera positions, alternatives to a take, rejection reasons, assembled versions, and durable decisions. Those lessons inform reusable capabilities rather than film-specific assumptions.

**Singular is a production and validation case, not a bundled demo or a boundary on what Cine Toaster can create.** Its working files live outside the application repository. The same Cine Toaster mechanisms must serve other films and production styles.

## Architecture: the film owns its state

Cine Toaster is **local-first, open, and provider-independent**. The project files are the authoritative record of the production. A browser, CLI, agent, or external service must not become a competing source of truth.

```text
Filmmaker / Browser UI / CLI / External API / Agents
                         |
                  Application API
            commands | queries | events
                         |
                Application Runtime
         projects | jobs | processes | agents
                         |
                    Project Core
     scenes | shots | takes | assets | decisions | gates
                         |
                       Adapters
       generation | orchestration | media | protocols
                         |
      ComfyUI | FFmpeg | AI providers | other tools
```

The Core owns production concepts and shared domain commands; adapters connect replaceable tools. Human-authored production files and runtime-owned decisions have distinct ownership. Derived indexes and caches must be rebuildable. Background jobs and agent sessions are operational state, not an alternative authority for the film.

Projects are portable filesystem-based productions, typically with YAML for structured creative and production data, Fountain for screenplay text, and ordinary media files for assets and takes. There is no mandatory import step for a native production. Project-specific creative values remain with the project, not in global application defaults.

Read the [architecture](ai-context/architecture.md), [architectural decisions](docs/architecture/), and [production-specific tooling principles](docs/production-tooling.md).

## What works today

The repository already contains executable foundations. Among the implemented capabilities are:

- A Python-based headless runtime and the **`toast` CLI**.
- External filesystem productions, project loading, indexing, search, and browser-based production views.
- Two independent example productions: **The Last Signal** and **Amiga Demo Reel**.
- Shot/take discovery, side-by-side comparison, selection, revision-aware writes, decision history, and assembled-version review.
- Scene geometry, blocking views, screenplay coverage, camera movement/cut checks, and continuity findings.
- Production knowledge and provider observations recorded with evidence and enforcement status.
- Selected media workflows including FFmpeg-based assembly, transitions, and audio-related tooling.
- Additional operational and production commands developed through the *Singular* validation work.

These are **foundations, not a finished end-to-end filmmaking studio**. The existence of a research document, architectural adapter, command, or prototype does not imply that a complete interactive workflow is available.

### Under development or investigation

Work continues on the richer creative UX, visual-identity exploration, screenplay editing and interchange, model-aware generation experiences, reusable spatial environments, agent collaboration, production orchestration, broader VFX and finishing integrations, and remote compute workflows.

For the current implementation and priorities, consult [project status](ai-context/project-status.md) and the [development roadmap](ai-context/development/roadmap.md). These records are more detailed and are the appropriate place to verify individual feature maturity.

## Get started

**Requirements:** Python 3.12+ for the core installation. Additional tools are optional and depend on the workflows you want to run.

```bash
git clone https://github.com/JJDSNT/cine_toaster.git
cd cine_toaster
make setup
make demo
make serve
```

`make setup` installs the application and reports available capabilities. `make demo` creates example productions outside the source checkout, and `make serve` opens the browser-based control room.

Useful commands:

| Command | Purpose |
| --- | --- |
| `make setup` | Set up and inspect local capabilities |
| `make demo` | Create the example productions |
| `make serve` | Open the production control room |
| `make check` | Run production continuity/schema checks |
| `make build` | Build the Amiga reel demonstration |
| `make test` | Run the test suite |
| `make ui` | Build the production canvas (Node 20+ required) |
| `toast doctor` | Inspect installed and missing capabilities |
| `toast --help` | Explore the CLI |

For the canvas setup, see [docs/canvas.md](docs/canvas.md). Media, GPU, audio, and model dependencies are not all bundled; install only those needed for your chosen workflow.

### Example productions

**Amiga Demo Reel** demonstrates the project's Video Toaster heritage with cards, transitions, a coherent look, and offline rendering.

**The Last Signal** demonstrates a dramatic production with scene geometry, shots, takes, review, and continuity checks.

These are independently identified productions, not *Singular*. Other demo concepts may be planned without being shipped yet.

## Principles

1. **The filmmaker directs.** AI can assist, suggest, and execute, but human creative judgment remains authoritative.
2. **The film outlives its tools.** Projects and decisions must remain accessible when providers or interfaces change.
3. **Creative decisions are durable.** Keep alternatives, rationale, provenance, and the ability to reconsider.
4. **Visual coherence is intentional.** Preserve identity across the production while allowing deliberate artistic exceptions.
5. **No single mandatory pipeline.** Models, DCC tools, media engines, and orchestration frameworks are replaceable resources.
6. **Use established tools well.** Integrate strong filmmaking software instead of rebuilding every instrument.
7. **Describe maturity accurately.** Distinguish working software, prototypes, plans, and open research.

## Origins and inspiration

The original **NewTek Video Toaster** helped make sophisticated video production accessible on the Amiga. Cine Toaster takes inspiration from that spirit: bringing powerful tools together in a creative workspace rather than requiring filmmakers to assemble disconnected systems by hand.

The project also learns from open filmmaking and generative-production initiatives, including [OpenMontage](https://github.com/calesthio/OpenMontage), [AI Video Production Editor](https://github.com/LudwigKienle/ai-video-production-editor), [Kupkaprod](https://github.com/vladimirvalcourt/kupkaprod-cinema-pipeline), [Calliope](https://github.com/benjiyaya/Calliope), and [AIMovieStudio](https://github.com/Heroesjouney/AIMovieStudiov2).

---

**Cine Toaster is a work in progress — an open filmmaking environment being shaped by the demands of making films, not just generating clips.**
