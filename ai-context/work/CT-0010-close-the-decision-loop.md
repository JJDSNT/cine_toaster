---
id: CT-0010
title: Close the decision loop and model assembly versions
type: work
status: done
owner: unassigned
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - project-core
  - assemblies
  - human-in-the-loop
---

# What

Make a committed decision change what gets rendered, model the history of
assembled versions, and detect a scene file that has gone stale against the
source it was generated from.

# Why

An assessment of the real production found the loop open. The Singular assembly
tool selects a clip by filename:

```python
clipe = f"{d['_dir']}/c{C.nome(n)}.mp4"
```

Selecting a take is therefore *which file is named `c04.mp4`*. A selection
committed in Cine Toaster changes nothing that gets rendered, so the interface
observes a process happening outside it, and the production pays double
bookkeeping — record the decision, then move the file. That decays within weeks.

The same assessment found two more frictions worth fixing here:

- **Three sources of truth.** `decupagem.yaml` is authored, `scene.toml` is
  generated from it, `state.json` is written by commands. Nothing detects that
  the generated file is stale, and a stale scene shows wrong shots with no
  warning.
- **The export is a view, not a representation.** Of 31 per-shot fields in the
  authored source, `scene.toml` carries 5. This is acceptable — Cine Toaster is
  the decision layer, not the generation source — but it must be stated so
  nobody treats the export as lossless.

The production's own version log (`versoes/VERSOES.md`) is the human-in-the-loop
record this product should own: twelve assembled versions, each with what
changed and the author's verdict, ending in one approved. It is the right model
and it is currently a hand-maintained Markdown table.

# Done

- `Assembly` in runtime state (schema version 2): media, summary, duration,
  verdict, reviewer, and the take snapshot it was built from.
- `record_assembly`, `review_assembly`, `restore_assembly`, reached from CLI,
  HTTP, and the browser like every other command.
- Rollback re-applies a version's selections atomically and is recorded as a new
  decision, never as an undo. A version with no snapshot refuses to restore
  rather than silently clearing selections.
- Approving a version supersedes the previously approved one instead of
  deleting it.
- `toast version list | record | review | restore | diff`, and a version panel
  in the scene view with per-shot differences between any two cuts.
- `scene_out_of_date`: a generated scene file records the digest of the source
  it came from, and the mismatch is reported like any other finding.
- `ferramentas/ct_state.py` in the production: the assembly tool now resolves a
  shot's clip through the committed selection, falling back to the previous
  behaviour when there is none.

# Decisions

- Assemblies are canonical runtime state and live in `state.json`, not a second
  file. Schema version moves to 2.
- A verdict is recorded, never inferred from which file is newest.

# Validation

- `tests/test_assemblies.py` (14): snapshot on record, duplicate ids, verdicts
  and supersession, restore semantics, refusal to restore a snapshotless or
  stale version, and shot-by-shot differences.
- `tests/test_project.py` (+5): staleness against a matching digest, an edited
  source, a missing source, a source outside the project, and a scene that
  declares none.
- Full suite: 110 tests passing.
- Closed loop verified against the real production: selecting the `POV` take on
  shot P2 of scene 3-01 makes the assembly resolve `c02-pov.mp4` in place of
  `c02.mp4`, and a shot with no decision still resolves the default. One bug
  found and fixed in the process: shot ids were `P2` on one side and `P02` on
  the other, so a leading zero silently discarded the author's choice.

# Open question raised during delivery

The exporter that produces `scene.toml` from the production's own scene format
is scaffolding, not architecture. It creates the very staleness this work then
had to detect. The right shape is a scene *reader* — the Core parsing the
production's existing files in memory, with no copy on disk — which ADR 0005
already anticipates for project sources. Recorded here rather than silently
carried forward.
