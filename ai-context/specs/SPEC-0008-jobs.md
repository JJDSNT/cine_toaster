---
id: SPEC-0008
title: Jobs — background work that outlives the interface that started it
type: specification
status: implemented
implementation: complete
owner: project
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - runtime
  - jobs
  - media
---

# Goal

Long work, such as a render, a previs video or later a generation, runs as a
**job**. A job:

- belongs to a project;
- is recorded durably outside the project;
- reports progress and can be cancelled;
- survives navigation and project switches;
- is reconciled after the runtime restarts;
- produces a **staged** result that enters the production only when adopted.

This implements the job lifecycle contract in `ai-context/architecture.md`
(Phase 2, plan step 6).

# Store

- `$XDG_STATE_HOME/cine-toaster/jobs.sqlite` (default
  `~/.local/state/cine-toaster/`). It is application operational state:
  deleting it loses job history, never the film.
- Staged results live in `$XDG_STATE_HOME/cine-toaster/jobs/<job_id>/`.
- Every runtime (CLI process, control room) opens the same store. A job is
  executed by the runtime that created it. Another runtime can read it and
  request cancellation.

# Record

`id`, `kind`, `project_id`, `project_root`, `params`, `state`, `progress`
(0–1), `message`, `attempt`, `retry_of`, `runtime_id`, `runtime_pid`,
`process_pid` (the external process, if any), `cancel_requested`,
`created_at`, `started_at`, `finished_at`, `error`, `result` (staged files
with their destinations), `adopted_at`.

# Lifecycle

```
queued -> running -> succeeded | failed | cancelled
                  \-> interrupted        (its runtime is gone)
```

- **Cancel** is a request (`cancel_requested`). The running job observes it
  within half a second, stops its external process, and ends `cancelled`.
  A queued job is cancelled at once.
- **Reconcile** runs when a runtime starts:
  - any `queued` or `running` job whose runtime process is no longer alive
    becomes `interrupted`;
  - if that job's external process is still alive and is provably the job's
    own, because its command line names the job's staging directory, it is
    terminated and the message says so.
- **Retry** creates a new job with the same kind and parameters,
  `attempt + 1`, and `retry_of` set. Nothing is resumed in place.
- **Adopt** copies a `succeeded` job's staged files to their declared
  destinations inside the project and sets `adopted_at`. It refuses to
  overwrite unless told to, and it is the only step that writes into the
  project.
- **Events** go to the project's event log: `job.queued`, `job.started`,
  `job.progress` (at most one per second), `job.succeeded`, `job.failed`,
  `job.cancelled`, `job.interrupted`, `job.adopted`.

# Isolation

Jobs are keyed by project. Opening, switching or closing a project in the
Project Manager does not touch another project's jobs, or its own.

# Kinds

| Kind | Parameters | Staged result | Destination |
| --- | --- | --- | --- |
| `previs` | `scene`, `shot` | `previs.mp4` | `renders/previs/<scene>-<shot>.mp4` |
| `build` | `engine` | `<production>.mp4` | `renders/<production>.mp4` |
| `assemble` | `scene`, `version`, `summary` | `assembly.mp4` | `renders/assemblies/<scene>/<version>.mp4`, then registered as a scene version (`record_assembly`) |

A kind validates its parameters before the job is queued. FFmpeg progress is
read from `-progress` output (`out_time_us` against the expected duration).

# Interfaces

- CLI: `toast jobs list|show|cancel|retry|adopt`. `toast previs` and
  `toast build` run as jobs in the foreground and adopt to `--output`.
- HTTP: `GET /api/jobs`, `GET /api/jobs/<id>`, `POST /api/jobs` to start,
  and `POST /api/jobs/<id>/cancel|retry|adopt`.
- UI: a jobs tray with progress, cancel and adopt.

# Implementation notes

- `src/cine_toaster/jobs.py`:
  - `JobStore` is SQLite in WAL mode;
  - `JobManager` runs jobs in a thread pool;
  - `JobContext` gives a job `progress`, `cancelled` and `run_process`;
  - `KINDS` registers `previs` and `build`.
- **Liveness:** a runtime writes a heartbeat every 2 s for its running jobs.
  Reconcile treats a job as lost when its runtime process is dead, or when
  its heartbeat is older than 30 s.
- **Cancellation:** a running FFmpeg process is terminated.
  - `previs` stops at once.
  - `build` stops between steps: its FFmpeg calls are short, but a step that
    has started finishes first.
- **Known deviation:** `build` still writes the storyboard stills
  (`stills/`) directly into the project while it runs. They are derived
  feedback that the storyboard reads, but they bypass adoption. Moving them
  to staging needs the storyboard to read staged stills.
- The control room owns one `JobManager`, and reconciles when it starts. Job
  events refresh only the jobs tray; adoption refreshes the page, because
  adoption changes the production.
- The UI never overwrites silently: when adoption finds an existing file, it
  asks.

# Not promised

- execution across a full application exit or a machine restart (no detached
  worker);
- cross-runtime queue stealing;
- resuming a job in place.

# Acceptance

- Every state transition is tested, including cancelling a running FFmpeg
  job and reconciling a job whose runtime died.
- A job for project A finishes while project B is opened and A is closed in
  the Project Manager.
- Adoption is the only write into the project, and it refuses to overwrite.
