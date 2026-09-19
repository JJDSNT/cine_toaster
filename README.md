# Cine Toaster

**An open production environment for AI filmmaking.**

Toaster Cinema aims to provide an integrated workspace for creating AI-assisted films, from screenplay and visual development to shot generation, review, editing, and delivery.

Inspired by the pioneering spirit of the **Amiga Video Toaster**, the project brings together modern generative tools, production automation, and traditional filmmaking workflows into a single open environment.

## Goals

- Manage films as projects composed of scripts, characters, locations, scenes, shots, and assets.
- Support AI-assisted screenplay analysis, directing, storyboarding, and shot planning.
- Provide visual tools for camera composition, blocking, and previs.
- Integrate **ComfyUI** workflows and local or remote GPU infrastructure.
- Generate and manage multiple takes for each shot.
- Support AI-assisted review, continuity checking, retakes, and re-generation.
- Provide human-in-the-loop approval checkpoints throughout the production pipeline.
- Support persistent and resumable production workflows.
- Provide GUI, CLI, API, and agent access to the same project state.
- Keep projects open, portable, and accessible outside the GUI.
- Integrate existing tools such as **FFmpeg**, **MLT/Kdenlive**, and other filmmaking software where appropriate.
- Remain independent of any specific AI model, provider, or generation backend.

## Architecture

Toaster Cinema is built around a shared **Project Core**. The GUI, CLI, API, and AI agents are different interfaces to the same canonical project state and production engine.

~~~
                ┌─────────┐
                │   GUI   │
                └────┬────┘
                     │
       ┌─────────────┼─────────────┐
       │             │             │
      CLI           API          Agents
       │             │             │
       └─────────────┼─────────────┘
                     │
              ┌──────▼──────┐
              │ Project Core │
              ├──────────────┤
              │ State        │
              │ Jobs         │
              │ Automation   │
              │ Human Gates  │
              └──────┬───────┘
                     │
       ┌─────────────┼──────────────┐
       │             │              │
    ComfyUI        FFmpeg       MLT/Kdenlive
       │
 Local / Remote GPU
~~~

Projects are intended to remain filesystem-based and human-readable whenever possible. Databases may be used for indexing or caching, but should not become the exclusive source of project state.

Generation and production services are exposed through replaceable adapters, allowing models, providers, GPU infrastructure, and external filmmaking tools to evolve independently from the core.

## Current Scope

The initial scope is the **production layer**, not the development of new generative models or a replacement for a mature non-linear editor.

The first milestones focus on:

- the filesystem-based Project Core;
- GUI, CLI, API, and agent access to the same project state;
- screenplay, character, location, scene, shot, and asset management;
- ComfyUI integration, including remote GPU execution;
- persistent job orchestration and resumable automation;
- storyboard and shot generation;
- multiple takes, review, selection, and retakes;
- AI-assisted continuity and production review;
- human-in-the-loop checkpoints.

Professional editing, compositing, audio, color, and delivery should initially be handled through integration with established tools such as **FFmpeg** and **MLT/Kdenlive** rather than reimplemented inside Toaster Cinema.

The scope may expand as real production requirements emerge.

## CLI

The command-line interface will be available through:

~~~
toast
~~~

Example:

~~~
toast init singular
toast status
toast shot generate 4.3
toast storyboard approve 4.3
toast take select 4.3 T02
~~~

## Status

Early development.

The initial focus is the project core, production workflow, ComfyUI integration, automation, and human-in-the-loop review.

## Inspiration

Toaster Cinema is inspired by the **Amiga Video Toaster** and by modern open-source AI filmmaking projects exploring generative production, visual directing, workflow orchestration, and automated film pipelines.
