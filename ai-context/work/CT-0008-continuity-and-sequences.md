---
id: CT-0008
title: Scene geometry, continuity checks, sequences, and the live board
type: work
status: done
owner: unassigned
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - project-core
  - continuity
  - sequences
  - interface
---

# What

Add scene geometry as authored project state, static continuity checks over it,
sequences as the review unit, and a live interface that follows committed
decisions.

# Why

Take selection alone does not make a production coherent. The failures that cost
most in generated film are structural — a camera across the line, a character
whose height flips between shots — and they are checkable from the staging plan
before anything is generated.

Requirements came from importing a real feature production rather than from
design. That production had already invented the same geometry model by hand
(room dimensions, people positions, named cameras with targets and shot lists),
which is the strongest evidence available that the model is right. It had also
already been grouping scenes into assembled, separately reviewed sequences.

# Done

- `geometry.py`: `[geometry]` parsing, `Room`, `Subject`, `Camera`, `Axis`, and
  six checks with severities.
- `toast check`, `/api/findings`, and a continuity panel in the scene view.
- Plan-view blockout drawn on a canvas: room, subjects, cameras with fields of
  view, the line of action, and flagged cameras in red.
- `[[sequences]]` in `project.toml`, aggregated progress, a Sequences room, and
  the assembled render played in place.
- Event log plus SSE, so a decision committed from the CLI updates an open
  browser.
- ADRs 0006, 0007, and 0008; `docs/continuity-checks.md`.

# Decisions

- The axis is declared, never inferred (ADR 0007).
- Heights are optional; checks that need them skip rather than assume.
- The blockout is a 2D plan on a plain canvas, not three.js. Everything a
  director needs to check before generating — which side of the line, which
  camera covers which shot, whether the measurements are sane — is readable from
  above, and a plan works offline with no dependency. Three.js stays a candidate
  for when occlusion and sightlines through real set geometry matter.
- The event log is operational. It lives in the application cache and can be
  deleted without losing production truth.

# Validation

- `tests/test_geometry.py`: 13 tests covering parsing, axis, eyeline, and sanity
  checks, including the cases that must *not* produce a finding.
- Full suite: 70 tests passing.
- Checked against a real production of 9 scenes, 242 shots, and 230 registered
  takes. With the axis declared for scene 3-01, the check reports one crossing
  affecting 8 named shots.
