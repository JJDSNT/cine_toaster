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

# Then

1. ~~ADR: per-scene versions and `VERSIONS.md`; implement.~~ Done.
2. `toast migrate`: field by field (SINGULAR's 31 keys to native fields or
   catalogs), with a report of converted / approximated / unhoused.
3. Validate in the new directory: checks, storyboard, assembling real
   scenes against SINGULAR's own versions.
