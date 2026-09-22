# Cine Toaster

**An open production environment for AI filmmaking.**

Cine Toaster aims to provide an integrated workspace for creating AI-assisted films, from screenplay and visual development to shot generation, review, editing, and delivery.

Inspired by the pioneering spirit of the **Amiga Video Toaster**, the project brings together modern generative tools, production automation, visual decision-making, and traditional filmmaking workflows into a single open environment.

## Why this exists

Cine Toaster is being built to finish a specific film: **Singular**, a feature
adaptation of a novel, produced with generative models.

That is not a footnote. It is the method. Every capability here was added
because Singular hit a wall without it, and nothing was added in anticipation of
a wall that has not been hit yet.

It is also why the shape of this tool is unusual. Most open tooling for
generative video turns a brief into a short piece: research, script, assets,
render, done. A feature is the opposite problem. The screenplay already exists.
The cast already has faces that must not drift across three hundred shots. The
room a scene happens in must be the same room from every angle, an hour of
footage apart. Shots arrive as several plausible takes and someone has to choose
between them, remember why, and still be able to change their mind next week.

So the concepts that got built first are the ones a feature cannot do without:

- **takes and selection**, because generation is probabilistic and collapsing
  alternatives early loses both the comparison and the reason for the choice;
- **scene geometry and continuity checks**, because the failures that cost most
  are coherent shots that do not cut together, and they are checkable from the
  staging plan before anything is generated;
- **sequences**, because "is this part done?" is asked about a run of scenes,
  never about the whole film;
- **decisions as durable records**, because on a production this long, the
  reason a take was rejected outlives everyone's memory of it.

Several of these were not designed. Singular had already invented them by hand —
measured room dimensions and named camera positions in a scene file, rejection
reasons encoded in filenames, consecutive scenes assembled into one reviewable
video. Cine Toaster's job was to notice and take ownership.

**Singular is not in this repository.** A production is an external project that
Cine Toaster opens, reads, and writes decisions into; it never lives inside the
application. The two demo productions shipped in `examples/` are the only
project-shaped directories here. Nothing about the tool is specific to Singular,
and the day it only works for Singular is the day it has failed.

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

The Application Layer now includes an initial in-memory Project Manager. It can
register multiple arbitrary local projects from unrelated paths, preserves
manifest identity across moves, and rejects two open locations claiming the same
project ID. Persisted recent projects, UI switching, jobs, and remote source
synchronization remain future work.

## Project Model

A Cine Toaster project is a self-contained, filesystem-based production.

~~~
project/
├── project.yaml              # authored: identity, paths, sequences
├── story/
│   └── screenplay.fountain
├── cenas/
│   └── 030-scene-name/
│       ├── decupagem.yaml    # authored: direction, geography, shots
│       ├── state.json        # runtime-owned: selections, decisions, versions
│       └── trabalho/         # the takes, as files
│           ├── c01.mp4               in the assembled cut
│           ├── c01-longer-hold.mp4   another candidate
│           ├── _tomadas/             takes kept for comparison
│           └── _descartados/         rejected, with the reason in the name
├── assets/
├── typography/
├── subtitles/
├── workflows/
├── renders/
└── edit/
~~~

Human-readable project files describe the production state, while media and generated artifacts remain ordinary files.

There is **one format and no import step**. The production's own breakdown is
the scene file; Cine Toaster reads it where it lies. YAML rather than TOML
because a breakdown is deeply nested and carries prose, which TOML punishes
([ADR 0010](docs/architecture/0010-one-native-format.md)).

Cine Toaster never rewrites a file a human authored. Comments, section headers
and long direction notes survive every write, because committed decisions go to
a separate runtime-owned `state.json` beside the breakdown
([ADR 0006](docs/architecture/0006-authored-and-runtime-files.md)).

**Takes are not declared — they are files.** The runtime reads the work
directory: the clip in the cut, the alternatives, and the rejected ones with
their reason in the filename. A list of takes in a manifest would be a second
copy of something the filesystem already says, and second copies drift.

The filesystem is the canonical source of truth. GUI, CLI, API, and agents operate on this same state. Databases may be used for indexes and caches, but must be rebuildable from the project itself.

This keeps projects portable, versionable, scriptable, and independent of the GUI.

## Choosing Between Alternatives

