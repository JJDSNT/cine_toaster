---
id: SPEC-0004
title: The production schema — one shape for a feature film and a demo reel
type: specification
status: draft
implementation: planned
owner: project
created_at: 2026-09-22
updated_at: 2026-09-22
tags:
  - project-core
  - schema
  - format
---

# Goal

One authored schema that holds a dramatic feature and a motion-graphics reel
without either one bending, and that the two built-in demos can exercise
completely.

# Context

Two bodies of evidence, neither of them imagined.

**A real feature.** Singular's breakdowns hold 359 shots across nine scenes and
use **56 distinct shot keys**. Only eight appear in more than a quarter of the
shots: `n`, `tipo`, `plano`, `dur`, `camera`, `atuacao`, `som`, `seg`. Eighteen
keys are used three times or fewer. One of them, `lira`, is a character's name
used as a field — the scattering defect of ADR 0012 reaching the shot grammar.

A schema that enumerated those 56 keys would be a schema shaped by one film.
The tail is not noise, though: each key was added because a shot needed it. The
design problem is to find the small number of concepts the tail is made of.

**A general system.** OpenMontage (CT-0014) covers thirteen production kinds
with documented manifests and working code: explainers, animation, rigged 2D
character work, screen demos, talking heads, clip factories, documentary
montage, localization dubs. Eleven of the thirteen share one linear spine and
differ only in tools. Those are not hypothetical requirements; they are read
from a running system. What that system cannot express is a feature: no
sequences, no persistent cast, no takes, no dialogue at all.

The schema below is the union, organized so that the feature is the general
case and the thirteen kinds are degenerate ones.

# The organizing question

**Where do this shot's frames come from?** Every other field hangs off the
answer, and the existing `kind` field is already a partial, undeclared version
of it.

```yaml
source: generated | captured | archival | composed
engine: <id>          # ltx, wan22, flux, remotion, hyperframes, rig, solid, blender
```

- `generated` — a model produces the frames. Singular's 249 `ltx` and 49
  `imagem` shots.
- `captured` — a camera or a screen recorder produced them. Screen demos,
  talking heads, the author's own footage.
- `archival` — the frames already existed. Stock, archive, a `trecho`.
- `composed` — a renderer draws them from data. Title cards, charts, kinetic
  type, rigged character animation, and a solid black frame. Singular's
  `preto`, `branco` and `cartela`; OpenMontage's entire Remotion and
  HyperFrames surface.

`engine` names the mechanism. It is what routes execution, and it exists
because Singular already proved the need: a scene marked `motor: ltx` run by
the tool for the old engine produced nothing and exited successfully. An engine
a runner does not implement is a refusal, never a silent pass.

# Project-level entities

Declared once, referenced by id, never restated in a scene (ADR 0012).

```text
project/
  project.yaml
  cast/<id>/character.yaml      sheet, authority, references or rig
  locations/<id>/location.yaml  the same shape, deferred in SPEC-0003
  looks/<id>/look.yaml          the visual contract
  sound/                        library with a licence manifest
  scenes/<scene>/scene.yaml
  transitions/                  project-local catalog (already implemented)
```

## `cast` — and where rigged animation lands

SPEC-0003 gives a cast member a sheet, declared authority, and executable
reference images. One field generalizes it to cover rigged work:

```yaml
embodiment: reference | rig | performer
```

- `reference` — identity is carried by master images (SPEC-0003). Generative
  film.
- `rig` — identity is structural. The member owns a rig, a pose library and an
  action vocabulary instead of reference images, and continuity is guaranteed
  by construction rather than by prompting. This is where OpenMontage's
  `character_design`, `rig_plan` and `pose_library` land, and it is the only
  part of that system where character continuity actually works.
- `performer` — a person or an avatar. Talking heads and spokespeople.

The three differ in what proves identity, not in what a scene says about them.
A shot names a character; the embodiment decides what the engine is handed.

## `looks` — the style contract

Singular already declares `look:` per scene (177 of 359 shots carry one) and
OpenMontage's playbooks hold the same material. The anatomy worth keeping,
reimplemented rather than copied (ADR 0011):

```yaml
id: archive
palette:        # colour, and what is authoritative about it
typography:
motion:         # pacing rules: minimum and maximum holds, transition duration
audio:          # voice character, music mood, ducking
generation:     # prompt anchors, negative anchors, consistency anchors
grade:          # the parameterized image operations, values owned by the film
rules:          # the checkable ones only
```

`consistency_anchors` belongs here and not in a scene — that placement is the
whole lesson of ADR 0012, applied to style instead of to people.

A look resolves by cascade: project, then sequence, then scene, then shot. The
nearest declaration wins. Singular already authors at scene and shot level; the
cascade is what makes the upper levels worth having.

# What the shot tail is made of

The 56 keys collapse into six families. Each family is one concept in the
schema and the keys become its fields.

| Family | Keys it absorbs | Becomes |
|---|---|---|
| **Lineage** | `usa`, `usa_de`, `usa_arquivo`, `usa_ultimo_de`, `reusa`, `deriva`, `ref` | `from:` — what these frames come from: a master image, another shot's last frame, a file |
| **Variation** | `variacao`, `variacao_clipe` | `variant:` — a declared alternative of the same intent |
| **Screen text** | `texto_tela`, `textos`, `texto_entra`, `cor_texto`, `titulo_3d` | `text:` — a composed overlay, which is a `composed` source with its own engine |
| **Image operation** | `apaga_luz`, `clarao`, `escurece`, `so_a_luz`, `nivel`, `foco`, `zoom`, `recorte`, `espelhar`, and the scene's `ajuste_imagem` | `ops:` — an ordered list of parameterized operations |
| **Sound** | `som`, `silenciar`, `som_montagem`, `som_baixa_de`, and the scene's `ambiente`, `ambiente_ate` | `sound:` — bed, cues, and mix placement |
| **Notes** | `nota_montagem`, `nota_producao` | `notes:` — read by people, never by a check |

