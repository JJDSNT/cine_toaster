---
id: CT-0096
title: Foundations before the demos -- a faster suite, a clean install checked, the cut as OpenTimelineIO
type: work
status: doing
owner: claude (agent)
created_at: 2026-10-16
updated_at: 2026-10-16
tags:
  - testing
  - install
  - otio
  - demos
---

# What

Three things chosen before the demos are produced (the user, 2026-10-16:
"before we leave for the demos, what would be worth doing now?"), each
independent of what the demos will reveal:

1. **The suite faster.** The whole suite takes 15 to 17 minutes, and every
   step of the demos closes with it. `--times` showed the time is not in
   the heavy tests but in ordinary ones waiting on each other in one
   process. Run modules in parallel, and look at the slowest.
2. **A clean install checked.** The repository is public and the demos
   will be its showcase; nothing checks that `git clone`, `make setup` and
   `make demo` still work on a fresh machine after everything that came in
   (the vision environment, models fetched, Blender, GL).
3. **The cut as OpenTimelineIO** (in the roadmap as "to do"): a version's
   cut -- shots, takes, in and out, joins, sound -- as `.otio`, to finish in
   Resolve, Premiere or FilmCraft; the picture's counterpart of the stems.

# Why

The demos will close many steps with the whole suite, will be watched by
whoever comes to the repository, and are made to be finished somewhere; each
of the three makes everything after it cheaper or possible.

# Done

## 1. The suite faster (2026-10-16)

- `tests/run.py` runs modules in parallel, one fresh process each (spawn,
  one task a process: as isolated as a module run alone), as many as the
  cores, the slowest first by their last times (a disposable cache); a
  module over a minute last time is split by class; each process gets its
  share of the cores for BLAS/OpenMP; the summary ends `OK` or `FAILED` as
  unittest's does. `-j 1` keeps the one-process run (and per-class times).
- Found by running in parallel: `test_assembly` submitted a second assembly
  and ended without waiting, the job still writing `state/` while the
  test's folder was removed -- it waits now.
- `--durations` found two slow things: a test helper rebuilding a 300,001
  point table of exact fractions at each of 25 calls (`test_retime_sound`:
  91 s -> 12 s, its claim unchanged); and the **product** reading a
  production's YAML with the pure-Python parser -- a decision read 27 files
  in 260 ms. `project._read_yaml` uses libyaml's parser when it is there
  (the same safe loading): 39 ms a decision, for the interface, the CLI and
  the agents alike.
- Measured: the whole suite 17 -> 8.2 minutes, the fast part 10 -> 2.4. The
  whole suite's floor is the heavy work (Blender and the models, about seven
  minutes of all the cores); lower would mean rendering less in those
  tests, which is the user's call.

## 2. A clean install checked (2026-10-16)

A fresh clone of this branch from GitHub, in a temporary folder, the
demos there too:

- `make setup` worked (3.2 min: the submodule, the canvas built, a coherent
  doctor) -- but **without the `vfx` extra** (OpenEXR, OpenColorIO), which
  since C6 and C8 carries signals, renders, Natron's frames and looks. The
  suite then **failed: 26 errors** on `import OpenEXR` / `PyOpenColorIO`, and
  a 27th masked behind them.
  - `make setup` installs `vfx` now: the clone's suite passes (1018, 51
    skipped: the voice and vision environments, USD, splats).
  - A minimal install still never fails for a missing extra:
    `@needs("OpenEXR")` in `tests/heavy.py` skips with the make target to
    run; without `vfx` the suite passes with 87 skipped.
- `make build` **failed**: Piper's own voice download stalled and waited out
  its ten minutes; retried by hand it took 8 s. It had also left a truncated
  model, which the old code accepted as a voice. `providers/piper.py`
  downloads the voice itself now -- a stall limit of 30 s a read, three
  tries, written whole or not at all, the model and its configuration both
  required (`tests/test_narration.py`, offline). `make build` then made the
  reel in 3.4 min.
- `make demo` worked.
- `scripts/fresh_clone_check.sh` repeats the whole path on a fresh clone,
  timing each step.

# To do

# Decisions

# Validation