Generation is probabilistic, so a shot arrives as several plausible takes.
Collapsing them immediately loses both the comparison and the reason for the
choice.

A shot registers its alternatives; each stays available, including the rejected
ones and why they were rejected. The comparison room puts two of them side by
side with synchronised playback, and selecting one records who chose it, when,
and why. Choosing does not discard anything.

## Continuity Before Generation

A scene may declare its measured geometry: the room, where each subject stands,
the fixed named camera positions, and the line of action. Shots reference a
camera by id rather than describing a new viewpoint.

From that, `toast check` reports the failures that survive shot-by-shot review
and only appear once the scene is cut — a camera across the line, a character
filmed from above in one shot and below in the next, a camera outside the
declared room. The interface draws the same data as a plan of the set.

The axis is never inferred and heights are never assumed. See
[`docs/continuity-checks.md`](docs/continuity-checks.md).

## Accumulated Knowledge

A production learns expensive things: which instructions a model obeys, which it
inverts, which mistake cost five discarded versions and on what date it was
measured. That knowledge normally lives in a document nobody reads at the moment
it matters.

Cine Toaster stores it as data instead.

A **practice** is a rule the production learned, with its status
(`measured`, `suspected`, `convention`, `refuted`), the date, the evidence, what
it cost — and `enforced_by`, the checks that now enforce it automatically. A
**provider profile** is what a specific generator does and does not obey, claim
by claim, each with its own measurement date and workaround.

The field that makes this more than a folder of notes is `enforced_by`. It is
validated against the real check registry, so the tool can report its own
coverage honestly:

```
PRACTICES  5/6 enforced by a check (83%)
  ...
  Still depends on a person remembering:
    one-master-image-per-position
```

A rule with no check behind it is not hidden — it is listed, by name, as
something a human still has to remember. Refuting a fact is a first-class act:
mark it `refuted` and it stops being enforced without being deleted, because
having once believed it is worth keeping.

Findings stop being bare verdicts. `toast why eyeline_mismatch` prints the rule,
what it cost the last time it was missed, and the evidence, and the interface
shows the same text under the finding.

Judgement stays out of this. When to use a long lens, what a director's style
means, "less is more" — none of that is checkable, and it belongs in the skills
a person or an agent reads, not in a ledger.

## Sequences

A sequence is an ordered run of scenes assembled and reviewed as one thing — the
level at which a production says "this part works now". Sequences aggregate
progress and open decisions from their scenes and can point at their assembled
render, which the interface plays beside the count of undecided shots.

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

Commands available today:

~~~
toast demo --list
toast demo ~/productions/the-last-signal
toast serve ~/productions/the-last-signal        # the control room
toast index ~/productions/the-last-signal
toast find  ~/productions/the-last-signal "continuity"

toast shots ~/productions/the-last-signal --scene SC-030
toast take select ~/productions/the-last-signal SC-030 SH-030-01 T02 \
      --rationale "Dread beats volume."
toast take clear  ~/productions/the-last-signal SC-030 SH-030-01
toast check  ~/productions/the-last-signal       # continuity, exits 1 on error
toast why    eyeline_mismatch                    # the rule behind a finding
toast knowledge ~/productions/the-last-signal    # practices, profiles, coverage
toast events ~/productions/the-last-signal
~~~

Every mutation runs through one application command, whichever interface calls
it. `take select` takes `--expect-revision` to fail instead of overwriting a
newer decision, and exits `3` on a domain error with a stable error code on
stderr. A decision made in the terminal appears immediately in an open browser.

`toast demo DESTINATION` creates The Last Signal by default. Demo templates are
independent productions with stable project IDs; list them with `toast demo
--list` and select another with `--template`.

Runtime productions belong outside the Cine Toaster source checkout. The demo
command refuses an in-repository destination by default. The
`--allow-inside-repository` override exists only for intentional fixture
development; conventional local directories such as `/projects/` and
`/local-projects/` are ignored as an additional safeguard.

The vocabulary still to come, from the same project core:

~~~
toast scene show 4
toast shot generate 4.3
toast storyboard approve 4.3
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

https://github.com/calesthio/OpenMontage

https://github.com/LudwigKienle/ai-video-production-editor

https://github.com/vladimirvalcourt/kupkaprod-cinema-pipeline

https://github.com/benjiyaya/Calliope

https://github.com/Heroesjouney/AIMovieStudiov2
