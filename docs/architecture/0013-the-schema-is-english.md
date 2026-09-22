# ADR 0013: The schema is English; a production's language stays in its content

Status: accepted

Amends [`ADR 0010`](0010-one-native-format.md).

## Context

ADR 0010 removed the export step and made the production's own YAML the native
format. The decision was right and the drift it caused was invisible: the first
productions were authored in Portuguese, so the application's schema became
Portuguese. `project.py` read `cena`, `planos`, `titulo` and `situacao`; scenes
lived in `cenas/`, takes in `trabalho/`, rejected takes in `_descartados/`. Both
demo productions shipped that way, which made a film's language part of what a
new user copies first.

`AGENTS.md` already required English for code, comments and documentation. The
schema had simply never been named as one of those things.

The code had also already described the right boundary without holding it.
`_geometry_document` carries the docstring *"The file speaks the production's
language; the domain model speaks one of its own. This is the only place the two
meet."* That sentence was true of geometry and false of everything else.

A general application that carries one film's language carries it for every
film that follows. The test for what belongs where is whether another film, in
another language, would have it identically: `status: superseded` would;
a line of direction about a character's shoulders would not.

## Decision

Three layers, and the schema is the only one the application owns:

- **Schema** — directory names, file names, field names, enum values — is
  English. It is the application's contract and the application is general.
- **Model-facing content** — prompts and anything a generation provider reads —
  is English, because that is what the models are trained on.
- **Author-facing content** — direction, dialogue, shot description, subtitles —
  is the film's language, and the application never translates it.

The canonical names are `scenes/`, `scene.yaml`, `work/`, `_takes/`,
`_rejected/`, and English field names throughout.

Legacy names are accepted through `vocabulary.py` and nowhere else, making true
the boundary the code already claimed. A canonical name always wins over a
legacy one, so a production can be migrated field by field and stay readable
while half-translated.

The legacy table is a compatibility map, not a second schema. Nothing is added
to it. It is deleted when the productions that need it have migrated, and until
then it has exactly one reason to exist: a film in production must not stop
loading because the tool grew up.

## Consequences

A new production copied from a demo starts in the application's vocabulary
rather than inheriting Portuguese from a film it has nothing to do with.

Every read of an authored file passes through one module, so adding a field
means adding it in one place, and so does removing the legacy map later.

Existing productions keep working unchanged, which is what makes the deletion
schedulable instead of urgent.
