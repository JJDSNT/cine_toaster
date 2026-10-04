# Production validation and demo productions

Status: **product validation strategy**

Cine Toaster is validated in two different ways that must not be conflated:

1. by using it on **real productions**, where artistic needs come first; and
2. by maintaining **demo productions**, deliberately designed to exercise,
   explain or regress different classes of capability.

A real production does not become a demo merely because Cine Toaster learns
from it.

## Real production validation — Singular

**Singular is a real feature-film production, not a Cine Toaster demo.**

Its needs are allowed to expose production walls and drive reusable Cine
Toaster capabilities, but the film must never be forced to exercise a feature
merely so the software can demonstrate it.

The first major end-to-end validation milestone is **Prologue to Title**. This
supersedes the Boreal Station sequence as the initial Singular validation
boundary. Boreal remains a useful later production benchmark for spatial
continuity, 3D blocking and layout-guided generation.

The opening stresses conceptual imagery, transition into narrative, character
and environment continuity, hospital and corridor staging, ATLAS drones,
exterior/city cinematography, camera/blocking/previs, generative performance,
sound, music, edit, VFX/finishing and title design.

A successful run should travel coherently through:

```text
screenplay
 -> breakdown / directing decisions
 -> shot planning
 -> storyboard / 3D previs where useful
 -> reference/master imagery
 -> generation and takes
 -> review / selection
 -> continuity
 -> edit
 -> VFX / finishing / titles
 -> sound / music
 -> delivery
```

The same production should provide operational evidence for provenance,
Digital Workforce handoffs, provider execution, FinOps and Studio Analytics.
Success is not that every subsystem was invoked: the resulting sequence must
work as cinema.

## Demo production portfolio

Cine Toaster maintains four complementary demo productions. They are not four
versions of the same sample film; each has a distinct validation responsibility.

### Demo 1 — The Last Signal

**Role: technical/control demo and regression fixture.**

The existing `examples/demo-project` remains intentionally small and
controlled. It exercises the native project structure, screenplay, scenes and
shots, real take files, rejected alternatives, measured geography, line of
action, checks, comparison and selection.

Its value is repeatability. It should remain cheap enough to use while
developing the runtime and schemas rather than growing into a showcase
production.

### Demo 2 — Amiga Demo Reel / Cine Toaster Self-Demo

**Role: product showcase, commercial communication and continuous dogfooding.**

The existing Amiga Demo Reel evolves rather than being replaced by a new
advertisement. Its Amiga heritage remains part of its creative identity and
connects Cine Toaster to the historical Video Toaster idea of demonstrating a
production system through audiovisual work.

The reel adopts a two-movement communication structure:

```text
Act I: establish what Cine Toaster can do
                  |
                  v
Act II: show Cine Toaster doing it while producing the demo itself
```

As capabilities mature, they may be incorporated when they strengthen the
piece. The reel must not become an exhaustive feature checklist.

### Demo 3 — Animated Short

**Role: animation and stylised-character production.**

This demo should prove that Project Core is not implicitly restricted to
live-action/generative-film assumptions. It should exercise concepts such as
character and style bibles, model sheets or equivalent references, poses,
expressions, backgrounds/layout, recurring character consistency, voice,
lip-sync and generative or hybrid animated performance.

The purpose is not to mandate a particular animation technique or engine. It is
to ensure Cine Toaster can represent and manage animation as a genuine
production modality.

### Demo 4 — Music / Visual Piece

**Role: music-driven and non-dialogue-led audiovisual production.**

A short visual/music piece should stress timing and rhythm rather than making
screenplay dialogue the dominant organising principle. It can exercise beat
and musical structure, audiovisual synchronisation, rhythmic editing,
expressive camera work, transitions, VFX, motion graphics, sound/music
workflow and experimental generative imagery.

This demo is especially useful for discovering assumptions that every
production naturally follows `screenplay -> scene -> shot`. Music-driven work
may instead require relationships such as
`music -> time/beat -> segment -> shot/visual event`.

## Coverage model

```text
REAL PRODUCTION
  Singular
    -> feature-film reality
    -> artistic and narrative requirements
    -> long-form continuity
    -> production walls discovered in practice

DEMO PRODUCTIONS
  The Last Signal
    -> engineering / regression / controlled production state

  Amiga Demo Reel
    -> product / commercial / UI / dogfooding

  Animated Short
    -> animation / stylisation / recurring animated characters

  Music / Visual Piece
    -> rhythm / music / VFX / non-narrative audiovisual structure
```

Capabilities such as vertical delivery, localisation, subtitles,
accessibility, HDR, multiple masters and alternative aspect ratios should not
automatically create additional demo projects. Where practical, they should be
tested as variants or deliveries of these productions.

Documentary/factual production remains a currently uncovered modality. It
introduces additional concerns such as research, evidence, archival material,
rights and factual provenance and does not require a dedicated demo until that
scope becomes a real product need.

## Product principle

Real productions and demos are **evidence sources, not special cases in code**.

No Project Core concept should depend on Singular, The Last Signal, the Amiga
Demo Reel, the Animated Short, the Music / Visual Piece, or a specific
provider/model. When one of them exposes a missing capability, the solution
should be expressed as a reusable production concept when justified.

The distinction is intentional:

> Singular does not exist to demonstrate Cine Toaster. Cine Toaster exists to
> help produce Singular and other audiovisual work. Demo productions exist to
> exercise and demonstrate Cine Toaster.

## Evidence of progress

Across both real and demo productions, useful evidence includes end-to-end
coverage, undocumented workarounds, durable decisions and human gates, takes
and approval outcomes, continuity/rework, execution time, provider/resource
profile, reconciled cost, compute efficiency and capability
adoption/effectiveness in Studio Analytics.

Interpret that evidence according to the production's purpose. A technical
fixture optimises for repeatability; a showcase must communicate; an animation
demo must prove its modality; a music piece must work audiovisually; and a real
film must first work as a film.
