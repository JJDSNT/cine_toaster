---
id: CT-0009
title: Knowledge layer and the eyeline direction check
type: work
status: done
owner: unassigned
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - knowledge
  - continuity
  - project-core
---

# What

Give Cine Toaster somewhere to accumulate what a production learns, and
mechanize the continuity rule that has cost the most so far.

# Why

Singular holds years of compressed judgement in four skill documents, dated and
evidenced. None of it was reachable by the software, so every rule still
depended on a person remembering it at the right moment. Storing prose would not
have fixed that; the missing link was between a rule and the check that enforces
it.

# Done

- `knowledge.py`: `Practice` and `ProviderProfile` records with `+++` TOML
  headers, loaded from built-in, shared, and project layers.
- `enforced_by` validated against `geometry.CHECK_CODES`, so a record cannot
  claim a check that does not exist.
- `coverage()` reports enforced versus manual, per domain, plus checks with no
  recorded reasoning.
- `toast knowledge` and `toast why <check_code>`; `/api/knowledge`; a Knowledge
  room; findings in the scene view now carry the reasoning behind them.
- Six built-in practices covering every current check, one of them deliberately
  unenforced to keep a known gap visible.
- `eyeline_mismatch` and `eyeline_subject_missing` checks, with `subject` and
  `looks_at` on shots and a reusable `screen_side()`.
- ADR 0009.

# Decisions

- Knowledge is data with dates, evidence, and an enforcement link — not a manual.
  See ADR 0009 for the comparison that led here.
- Judgement stays in skills. Only checkable rules and measured provider claims
  become records.
- The eyeline check needs no declared axis, only a declared `subject` and
  `looks_at`. It is still declaration, never inference.
- No pipeline manifests. The existing per-scene workflow is the right place for
  sequencing, once its steps become real human gates.

# Validation

- `tests/test_knowledge.py` (14): frontmatter parsing, layering and override,
  rejection of unknown checks and statuses, refuted records not enforced,
  provider claim parsing, coverage arithmetic, and an assertion that every
  built-in check has a practice explaining it.
- `tests/test_geometry.py` (19, was 13): eyeline direction including the cases
  that must stay silent — undeclared subjects and a centred interlocutor.
- Full suite: 90 tests passing.
- Against real data: with `subject`/`looks_at` declared on scene 3-01, the check
  reports Kael (27°) and Líra (80°) both looking to frame right. This is the same
  geometric fact the axis check found from a different direction, which is the
  strongest confirmation available that the finding is real.
- Twelve measured LTX 2.5 claims migrated from the Singular skills into a
  provider profile in the production, with their original dates and evidence.
