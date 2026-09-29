---
id: CT-0032
title: Jobs runtime — durable store, FFmpeg jobs, staging and adoption
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - runtime
  - jobs
  - media
---

# What

Plan step 6 (Phase 2): implement SPEC-0008. The work covers a durable job
store, an in-process runner, and `previs` and `build` as the first kinds.
It also includes cancellation, reconciliation, retry, adoption, events, CLI,
HTTP and a UI tray.

# Why

Nothing may generate or orchestrate before background work has a contract
(roadmap step 6). Renders already run long enough to block an interface.

# Done

- SPEC-0008, written and implemented (see its implementation notes).
- `toast build` and `toast previs` run as foreground jobs and adopt to
  `--output`. `toast jobs list|show|cancel|retry|adopt` manage them.
- HTTP endpoints `/api/jobs…`. The control room has a jobs tray, and a
  "Render video" button on the previs player.

# To do

- Stage `build`'s stills instead of writing them during the run (known
  deviation in SPEC-0008).
- Build cancellation inside a running FFmpeg step: route `build`'s
  subprocesses through `JobContext.run_process`.
- A detached worker for work that must survive a full application exit
  (not promised yet).

# Decisions

- Jobs are application operations, not film-domain commands. They have their
  own endpoints. Adoption is the only write into the project.
- The store is SQLite in `XDG_STATE_HOME`. It is state rather than cache,
  because deleting it loses history.

# Validation

- `tests/test_jobs.py` (19 tests):
  - lifecycle and events; failure recorded, not raised; unknown kind refused;
  - adoption as the only write, never overwriting unless told, staying
    inside the project;
  - cancellation of an external process, from another runtime, and while
    queued; retry;
  - reconcile with a dead runtime (its orphan is stopped), a process that is
    not the job's own (left alone), a live runtime, and a silent runtime;
  - isolation: project A's job finishes after B is opened and A is closed;
  - the previs job end to end.
- Real processes:
  - a GL build of the Amiga reel was cancelled from another shell at 69 %,
    and nothing reached the production;
  - the CLI was killed with SIGKILL while FFmpeg encoded a previs. The next
    runtime marked the job interrupted and stopped the orphan.
- Headless control room:
  - a previs job was started from the UI; the tray showed it ready to adopt,
    next to the interrupted job;
  - adoption over HTTP placed the file; a second adoption was refused;
  - a retry ran as attempt 2.
- Full suite: 321 tests OK.
