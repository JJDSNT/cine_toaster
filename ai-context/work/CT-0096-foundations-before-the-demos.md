---
id: CT-0096
title: Foundations before the demos -- a faster suite, a clean install checked, the cut as OpenTimelineIO
type: work
status: done
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

## 3. The cut as OpenTimelineIO (2026-10-16)

- `otio_export.py` (adapter; OpenTimelineIO, Apache-2.0, as the `otio`
  extra, `make install-otio`, a doctor capability): V1 the cut -- a take
  from its cut point, a drawn shot from its own picture, a solid screen a
  generator, each clip's shot, take and production path in its metadata;
  transitions centred on the cut over the frames the assembly overlapped
  (OTIO's `in_offset` from the entering shot's head, `out_offset` from the
  leaving shot's tail, trimmed so the timeline keeps the cut's length); V2
  the version, disabled; A1 the mix; A2... the stems.
- The assembly records the cut as it made it (`Plan.timeline`: each piece's
  file, its in point, its frames, the overlap into it); the job keeps the
  drawn shots beside the version (`vN.media/`), since its work folder is
  removed, and writes `vN.otio` with the files' final places.
- `toast assemble --otio`, and `otio` on the MCP server's `assemble_scene`:
  one command for every interface. Asked for without the extra, it is
  refused when submitted, with the command to run.
- `docs/otio.md`. What it leaves is in the roadmap: J/L-cuts split on the
  tracks, a transition's look beyond a dissolve, a sequence's cut.

# To do

# Decisions

# Validation

- The suite in parallel: whole 8.2 min, fast part 2.4 min, green
  (`tests/run.py`).
- A fresh clone from GitHub: `make setup` 3.2 min; `make demo`; `make test`
  1018 passed, 51 skipped; `make build` 3.4 min -- after the fixes above.
  Without `vfx`: 1018 passed, 87 skipped. `scripts/fresh_clone_check.sh`
  repeats it; its own run on the branch passed end to end (setup 137 s,
  test 198 s, build 279 s; OK, 51 skipped).
- The whole suite with the OpenTimelineIO export: 1022 tests, OK, 8.9 min.
- `tests/test_otio.py`: the adapter's arithmetic (handles trimmed, the cut's
  length kept, a generator for a solid); a real assembly with a transition
  and a titled shot, adopted and read back by OpenTimelineIO -- one clip a
  shot in order, one transition, the timeline exactly the version's frames,
  every file it points at present, the drawn shot in `v1.media/`.
- `tests/test_narration.py`: a stalled voice download tried again and kept
  whole; one that never answers fails after three tries leaving nothing.
