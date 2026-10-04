---
id: CT-0055
title: Generation parity with SINGULAR's tools -- a reference, not a target
type: work
status: done
owner: unassigned
created_at: 2026-10-04
updated_at: 2026-10-04
tags:
  - generation
  - singular
  - validation
---

# What

Backlog "Now" item 1: compare, for the shots of "Prologue to Title" (1-01 to
1-04), what SINGULAR's tools (`cena_ltx.py prompts`, read-only) and Cine
Toaster (`plan_shot`, on a scratch copy of the migration) would send to the
model.

The user (2026-10-04): the parity is **only a reference** -- the sequence will
be remade from scratch in Cine Toaster, with no commitment to what was
produced, except the screenplay. So the comparison stopped once it had shown
what Cine Toaster lacked in general; matching SINGULAR's wording is not a goal.

# Findings (98 shots compared, mean textual similarity 0.69)

- The scope format added a style sentence to every prompt: a delivery format
  now carries no prompt (it changes how the cut is framed, not what the model
  renders); the style test allows a format without one.
- SINGULAR's "what holds still" variants (`so_a_luz`, `entra_sai`) had no
  native home: a core shot field `holds` (`setting` default, `light`, `open`),
  said right after the camera in a single shot, as SINGULAR's tests of 17/09
  established; the migration maps both.
- A voice the scene restates now wins over the sheet's identity (nearest
  wins, as for looks and styles); the check still asks to keep only the state
  there.
- A declared first frame now wins over a picture of the shot's own: the last
  frame of another shot (`last_frame_of`, from the frame kept beside the clip
  or drawn into the cache from it), a file, another shot's picture --
  SINGULAR's `origem` order.
- Not pursued: block prompts (Cine Toaster plans 1-03's blocks as blocks);
  two shots on which SINGULAR's own tool crashes (pictures missing there).

# Validation

`tests/test_blocks`, `test_generation`, `test_styles`, `test_migrate`,
`test_emotions` pass.
