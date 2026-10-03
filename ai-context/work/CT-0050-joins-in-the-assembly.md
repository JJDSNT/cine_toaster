---
id: CT-0050
title: Transitions and J/L-cuts rendered in the assembly
type: work
status: review
owner: unassigned
created_at: 2026-10-03
updated_at: 2026-10-03
tags:
  - assembly
  - cut
  - transitions
  - sound
---

# What

A scene's assembled version renders its joins: catalog transitions (shader
or FFmpeg stand-in) and J/L split edits with the takes' handles. Until now
the assembly cut everything straight and noted "not rendered in this
version" (SPEC-0007, CT-0039).

# Why

With sound on the cut (CT-0048) the joins were the most visible gap left in
a version: 127 transitions in the catalog and J/L decisions on the canvas
that no version showed. `toast build` already rendered transitions for the
demo reel; the assembly did not use them.

# Done

- `cut.split` (seconds, J/L only, ≤ 5): validated in `set_cut`, kept by
  decisions, in the cut record, the canvas edge (`split`), the canvas
  editor (a seconds field for J/L), the Cut room card, `toast cut set
  --split`, MCP `set_cut`/`set_cuts`.
- `assembly.plan_scene` resolves each join (`_resolve_join`): the
  transition (shader when GL runs, else `[render].ffmpeg`, else a note and
  a straight cut; shortened to half the shorter shot, said) and the split
  (0.8 s by default). `Segment.transition`, `Segment.split`,
  `Segment.overlap`; `Plan.duration` subtracts transitions.
- `assembly.render` is now picture + sound: normalised picture pieces
  joined by `_join_pictures` (bodies and transition clips as in `build`,
  re-encoded once when transitions exist); one levelled sound clip per shot
  with its J/L handles, faded per join, laid on the timeline; muxed; then
  the sound catalog's cues. The split is clamped to the handle the take has
  (and 90 % of either shot), said when shortened.
- `build._frames` and `_shader_join` take size and frame rate.
- `sounds.place` accounts for transition overlaps.

# Decisions

- The other side's sound **fades across the split** (J: the outgoing fades
  out over the lead; L: the incoming fades in over the run-on); the
  borrowed sound gets a short 0.15 s edge so it does not click. A
  crossfade of both over the window would fade the leading line itself.
- A J/L-cut with a transition crossfades over the transition and ignores
  the split, with a note: two ways of overlapping the same join.
- A transition that cannot run is a straight cut **and a note**, not a
  refusal as in `build`: a version is a review copy, and it says what it
  could not do.

# Validation

- `tests/test_joins.py`: a 0.5 s dissolve through the FFmpeg stand-in and
  through the shader (3.5 s from two 2 s shots; the middle frame mixes red
  and blue); a J-cut heard over the outgoing picture from the incoming
  take's handle; an L-cut running on, its split shortened to the handle and
  said; a breakdown transition resolved and shortened; a decided split.
- `tests/test_assembly.py` updated (SC-030 P3's J-cut gets the default
  split); assembly, assemblies and sound tests pass; canvas build and its
  tests pass.

- On a demo copy (SC-030, 12 fps takes, a dissolve into P2, P3's J-cut):
  two bugs found and fixed. A take ending mid-frame gives one frame less
  than its length says, so the timeline now counts each picture piece's
  real frames (`_frames_in`) and clamps transitions to them. The sound
  catalog's mix ended 0.22 s early: `amix` with `duration=first` stops
  while a delayed input still plays, so it mixes `longest`, then pads and
  trims to the cut. Picture and sound now both run 1.50 s; P3's J-cut is
  shortened to its 0.35 s handle, and the version says so.

# To do

- Cuts between scenes (the sequence assembly) and their transitions.
- WebM transitions (overlays, luma mattes) as compositing contracts.
- A per-cut transition parameter override.
