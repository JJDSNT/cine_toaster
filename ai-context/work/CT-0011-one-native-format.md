---
id: CT-0011
title: One native format — read the production's YAML directly
type: work
status: done
owner: unassigned
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - project-core
  - format
  - filesystem
---

# What

Remove the export step. Cine Toaster reads the production's own YAML breakdown
where it lies, discovers takes from the filesystem, and has one native format.

# Why

The exporter generated a `scene.toml` beside every breakdown. It was scaffolding
mistaken for architecture, and the proof was `scene_out_of_date`: a digest check
whose only job was to detect drift the copy itself created. A fix for a
self-inflicted wound is a reliable sign of a bad boundary.

"The filesystem is the source of truth" means state lives in files any tool can
read. It does not mean everyone must use the file we invented.

# Done

- `project.py` rewritten to read `project.yaml` and `decupagem.yaml` directly,
  translating the production's plan into the Core's geometry vocabulary in one
  place.
- `takes.py`: a shot's alternatives are discovered by reading the work
  directory. Rejected takes keep the reason from their filename.
- Cameras are assigned to shots from the geography's own shot list.
- Scene variants: the project names the variant in production; others stay on
  disk as history without competing for the scene id.
- `Selection` records the chosen file, so the assembly tool needs to read
  nothing but `state.json`.
- Deleted: `ct_export.py`, nine generated `scene.toml`, `project.toml`, the
  digest, `scene_out_of_date`, and its practice record.
- Both demo productions rebuilt in the native format, with real take files.
- PyYAML added as a dependency; conventions updated rather than quietly broken.
- ADR 0010; ADR 0006 amended.

# Decisions

- YAML, chosen for the shape of the data: a breakdown is deeply nested and
  carries prose, which TOML punishes.
- Field names stay in the production's vocabulary. Renaming would have broken
  roughly 1,500 lines of working production tooling mid-production to buy
  nothing the film needs. The Core's domain model is English and one function
  translates.
- Takes are files, never a declaration.
- Known risk: YAML implicit typing. `safe_load` everywhere, ids quoted in
  templates.

# Validation

- 112 tests passing under both documented commands.
- Against the real production, with no export step and no generated file:
  9 scenes, 2 sequences, 242 shots, 230 takes — the same figures the exporter
  produced, from the original files.
- Closed loop re-verified: selecting `POV` on shot P2 of scene 3-01 makes the
  assembly resolve `c02-pov.mp4`; a shot with no decision resolves the default.
