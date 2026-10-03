---
id: CT-0054
title: Migrating SINGULAR to ~/films/singular in Cine Toaster's native format
type: work
status: doing
owner: unassigned
created_at: 2026-10-03
updated_at: 2026-10-03
tags:
  - singular
  - migration
  - validation
  - layout
---

# What

The validation milestone (backlog "Next" item 1) becomes SINGULAR's
migration, at the user's direction (2026-10-03): a repeatable tool
(`toast migrate`) reads `~/confyui/singular` and writes **`~/films/singular`**
in Cine Toaster's native schema -- not aliases. The original is never
modified and its tools keep working; if nothing from SINGULAR is missed,
the new directory becomes the working folder. Its organisation must make
the versions easy to see during production.

# Survey of SINGULAR (read-only, 2026-10-03)

5.8 GB: `cenas/` 3.2 GB (9 scenes; a scene may have two breakdowns, the
Wan one and `ltx/`, the production's `variante: ltx`; `versoes/` with
`VERSOES.md` -- a table of version, date, duration, what changed, the
author's notes, approval -- and `decupagem-vN.yaml` per version;
`trabalho/` with clips `cNN.mp4`, word sidecars `cNN.palavras.json`,
voices, pictures `pNN*.png`, `_tomadas/` alternative takes, `_descartados/`,
`partes/` intermediates; `teste/`; review PDFs), `sons/` 1.3 GB (library
with `MANIFESTO.csv`), `arquivo/` (pilot, trailers, casting test),
`cenarios/` (5 locations), `elenco/` (sheets, LoRA, motion, objects,
voices), `estetica/` (LUTs, visual grammar, `mundos.yaml`), `livro/`,
`roteiro/` (V4 generated from the author's V3), `sequencias/`, `docs/`,
`knowledge/`. `project.yaml` declares 31 SINGULAR-only shot fields.

# Layout (decided)

The user (2026-10-03): the evaluation and the decision are mine -- the
structure must run the film's production and keep the history of its
evolution. Evaluation: SINGULAR has no git; its history is its `versoes/`
folders (cut + breakdown + notes table), `.orig` files and screenplay
versions. Cine Toaster kept versions away from scenes, without the
breakdown that made them, and truncated the decision history at 200.
Decided in ADR 0021; the layout below stands.

```
~/films/singular/
  project.yaml       README.md (generated: scenes, status, latest version, pending)
  story/book/  story/screenplay/        cast/<person>/   locations/<place>/
  look/   sounds/   docs/   archive/    deliveries/
  scenes/<id>-<slug>/
    scene.yaml       the active breakdown
    versions/        vN.mp4 + VERSIONS.md (regenerated from the records)
    takes/<shot>/    takes with word timings
    pictures/        master pictures, 3D boards
    review/          review PDFs, direction notes
    archive/         the other breakdown, discarded takes, tests
  sequences/<id>/versions/
```

- Versions inside each scene, with a human index regenerated on every
  version and verdict, in SINGULAR's own table format; its history moves
  over (3-01: v2-v12 with notes, v12 approved). Needs a Cine Toaster
  change (today: `renders/assemblies/<scene>/`), an ADR.
- The active breakdown becomes `scene.yaml`; the other goes to `archive/`.
- Media copied, not hard-linked (SINGULAR's tools overwrite files in place).
- Working files (`trabalho/` intermediates, logs) stay out: disposable.

# Done: ADR 0021 implemented (2026-10-03)

- Versions in `<scene>/versions/` (and `sequences/<id>/versions/`) with
  `vN.scene.yaml`, the breakdown that made the version; `versions.py`
  regenerates `VERSIONS.md` after `record_assembly`, `review_assembly`,
  `record_sequence_version`, `review_sequence_version`.
- `history.jsonl`: every decision, append-only, deduplicated by command
  id (`state._journal`, `read_history`).
- Tests: the snapshot and the index with a verdict (`test_assembly`), the
  journal beyond 200 decisions (`test_history`).

# Done: the migration, pass 1 (2026-10-03)

`migrate.py`, `toast migrate singular <source> <target> [--replace]
[--proposals] [--no-git]`. Trial runs into a scratch folder only;
`~/films/singular` not written yet.

- Layout as decided; 4,448 files, 4.9 GB copied (never hard-linked), in
  about 50 s; the source verified untouched (no file newer than the run).
- Scenes: the active breakdown becomes `scene.yaml` in the English schema
  (scene and shot keys renamed; `ambiente` to an ambience from the sound
  catalog, `som` lists and `som_montagem` to catalog sounds; `fala` to
  `lines`; the variant dropped and the scene's own title kept); paths
  rewritten (`trabalho/` to `work/`, `../trabalho/` to the archived main
  breakdown's work, `propostas/` to `story/proposals/`); work keeps takes,
  pictures, voices and sidecars (`_tomadas`/`_descartados` to
  `_takes`/`_rejected`), leaves a run's scratch (`partes/`, logs); the
  other breakdown archived whole.
- History: every surviving cut becomes a version record with its date,
  length, what changed, the author's note and a verdict read from the note
  (approved; `not_sent` for "não enviada"; rejected for a sent version's
  critique; pending without a note) -- 33 versions, 3-01 v2-v12 with v12
  approved; the breakdown snapshots kept as `vN.decupagem.yaml` (history is
  not translated); `history.jsonl` and `VERSIONS.md` per scene; the
  overview `README.md`; sequences' versions.
- Cast: 7 sheets gathered from every scene (variants from `fichas` with
  their face pictures, every wording of a variant's description and of a
  voice kept, the most used leading); plan names by pose tied to their
  person. Looks: 1 look definition per id from the scenes' descriptions.
  Sounds: SINGULAR's library copied and registered with licences (relative
  paths). The author's proposals brought in. Git started for the text.
- `MIGRATION.md`: converted, approximated, read through the legacy
  vocabulary, kept as written.
- **Equivalence** (`migrate.compare`): scenes, shots, durations, labels,
  sources, engines, lines and takes identical across the 9 scenes and 242
  shots; findings changed only by checks the cast switches on: 4
  `cast_reference_missing` (Narrador, Enfermeira, Diretor have no face --
  a real gap) and 2 `voice_identity_restated` (1-03 "very tired", 3-01
  "weak, hoarse": a state mixed into identity -- real, for the author).
- Found and fixed in Cine Toaster on the way: scene discovery read an
  archived breakdown as the scene (archives and versions folders now
  never compete, ADR 0021); `cast_label_drift` accused poses ("Kael
  (sentado)") -- SPEC-0003 amended: a pose or mark is not a name.
- Tests: `tests/test_migrate.py` (layout, schema, takes, archive, history
  with verdicts, index, journal, cast, looks, overview, report,
  equivalence, the source untouched, refusals); `tests/test_cast.py`.

# Done: pass 2a, sources (2026-10-03)

- SINGULAR's source fields as native relations, their meaning read from
  its own `cena_ltx.py` (`origem`, `ultimo_quadro`): `usa`/`usa_de` ->
  `picture_of`, `usa_arquivo` -> `file`, `usa_ultimo_de` ->
  `last_frame_of`, `reusa` -> `reuses` ("1-02/ltx c03" -> "1-02 c03":
  variants are gone); `deriva` -> the native `derive {from, with,
  request}` (16 shots: picture planning with cast faces now works for
  them); `ref: false` -> `cast_references: false` (it was never a source).
- Paths out of the scene rewritten: the sets (`../../../cenarios/` ->
  `../../locations/`, 1-02A's blockouts).
- `compare` now checks every shot's sources after the intended moves, and
  that every file a shot points at exists in the migrated film -- which
  found the blockout paths. Result: identical, the 6 real findings only.

# Pass 2 (next)

- `cenario` and the plans (`geografia`) into locations; `referencias_3d`.
- SINGULAR's montage operations (`silenciar`, `escurece`, `espelhar`,
  `recorte`, `apaga_luz`, `so_a_luz`, `sobrepor`, `fade`, `entra_sai`,
  `ajuste_imagem`) into effects and titles; screen text (`corpo`,
  `cor_texto`, `pos`, `texto_entra`) into titles.
- Generation prompts (`quadro`, `still`, `cam`, `variacao*`, `guias`,
  `in_frame`, `lira`) -- they feed SINGULAR's own generators.
- Then run into `~/films/singular` and validate there: assembling real
  scenes against SINGULAR's own cuts.

# Then

1. ~~ADR: per-scene versions and `VERSIONS.md`; implement.~~ Done.
2. `toast migrate`: field by field (SINGULAR's 31 keys to native fields or
   catalogs), with a report of converted / approximated / unhoused.
3. Validate in the new directory: checks, storyboard, assembling real
   scenes against SINGULAR's own versions.