`ops` is the parameterized-mechanism case CT-0013 already described, and its
mechanisms exist: `media/grading.py`, `media/relight.py`, `media/focus.py`,
`media/face_patch.py`. Cine Toaster owns the operation; the film owns the
values.

No key is dropped. The families are the typed core, and everything else is
still read, still stored, and still shown:

| Tier | What it is | What the application does |
|---|---|---|
| **Typed core** | the six families and the fields above | checks, dedicated UI, meaning to a runner |
| **Declared extra** | a key the production names in `project.yaml` under `shot_fields:`, with a label and an optional type | carried as data, shown in the shot panel under the label the film chose |
| **Passthrough** | anything else | preserved verbatim, shown raw, never silently discarded |

An undeclared key is a finding, not a silence. `shot_field_undeclared` is
advisory: it tells the author that a key exists which nothing understands, and
offers the two ways out -- declare it, or let a family absorb it. A breakdown
that carries `lira` keeps working the day it is written and stops being
invisible the day someone looks.

This is the same rule the production already learned about commands: a step
that does nothing must say so rather than succeed. A field the schema does not
know is the data version of that failure.

Three tiers rather than one flat list of every key, because a general schema
that enumerated Singular's 56 would have the shape of one film. Tiering keeps
nothing lost and still keeps the core small enough for a second production to
recognise.

# Dialogue

The field with no counterpart anywhere in OpenMontage, and present in a third
of Singular's shots.

```yaml
lines:
  - who: KAEL           # resolves to a cast id
    text: "..."         # the film's language
    en: "..."           # what the model is given, when they differ
    delivery: "..."     # direction for the performance
    voice: <id>         # the voice this character is cast with
    mix: {file: ..., at: 1.8}
```

`who` resolving to cast is what makes a voice castable once instead of per
scene — the same argument as ADR 0012, applied to sound.

A localization is another `text` for the same line, not another scene. That is
one of the thirteen kinds covered by a field the feature needed anyway.

# Transitions

The catalog is implemented, has a real GL Transition v1 contract, and three
override layers. Nothing references it: no scene or shot can name a transition
today. The schema closes that:

```yaml
transition:
  id: diamond-wipe      # from the catalog
  duration_ms: 900
  reason: "..."         # why this cut needs punctuation
```

`reason` is required for the same purpose `authoritative_for` is required in
SPEC-0003: a choice that records no reason cannot be reviewed later. The
catalog's `use_when` and `avoid_when` are the agent-facing counterpart, already
written.

# Skills and knowledge

Unchanged, and already correct. CT-0009 drew the line: judgement stays in
skills, only checkable rules and measured provider claims become records with
`enforced_by`. OpenMontage's three knowledge layers map onto the layering that
`knowledge.py` already loads — built-in, shared, project. Nothing here needs a
new concept; the new checks this schema enables need practices to explain them.

# What the two demos must prove

The demos exist to populate the interface with varied, real elements of the
process, not to tick schema boxes. They divide by which moment of production
they serve.

The interface today has rooms for scenes, shots, sequences, review, continuity,
blockout, decisions, iterations, transitions, knowledge, library and activity.
That is the deciding half, and CT-0010 built it deliberately. There is no room
for a screenplay, a storyboard or a line of dialogue. The demos must carry
content for the half that does not exist yet, or it will be built against
nothing.

**Amiga Demo Reel** -- the reel. Cine Toaster is named after NewTek's Video
Toaster, whose demo reel was a slideshow carried by its transitions. This demo
is that: an opening narration, cards that cut on transitions, a music bed
underneath.

Every part of it runs with no API key: narration from offline Piper TTS, music
from Freesound under CC0 with its licence recorded, cards as `composed` shots,
transitions from the catalog including the production's own
`amiga-copper-bars`. A demo that needs a credential is a demo most people never
see run.

It proves: all of `composed`, screen text, the transition reference with its
reason, a look whose motion rules drive the pacing, and the sound bed. It fills
the transition and library rooms, and gives the script room its minimum case.

**The Last Signal** -- the production. A dramatic short with a cast, dialogue,
master images, takes and continuity.

It proves: cast with executable references and declared authority, dialogue
with a speaker that resolves to a cast id, lineage from master to shot,
geometry and axis (already there), `ops`, and takes under review.

It fills both moments completely, which is what makes it the fixture the
screenplay, storyboard and dialogue rooms get built against.

Between the two: all four sources, both cast embodiments, the six families,
dialogue, the transition reference, and both halves of the interface.

# Acceptance criteria

- Every one of Singular's 56 shot keys survives a load: typed, declared, or
  passed through. None is dropped, and an undeclared one produces a finding.
- Each of the thirteen OpenMontage production kinds is expressible as a
  restriction of this schema, with no field added for it alone.
- An engine that a runner does not implement is a refusal with a message, never
  a successful no-op.
- A look resolves by cascade and the resolution is inspectable.
- A shot's `from:` records lineage that a check can follow to something that
  exists.
- Both demos exercise the surface listed above and `toast check` passes.

# Deferred choices

- `locations`, as in SPEC-0003.
- The `ops` vocabulary itself. The families are named; which operations are
  Cine Toaster's and which are the film's is decided by implementing the demos,
  not by listing them here.
- Multi-project shared looks. A look that two productions use is a real idea
  and there is no second production asking for it yet.
- Whether `engine` is a closed enum. It is open until a second generative
  engine is wired, because a closed list written now would describe an imagined
  engine.
