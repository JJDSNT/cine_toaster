---
id: CT-0016
title: Remove Portuguese from the schema, the demos, and the documentation
type: work
status: done
owner: unassigned
created_at: 2026-09-22
updated_at: 2026-09-22
tags:
  - schema
  - format
  - boundaries
---

# What

Make the application's schema English, keep a production's own language in its
content, and route every legacy name through one module so an in-flight film
keeps loading.

# Why

`AGENTS.md` already required English for code, comments and documentation. The
schema had never been named as one of those things, so it drifted: `project.py`
read `cena`, `planos`, `titulo` and `situacao`; scenes lived in `cenas/`, takes
in `trabalho/`, rejected takes in `_descartados/`; and both demo productions
shipped that way, which made one film's language the first thing a new user
copies.

The drift was a cost of ADR 0010 rather than a mistake. Removing the export step
made the production's own YAML native, and the native productions were
Portuguese. The decision stands; this is the correction it needed.

The code had also already described the right boundary without holding it.
`_geometry_document` carries the docstring *"The file speaks the production's
language; the domain model speaks one of its own. This is the only place the two
meet."* True of geometry, false of everything else. This work makes the sentence
true.

# Done

- `vocabulary.py`: the single translation point. Canonical file, directory and
  field names; a legacy map of 41 field names, shot kinds and statuses; and
  `field`/`text`/`shot_kind`/`status` resolvers where a canonical name always
  wins.
- `project.py`, `takes.py` and `classify.py` read every authored name through
  it. No Portuguese identifier remains in the source.
- Canonical names are `scenes/`, `scene.yaml`, `work/`, `_takes/`, `_rejected/`.
- Both demo productions rewritten in English, keys and prose, with `git mv` so
  their history survives. The Last Signal keeps its geometry, its axis and its
  eight take files.
- `tests/test_vocabulary.py` (4): a canonical and a legacy production load to
  an identical model; a canonical name wins over its legacy twin; legacy shot
  kinds normalize; and no legacy name leaks into the loaded model.
- Test fixtures translated. `README.md`, `ai-context/project-model.md`,
  `docs/architecture/0010-one-native-format.md` and the demo README updated to
  the canonical names.
- `ADR 0013` accepted, amending `ADR 0010`.

# To do

- Delete `LEGACY_KEYS` and the legacy file, directory and value tables when the
  productions that need them have migrated. Singular is the only one, and its
  restructure is already planned as a fresh copy rather than an in-place
  migration.

# Decisions

- **Three layers, and the application owns one.** Schema in English; model-
  facing content in English because that is what models read; author-facing
  content in the film's language, never translated. The test for which layer
  something belongs to is whether another film, in another language, would have
  it identically.
- **Legacy names are a compatibility map, not a second schema.** Nothing is
  added to it, a canonical name always wins, and it has a named end. Recorded
  this way for the same reason CT-0012 recorded its duplication: so it does not
  become permanent by default.
- **A canonical name wins over a legacy one**, so a production can be migrated
  field by field and stay readable while half-translated.
- **Historical work records were left as written.** `CT-0010` and `CT-0011`
  refer to `decupagem.yaml` because that was the file's name when they were
  written. Rewriting them would make the record lie, and the record is the point.

# Validation

- Full suite: 145 tests passing, up from 141.
- Both demos load with English keys: The Last Signal (2 scenes, 3 shots and 8
  discovered takes in SC-030, geometry and axis parsed) and Amiga Demo Reel
  (2 scenes, independent identity).
- Against the real Singular production, before and after the change:
  9 scenes, 242 shots, 208 takes, 0 findings — identical, so a film authored
  entirely in the legacy vocabulary is unaffected.
- `grep` over the repository for Portuguese identifiers and paths returns only
  the legacy tables in `vocabulary.py`, the `cenas` entry in `classify.py`'s
  category map, and the two historical work records.
