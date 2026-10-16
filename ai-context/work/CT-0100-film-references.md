---
id: CT-0100
title: A film's references -- what it looks at, with where each came from
type: work
status: done
owner: claude-code
created_at: 2026-10-16
updated_at: 2026-10-16
tags:
  - project-model
  - references
  - provenance
  - cli
  - mcp
---

# What

A production keeps what it looks at but does not use as material -- draft
boards, model probes, paintings, stills -- in `references/<id>/`, each
folder holding its files and a `reference.yaml`: title, kind (`generated`,
`found`, `made`), made_by, made_on, source, prompt, `from` (the references
it came from), licence, credit, notes, and `files` by sha256.

# Why

Found by the first demo (CT-0099): the ChatGPT draft board and the Codex
probe had nowhere to go, and were filed by hand. The user (2026-10-16):
"it's fair to have a references folder in the project". A reference's
origin matters as much as a take's: what prompt, which model, which
earlier picture it was made from, and whether it may be shown.

# Done

- `references.py`: `load_references` (each record with findings: a file
  changed, missing or unlisted; an unknown kind; a `from` that is not a
  reference here; `found` with no licence as a warning) and `add_reference`
  (copies files in under `<made_on>-<slug>`, writes the record once through
  YAML's dumper; never over an existing folder; parents must exist).
- `toast references add|list [--json]`; MCP `list_references` (read-only).
- `docs/making-a-film.md` (the folder, a References section),
  `docs/mcp.md`, `ai-context/project-model.md`.
- demo-01's two references converted.

# Decisions

- References are authored, like cast and locations: written once by `add`,
  never rewritten by the runtime. Kept out of `load_production`, so no
  digest is computed on every load.
- Not SPEC-0002 (which locates a project's storage); field names follow
  `take add` (`source`, `licence`, `credit`).
- `toast references` (plural) is a different command from `toast
  reference`, which decides what a shot is made from. The closeness of the
  names is accepted for now.

# To do

In the roadmap (CT-0098's section): an agent adding a reference; reference
findings in `toast check` and the control room.

# Validation

- `tests/test_references.py` (5): records and lineage; changed, missing
  and unlisted files; licence warning and unknown parent; never over, parents
  must exist; the CLI.
- `tests/test_mcp.py`: `list_references` is a read.
- `toast references list ~/films/demo-01`: two references, no findings.
