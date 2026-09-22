---
id: CT-0017
title: The production schema, and the reel that exercises it
type: work
status: doing
owner: unassigned
created_at: 2026-09-22
updated_at: 2026-09-22
tags:
  - project-core
  - schema
  - demos
---

# What

Implement the first slice of `SPEC-0004` — where a shot's frames come from, the
three field tiers, four of the six families, looks with cascade, and the
transition reference — and rebuild the Amiga Demo Reel as the production that
exercises it.

# Why

The interface has rooms for scenes, shots, sequences, review, continuity,
blockout, decisions, iterations, transitions, knowledge, library and activity.
That is the deciding half, built deliberately by CT-0010. There is no room for a
screenplay, a storyboard or a line of dialogue, and nothing in either demo to
build one against.

The transition catalog had the same shape of gap: a real GL Transition v1
contract, editorial metadata, three override layers, and no scene or shot able
to name an item in it. A library nobody can call.

Cine Toaster is named after NewTek's Video Toaster, whose demo reel was a
slideshow carried by its transitions. That is what the Amiga demo should have
been, and making it that is what forced the schema to be real.

# Done

- `vocabulary.py`: `source` and `engine`, with the legacy `tipo` values mapped
  to the source and engine they always meant; `CORE_SHOT_FIELDS` resolved
  against the legacy table so an old breakdown is not reported as unknown.
- `project.py`: shots carry `source`, `engine`, `from`, `variant`, `text`,
  `ops`, `sound`, `notes`, `lines`, `transition`, `look`, `extra_fields` and
  `unknown_fields`.
- Three tiers, and nothing dropped: typed core, extras a production declares
  under `shot_fields` in its manifest, and passthrough. An undeclared key is
  kept, shown, and reported as `shot_field_undeclared` (advice).
- `transition_unknown` (error): a shot may not name a transition no catalog
  has, because it would render as a cut with nobody told.
- `looks.py`: a look as project-level state, with `resolve()` returning both the
  value and the level that decided it.
- Two knowledge practices, because a check nobody can explain is a check nobody
  will trust: `no-silent-fields` and `transitions-are-chosen-not-named`.
- **Amiga Demo Reel rebuilt**: four scenes, four transitions each with its
  recorded reason, a look whose pacing rules the shots obey, narration cast and
  placed in the mix, and two declared shot fields. Its own
  `amiga-copper-bars` is now referenced by a shot rather than only loadable.
- The narration is real and checked in: `sound/vo-open.mp3`, 7.7 s, generated
  offline with Piper TTS. The reel needs no API key to be true.
- `tests/test_schema.py` (17) and the suite at 162, up from 145.

# To do

Wiring the remaining families. The `shot_field_undeclared` check reported them
against the real production, which is how this list was produced rather than
guessed — 31 undeclared keys across 104 findings in Singular:

1. **Sound** — `silenciar`, `som_montagem`, `som_baixa_de`, and the scene's
   `ambiente` / `ambiente_ate`.
2. **Image operations** — `apaga_luz`, `clarao`, `escurece`, `so_a_luz`,
   `nivel`, `foco`, `zoom`, `recorte`, `espelhar`, `sobrepor`, and the scene's
   `ajuste_imagem`. The mechanisms exist in `media/`; the vocabulary does not.
3. **Variation** — `variacao`, `variacao_clipe`.
4. **Screen text** — `cor_texto`, `texto_entra`, `fade`.
5. **Framing** — `quadro`, `still`, `cam`, `corte`, `seg`, `pos`, `entra_sai`.
6. Genuine one-offs — `lira`, `corpo`, `montagem_pov`, `de`, `guias`,
   `imagem_autor`, `bloco` — for Singular to declare under `shot_fields`.

Then: the look cascade applied at load; `cast` (CT-0015); and The Last Signal
rebuilt as the dramatic half, which is what the screenplay, storyboard and
dialogue rooms get built against.

# Decisions

- **`source` and `engine` are two fields, not one.** `generated`+`ltx` and
  `generated`+`flux` share lineage checks that `composed`+`remotion` does not,
  and `engine` is what refuses the wrong runner. Singular already paid for the
  absence of the second field: a scene marked `motor: ltx` run by the tool for
  the previous engine produced nothing and exited successfully.
- **Three tiers rather than a flat list of every key.** The application must
  handle every key, and a general schema that enumerated Singular's 56 would
  have the shape of one film. Tiering loses nothing and keeps the core small
  enough for a second production to recognise.
- **An undeclared field is advice, not an error.** The breakdown is correct and
  still loads; what is wrong is that nothing reads the field. Making it an error
  would block a production for writing down something true.
- **A transition reference records its reason.** The catalog's `use_when` and
  `avoid_when` exist to be argued with; a choice carrying only an id can only be
  re-litigated from memory.
- **The reel checks in its narration.** A demo that needs a credential is a demo
  most people never see run, and the end card claims the reel cost nothing.
- **The music bed is not checked in.** It is fetched under CC0 with its licence
  recorded. A music file with unclear provenance would make the end card lie.
- **A scene id is unique within a project, never across them.** Both demos now
  use `SC-030`, and the independence test asserts each resolves its own.

# Validation

- Full suite: 162 passing, up from 145. `tests/test_schema.py` covers source
  and engine, the three tiers including an undeclared key that is kept and
  reported, the seven lineage keys collapsing into one, legacy `falas` loading
  as `lines`, the transition reference and its refusal, the look cascade, and
  the reel obeying its own look's pacing.
- Against the real Singular production: 9 scenes, 242 shots, 208 takes —
  unchanged. Lineage is now captured on **190 shots** and dialogue on **94**,
  both of which were previously discarded on load.
- 31 undeclared keys surfaced across 104 findings. Nothing was dropped and
  nothing was silently accepted, which is the behaviour the tiers exist for.
- The reel loads clean: four scenes, zero findings.
