"""Jobs: background work that outlives the interface that started it (SPEC-0008).

A job belongs to a project, is recorded outside it, reports progress, can be
cancelled, survives project switches and is reconciled when a runtime starts
again. What it produces is staged in the operational store and enters the
production only when it is **adopted** -- the one step that writes into the
project.

Every runtime (a CLI process, the control room) opens the same store and
executes the jobs it created. Another runtime may read them and ask them to
stop.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .errors import CineToasterError, ResourceNotFoundError, ValidationError
from .events import Event, append_event

STATES = ("queued", "running", "succeeded", "failed", "cancelled", "interrupted")
FINISHED = ("succeeded", "failed", "cancelled", "interrupted")
#: A running job's runtime writes a heartbeat this often...
HEARTBEAT_SECONDS = 2.0
#: ...and a job whose heartbeat is older than this has lost its runtime.
STALE_SECONDS = 30.0
PROGRESS_EVENT_SECONDS = 1.0


class JobError(CineToasterError):
    code = "job_failed"
    http_status = 409


class JobCancelled(Exception):
    """Raised inside a job when its cancellation was requested."""


def state_root() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".local" / "state"
    return base / "cine-toaster"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return ""


# --- store -------------------------------------------------------------------

_COLUMNS = (
    "id", "kind", "project_id", "project_root", "params", "state", "progress", "message",
    "attempt", "retry_of", "runtime_id", "runtime_pid", "process_pid", "cancel_requested",
    "created_at", "started_at", "finished_at", "heartbeat_at", "error", "result", "adopted_at",
)
_JSON = {"params", "result"}


class JobStore:
    """The durable record. SQLite in WAL mode, shared by every runtime."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or state_root() / "jobs.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, project_id TEXT NOT NULL,
                    project_root TEXT NOT NULL, params TEXT NOT NULL, state TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '',
                    attempt INTEGER NOT NULL DEFAULT 1, retry_of TEXT, runtime_id TEXT,
                    runtime_pid INTEGER, process_pid INTEGER,
                    cancel_requested INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                    started_at TEXT, finished_at TEXT, heartbeat_at REAL, error TEXT,
                    result TEXT, adopted_at TEXT)"""
            )
            connection.execute("CREATE INDEX IF NOT EXISTS jobs_project ON jobs(project_id, created_at)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _row(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        job = dict(row)
        for key in _JSON:
            job[key] = json.loads(job[key]) if job[key] else ({} if key == "params" else None)
        job["cancel_requested"] = bool(job["cancel_requested"])
        return job

    def insert(self, job: dict[str, Any]) -> None:
        values = {key: job.get(key) for key in _COLUMNS}
        for key in _JSON:
            values[key] = json.dumps(values[key]) if values[key] is not None else None
        values["cancel_requested"] = int(bool(values["cancel_requested"]))
        with self._lock, self._connect() as connection:
            connection.execute(
                f"INSERT INTO jobs ({', '.join(_COLUMNS)}) VALUES ({', '.join('?' for _ in _COLUMNS)})",
                [values[key] for key in _COLUMNS],
            )

    def update(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        for key in _JSON & fields.keys():
            fields[key] = json.dumps(fields[key]) if fields[key] is not None else None
        if "cancel_requested" in fields:
            fields["cancel_requested"] = int(bool(fields["cancel_requested"]))
        assignments = ", ".join(f"{key} = ?" for key in fields)
        with self._lock, self._connect() as connection:
            connection.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", [*fields.values(), job_id])

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return self._row(connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())

    def list(self, *, project_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query, args = "SELECT * FROM jobs", []
        if project_id:
            query += " WHERE project_id = ?"
            args.append(project_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self._connect() as connection:
            return [self._row(row) for row in connection.execute(query, args).fetchall()]

    def unfinished(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM jobs WHERE state IN ('queued', 'running')").fetchall()
            return [self._row(row) for row in rows]


# --- kinds -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class JobKind:
    """What a kind of job needs: its parameters checked, then the work itself."""

    name: str
    validate: Callable[[Path, dict[str, Any]], dict[str, Any]]
    run: Callable[["JobContext"], dict[str, Any]]
    #: Called after the staged files are placed: a kind that produces a
    #: production record (an assembly version) registers it here.
    adopted: Callable[[dict[str, Any], list[str]], None] | None = None


KINDS: dict[str, JobKind] = {}


def register(kind: JobKind) -> JobKind:
    KINDS[kind.name] = kind
    return kind


class JobContext:
    """What a running job can do: report, notice cancellation, run a process."""

    def __init__(self, manager: JobManager, job: dict[str, Any]) -> None:
        self._manager = manager
        self.job_id = job["id"]
        self.project_root = Path(job["project_root"])
        self.params = job["params"]
        self.staging = manager.staging_dir(job["id"])
        self._last_check = 0.0
        self._cancelled = False

    def progress(self, fraction: float, message: str = "") -> None:
        self._manager._progress(self.job_id, max(0.0, min(1.0, fraction)), message)
        self.check()

    def cancelled(self) -> bool:
        if self._cancelled or self._manager._local_cancel(self.job_id):
            self._cancelled = True
        elif time.monotonic() - self._last_check > 0.3:
            self._last_check = time.monotonic()
            job = self._manager.store.get(self.job_id)
            self._cancelled = bool(job and job["cancel_requested"])
        return self._cancelled

    def check(self) -> None:
        if self.cancelled():
            raise JobCancelled()

    def run_process(self, command: list[str], *, expected_seconds: float | None = None,
                    message: str = "", span: tuple[float, float] = (0.0, 1.0)) -> None:
        """Run an external process, stopping it when the job is cancelled.

        An FFmpeg command gets ``-progress pipe:1`` so its encoded time drives
        the job's progress over ``span``.
        """

        is_ffmpeg = Path(command[0]).name.startswith("ffmpeg")
        if is_ffmpeg:
            command = [command[0], "-progress", "pipe:1", "-nostats", *command[1:]]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self._manager.store.update(self.job_id, process_pid=process.pid)
        state = {"seconds": 0.0}
        stderr: list[str] = []

        def read_progress() -> None:
            for line in process.stdout:  # type: ignore[union-attr]
                key, _, value = line.strip().partition("=")
                if key in ("out_time_us", "out_time_ms") and value.isdigit():
                    state["seconds"] = int(value) / 1_000_000

        def read_errors() -> None:
            stderr.extend(process.stderr)  # type: ignore[arg-type]

        readers = [threading.Thread(target=read_progress, daemon=True), threading.Thread(target=read_errors, daemon=True)]
        for reader in readers:
            reader.start()
        try:
            while process.poll() is None:
                if self.cancelled():
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise JobCancelled()
                if expected_seconds:
                    done = min(1.0, state["seconds"] / expected_seconds)
                    self._manager._progress(self.job_id, span[0] + (span[1] - span[0]) * done, message)
                time.sleep(0.2)
        finally:
            for reader in readers:
                reader.join(timeout=2)
            for stream in (process.stdout, process.stderr):
                if stream:
                    stream.close()
            self._manager.store.update(self.job_id, process_pid=None)
        if process.returncode != 0:
            tail = " / ".join("".join(stderr).strip().splitlines()[-3:])
            raise JobError(f"{Path(command[0]).name} failed: {tail}")
        self._manager._progress(self.job_id, span[1], message)


# --- manager -----------------------------------------------------------------


class JobManager:
    """The Job Manager of one runtime process."""

    def __init__(self, store: JobStore | None = None, *, max_workers: int = 2, reconcile: bool = True) -> None:
        self.store = store or JobStore()
        self.runtime_id = "rt_" + uuid.uuid4().hex[:12]
        self.pid = os.getpid()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job")
        self._futures: dict[str, Any] = {}
        self._cancel_flags: dict[str, threading.Event] = {}
        self._last_progress_event: dict[str, float] = {}
        #: Called with (manager, job) when a job finishes: how a workflow moves
        #: on without anyone polling (SPEC-0009).
        self.listeners: list[Callable[["JobManager", dict[str, Any]], None]] = []
        self._stop = threading.Event()
        self._heartbeat = threading.Thread(target=self._beat, daemon=True)
        self._heartbeat.start()
        self.reconciled: list[dict[str, Any]] = self.reconcile() if reconcile else []

    # identity and events

    def staging_dir(self, job_id: str) -> Path:
        path = self.store.path.parent / "jobs" / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _event(self, job: dict[str, Any], event_type: str, **payload: Any) -> None:
        append_event(
            Path(job["project_root"]),
            Event.create(event_type, job["project_id"], job_id=job["id"], kind=job["kind"], **payload),
        )

    def _progress(self, job_id: str, fraction: float, message: str) -> None:
        fields: dict[str, Any] = {"progress": round(fraction, 4)}
        if message:
            fields["message"] = message
        self.store.update(job_id, **fields)
        now = time.monotonic()
        if now - self._last_progress_event.get(job_id, 0.0) >= PROGRESS_EVENT_SECONDS:
            self._last_progress_event[job_id] = now
            job = self.store.get(job_id)
            if job:
                self._event(job, "job.progress", progress=round(fraction, 3), message=message)

    def _local_cancel(self, job_id: str) -> bool:
        flag = self._cancel_flags.get(job_id)
        return bool(flag and flag.is_set())

    def _beat(self) -> None:
        while not self._stop.wait(HEARTBEAT_SECONDS):
            for job_id, future in list(self._futures.items()):
                if not future.done():
                    self.store.update(job_id, heartbeat_at=time.time())

    # lifecycle

    def reconcile(self) -> list[dict[str, Any]]:
        """Mark work whose runtime is gone as interrupted, and stop its orphans."""

        changed = []
        for job in self.store.unfinished():
            if job["runtime_id"] == self.runtime_id:
                continue
            fresh = job["heartbeat_at"] and time.time() - job["heartbeat_at"] < STALE_SECONDS
            if _alive(job["runtime_pid"]) and (fresh or job["state"] == "queued"):
                continue
            message = "Its runtime exited before it finished."
            pid = job["process_pid"]
            staging = str(self.store.path.parent / "jobs" / job["id"])
            if pid and _alive(pid) and staging in _cmdline(pid):
                try:
                    os.kill(pid, 15)
                    message += f" Its orphaned process {pid} was stopped."
                except OSError:
                    pass
            self.store.update(job["id"], state="interrupted", finished_at=_now(), message=message, process_pid=None)
            job = self.store.get(job["id"])
            self._event(job, "job.interrupted", message=message)
            changed.append(job)
        return changed

    def submit(self, kind: str, project_root: Path, params: dict[str, Any] | None = None, *,
               retry_of: str | None = None, attempt: int = 1) -> dict[str, Any]:
        from .project import load_production

        if kind not in KINDS:
            raise ValidationError(f"Unknown job kind {kind!r}", available=sorted(KINDS))
        root = Path(project_root).expanduser().resolve()
        checked = KINDS[kind].validate(root, dict(params or {}))
        job = {
            "id": "job_" + uuid.uuid4().hex[:16],
            "kind": kind,
            "project_id": load_production(root)["id"],
            "project_root": str(root),
            "params": checked,
            "state": "queued",
            "progress": 0.0,
            "message": "",
            "attempt": attempt,
            "retry_of": retry_of,
            "runtime_id": self.runtime_id,
            "runtime_pid": self.pid,
            "cancel_requested": False,
            "created_at": _now(),
            "heartbeat_at": time.time(),
        }
        self.store.insert(job)
        self._cancel_flags[job["id"]] = threading.Event()
        self._event(job, "job.queued", params=checked)
        self._futures[job["id"]] = self._executor.submit(self._execute, job["id"])
        return self.store.get(job["id"])

    def _execute(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if job is None:
            return
        if job["cancel_requested"] or self._local_cancel(job_id):
            self.store.update(job_id, state="cancelled", finished_at=_now(), message="Cancelled before it started.")
            self._event(self.store.get(job_id), "job.cancelled")
            self._finished(job_id)
            return
        self.store.update(job_id, state="running", started_at=_now(), heartbeat_at=time.time())
        self._event(job, "job.started")
        context = JobContext(self, job)
        try:
            result = KINDS[job["kind"]].run(context)
        except JobCancelled:
            self.store.update(job_id, state="cancelled", finished_at=_now(), message="Cancelled.")
            self._event(self.store.get(job_id), "job.cancelled")
        except Exception as error:  # a job's failure is recorded, never raised into the runtime
            message = getattr(error, "message", None) or str(error) or type(error).__name__
            self.store.update(job_id, state="failed", finished_at=_now(), error=message, message="Failed.")
            self._event(self.store.get(job_id), "job.failed", error=message)
        else:
            self.store.update(job_id, state="succeeded", finished_at=_now(), progress=1.0,
                              message="Ready to adopt.", result=result)
            self._event(self.store.get(job_id), "job.succeeded")
        self._finished(job_id)

    def _finished(self, job_id: str) -> None:
        job = self.store.get(job_id)
        for listener in list(self.listeners):
            try:
                listener(self, job)
            except Exception as error:  # a listener's failure must not become the job's
                self._event(job, "job.listener_failed", error=str(error))

    def get(self, job_id: str) -> dict[str, Any]:
        job = self.store.get(job_id)
        if job is None:
            raise ResourceNotFoundError(f"No job {job_id!r}")
        return job

    def list(self, *, project_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list(project_id=project_id, limit=limit)

    def wait(self, job_id: str, *, timeout: float | None = None,
             on_progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        deadline = time.monotonic() + timeout if timeout else None
        while True:
            job = self.get(job_id)
            if on_progress:
                on_progress(job)
            if job["state"] in FINISHED:
                return job
            if deadline and time.monotonic() > deadline:
                raise TimeoutError(f"Job {job_id} is still {job['state']}")
            time.sleep(0.2)

    def cancel(self, job_id: str) -> dict[str, Any]:
        job = self.get(job_id)
        if job["state"] in FINISHED:
            raise JobError(f"Job {job_id} is already {job['state']}", state=job["state"])
        self.store.update(job_id, cancel_requested=True)
        flag = self._cancel_flags.get(job_id)
        if flag:
            flag.set()
        return self.get(job_id)

    def retry(self, job_id: str) -> dict[str, Any]:
        job = self.get(job_id)
        if job["state"] not in ("failed", "cancelled", "interrupted"):
            raise JobError(f"Only a failed, cancelled or interrupted job can be retried; {job_id} is {job['state']}",
                           state=job["state"])
        return self.submit(job["kind"], Path(job["project_root"]), job["params"],
                           retry_of=job["id"], attempt=job["attempt"] + 1)

    def adopt(self, job_id: str, *, overwrite: bool = False, destination: Path | None = None) -> dict[str, Any]:
        """Copy a finished job's staged files into the project: its only write there.

        ``destination`` replaces the declared one for a single-file result, when
        the caller chose where it goes (the CLI's ``--output``).
        """

        job = self.get(job_id)
        if job["state"] != "succeeded":
            raise JobError(f"Only a succeeded job can be adopted; {job_id} is {job['state']}", state=job["state"])
        files = (job["result"] or {}).get("files", [])
        if destination is not None and len(files) != 1:
            raise ValidationError("A destination can only be given for a single-file result")
        root = Path(job["project_root"])
        staging = self.store.path.parent / "jobs" / job_id
        placed = []
        plan = []
        for item in files:
            source = staging / item["staged"]
            if not source.is_file():
                raise JobError(f"The staged file {item['staged']} is gone; retry the job.")
            target = Path(destination).expanduser().resolve() if destination else (root / item["destination"]).resolve()
            if destination is None:
                target.relative_to(root.resolve())  # a declared destination stays inside the project
            if target.exists() and not overwrite:
                raise JobError(f"{target} exists; adopt with overwrite to replace it.", path=str(target))
            plan.append((source, target))
        for source, target in plan:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.adopting")
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
            placed.append(str(target))
        hook = KINDS[job["kind"]].adopted if job["kind"] in KINDS else None
        if hook:
            hook(job, placed)
        self.store.update(job_id, adopted_at=_now(), message=f"Adopted: {', '.join(placed)}")
        job = self.get(job_id)
        self._event(job, "job.adopted", files=placed)
        return job

    def shutdown(self, *, wait: bool = True) -> None:
        self._stop.set()
        self._executor.shutdown(wait=wait, cancel_futures=not wait)


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in job.items() if key not in ("runtime_pid", "process_pid", "heartbeat_at")}


# --- the first kinds -----------------------------------------------------------


def _validate_previs(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    from .project import load_scene

    scene_id, shot_id = str(params.get("scene", "")).strip(), str(params.get("shot", "")).strip()
    scene = load_scene(root, scene_id) if scene_id else None
    shot = next((item for item in (scene or {}).get("shots", []) if item["id"] == shot_id), None)
    if shot is None:
        raise ValidationError(f"No shot {scene_id} {shot_id}")
    if not ((shot.get("motion") or {}).get("start") or {}).get("camera"):
        raise ValidationError(f"{scene_id} {shot_id} has no camera pose to look from")
    return {"scene": scene_id, "shot": shot_id}


def _run_previs(context: JobContext) -> dict[str, Any]:
    from .blocking import PREVIS_FPS, previs
    from .project import load_scene

    scene = load_scene(context.project_root, context.params["scene"])
    shot = next(item for item in scene["shots"] if item["id"] == context.params["shot"])
    context.progress(0.02, "Drawing the frames")
    result = previs(scene, shot)
    frames = context.staging / "frames"
    frames.mkdir(exist_ok=True)
    for index, svg in enumerate(result["frames"]):
        (frames / f"{index:04d}.svg").write_text(svg, encoding="utf-8")
        if index % 12 == 0:
            context.progress(0.02 + 0.18 * index / len(result["frames"]), "Drawing the frames")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise JobError("FFmpeg is needed to encode the previs.")
    output = context.staging / "previs.mp4"
    context.run_process(
        [ffmpeg, "-y", "-loglevel", "error", "-framerate", str(PREVIS_FPS),
         "-i", str(frames / "%04d.svg"), "-vf", "scale=1280:720,format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-r", "24", str(output)],
        expected_seconds=result["duration_seconds"], message="Encoding", span=(0.2, 1.0),
    )
    shutil.rmtree(frames, ignore_errors=True)
    name = f"{context.params['scene']}-{context.params['shot']}.mp4"
    return {
        "files": [{"staged": "previs.mp4", "destination": f"renders/previs/{name}"}],
        "summary": {"frames": len(result["frames"]), "duration_seconds": result["duration_seconds"]},
    }


def _validate_build(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    from .build import ENGINES

    engine = str(params.get("engine") or "auto")
    if engine not in ENGINES:
        raise ValidationError(f"Unknown engine {engine!r}", available=list(ENGINES))
    return {"engine": engine}


def _run_build(context: JobContext) -> dict[str, Any]:
    from .build import BuildCancelled, build
    from .project import load_production

    production_id = load_production(context.project_root)["id"]
    output = context.staging / f"{production_id}.mp4"
    try:
        result = build(
            context.project_root, output, engine=context.params["engine"],
            work=context.staging / "work", progress=context.progress, should_stop=context.cancelled,
        )
    except BuildCancelled as error:
        raise JobCancelled() from error
    return {
        "files": [{"staged": output.name, "destination": f"renders/{production_id}.mp4"}],
        "summary": {**result.public_dict(), "output": None},
    }


register(JobKind("previs", _validate_previs, _run_previs))


def _validate_boards(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    from .project import load_scene

    scene_id = str(params.get("scene", "")).strip()
    scene = load_scene(root, scene_id) if scene_id else None
    if scene is None:
        raise ValidationError(f"No scene {scene_id!r}")
    if not (scene.get("geometry") or {}).get("cameras"):
        raise ValidationError(f"{scene_id} has no cameras in its plan to draw boards from")
    look = str(params.get("look") or "clay")
    if look not in ("clay", "colour"):
        raise ValidationError(f"Unknown board look {look!r}", allowed=["clay", "colour"])
    return {"scene": scene_id, "ends": bool(params.get("ends")), "look": look}


def _run_boards(context: JobContext) -> dict[str, Any]:
    """The scene's 3D boards, depth maps and labelled sheet (CT-0049), adopted into renders/boards/."""

    from .board import boards, sheet
    from .project import load_scene

    scene = load_scene(context.project_root, context.params["scene"])
    context.progress(0.05, "Drawing the boards in Blender")
    out = context.staging / "boards"
    out.mkdir()
    made = boards(context.project_root, scene, ends=context.params["ends"], look=context.params["look"], folder=out)
    sheet(context.project_root, scene, folder=out)
    prefix = f"renders/boards/{scene['id']}"
    return {"files": [{"staged": f"boards/{path.name}", "destination": f"{prefix}/{path.name}"}
                      for path in sorted(out.iterdir()) if path.is_file()],
            "summary": {"boards": len(made), "scene": scene["id"]}}


def _run_board_animatic(context: JobContext) -> dict[str, Any]:
    """The scene played through its cameras in 3D, to check the breakdown (never a model's input)."""

    from .board import animatic
    from .project import load_scene

    scene = load_scene(context.project_root, context.params["scene"])
    context.progress(0.05, "Playing the scene through its cameras")
    animatic(context.project_root, scene, output=context.staging / "animatic.mp4")
    return {"files": [{"staged": "animatic.mp4", "destination": f"renders/boards/{scene['id']}/animatic.mp4"}],
            "summary": {"scene": scene["id"]}}


register(JobKind("boards", _validate_boards, _run_boards))
register(JobKind("board_animatic", _validate_boards, _run_board_animatic))
register(JobKind("build", _validate_build, _run_build))


def _next_version(root: Path, scene_id: str) -> str:
    from .project import load_scene

    scene = load_scene(root, scene_id) or {}
    taken = {item["id"] for item in scene.get("assemblies") or []}
    number = 1
    while f"v{number}" in taken:
        number += 1
    return f"v{number}"


def _validate_assemble(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    from .assembly import plan_scene
    from .project import load_scene

    scene_id = str(params.get("scene", "")).strip()
    scene = load_scene(root, scene_id) if scene_id else None
    if scene is None:
        raise ValidationError(f"No scene {scene_id!r}")
    plan_scene(root, scene)  # refuse up front a scene with nothing to assemble
    version = str(params.get("version") or "").strip() or _next_version(root, scene_id)
    if any(item["id"] == version for item in scene.get("assemblies") or []):
        raise ValidationError(f"{scene_id} already has a version {version!r}")
    return {"scene": scene_id, "version": version, "summary": str(params.get("summary") or "")}


def _voices_for_cut(context: JobContext, production: dict[str, Any], scene_id: str, plan) -> dict[str, Any]:
    """Convert the voices of the shots the cut hears in the cast's own voices (CT-0040).

    Each conversion is kept in the operational state, keyed by the take, the
    recordings, the lines and the worker, so assembling again costs nothing
    and changing any of them converts again. A cache: deleting it loses time,
    not the film. A shot that cannot be converted any more keeps its take's
    sound, and the version says so.
    """

    from .voice import WORKER, plan_conversion, voice_python

    root = context.project_root
    wanted = [segment for segment in plan.segments if segment.revoice]
    measured: dict[str, Any] = {}
    python = voice_python() if wanted else None
    for index, segment in enumerate(wanted):
        if python is None:
            plan.notes.append(f"{segment.shot} keeps its take's own voice: the voice environment is not installed "
                              "(make install-voice).")
            continue
        try:
            voice = plan_conversion(root, production, scene_id, segment.shot, segment.take)
        except ValidationError as error:
            plan.notes.append(f"{segment.shot} keeps its take's own voice: {error}")
            continue
        spec = voice.spec()
        hashed = hashlib.sha256()
        for path in (voice.media, *(item["reference"] for item in voice.speakers), WORKER,
                     *([voice.words] if voice.words else [])):
            hashed.update(hashlib.sha256(Path(path).read_bytes()).digest())
        hashed.update(json.dumps(spec["lines"], sort_keys=True).encode())
        cache = state_root() / "voice"
        cache.mkdir(parents=True, exist_ok=True)
        key = hashed.hexdigest()[:24]
        audio, report = cache / f"{key}.wav", cache / f"{key}.json"
        span = (0.02 + 0.58 * index / len(wanted), 0.02 + 0.58 * (index + 1) / len(wanted))
        if not (audio.is_file() and report.is_file()):
            staged = context.staging / f"voice-{segment.shot}"
            staged.mkdir(parents=True, exist_ok=True)
            (staged / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
            context.run_process([str(python), str(WORKER), str(voice.media), str(staged / "spec.json"),
                                 str(staged / "voice.wav"), str(staged / "work"), str(staged / "report.json")],
                                message=f"{segment.shot}: {voice.speaker} in their own voice", span=span)
            shutil.move(staged / "voice.wav", audio)
            shutil.move(staged / "report.json", report)
            shutil.rmtree(staged, ignore_errors=True)
        result = json.loads(report.read_text(encoding="utf-8"))
        segment.sound = str(audio)
        measured[segment.shot] = {"take": segment.take, "speakers": voice.public_dict(root)["speakers"],
                                  "similarity_by_speaker": result.get("similarity_by_speaker")
                                  or ({voice.speaker: result["similarity"]} if result.get("similarity") else {}),
                                  "unplaced": result.get("unplaced") or [], "cache": key}
        for who in result.get("unplaced") or []:
            plan.notes.append(f"{segment.shot}: {who} was not heard in take {segment.take}.")
    return measured


def _run_assemble(context: JobContext) -> dict[str, Any]:
    from .assembly import plan_scene, render
    from .project import load_scene

    from .project import load_production

    production = load_production(context.project_root)
    scene = next(item for item in production["scenes"] if item["id"] == context.params["scene"])
    plan = plan_scene(context.project_root, scene, production.get("words_sidecar") or "{stem}.words.json")
    context.progress(0.01, f"{len(plan.segments)} shots")
    voices = _voices_for_cut(context, production, scene["id"], plan)
    output = context.staging / "assembly.mp4"
    # The same cut in every format it is delivered in (CT-0049): planned once, rendered per format.
    deliveries = [(item, copy.deepcopy(plan)) for item in scene.get("deliver") or []]
    share = 1.0 / (1 + len(deliveries))
    start = 0.6 if voices else 0.0
    render(context.project_root, plan, output, context.staging / "work", context.run_process,
           span=(start, start + (1.0 - start) * share))
    shutil.rmtree(context.staging / "work", ignore_errors=True)
    scene_id, version = context.params["scene"], context.params["version"]
    # A version lives with its scene, beside the breakdown that made it (ADR 0021).
    from .versions import scene_versions

    folder = scene_versions(scene["file"])
    shutil.copyfile(context.project_root / scene["file"], context.staging / "assembly.scene.yaml")
    renditions = []
    for index, (item, copied) in enumerate(deliveries, 1):
        copied.format = {"aspect": item["aspect"], **({"captions": True} if item["captions"] else {})}
        name = f"assembly.{item['id']}.mp4"
        render(context.project_root, copied, context.staging / name, context.staging / f"work-{item['id']}",
               context.run_process, span=(start + (1.0 - start) * share * index,
                                          start + (1.0 - start) * share * (index + 1)))
        shutil.rmtree(context.staging / f"work-{item['id']}", ignore_errors=True)
        renditions.append({"staged": name, "destination": f"{folder}/{version}.{item['id']}.mp4",
                           "rendition": item["id"]})
    # Where speech is heard in this version: a sequence's music ducks under it (CT-0051).
    (context.staging / "assembly.speech.json").write_text(json.dumps({"speech": plan.speech}), encoding="utf-8")
    return {
        "files": [{"staged": "assembly.mp4", "destination": f"{folder}/{version}.mp4"},
                  {"staged": "assembly.speech.json", "destination": f"{folder}/{version}.mp4.speech.json"},
                  {"staged": "assembly.scene.yaml", "destination": f"{folder}/{version}.scene.yaml"}, *renditions],
        "summary": {"segments": [{**{key: value for key, value in asdict(segment).items() if key not in ("sound", "source")},
                                  "gain_db": plan.gains.get(segment.shot, 0.0)} for segment in plan.segments],
                    "notes": plan.notes, "voices": voices, "sound": plan.sound, "loudness": plan.loudness,
                    "duration_seconds": plan.duration, "takes": plan.takes},
    }


def _adopted_assemble(job: dict[str, Any], placed: list[str]) -> None:
    """An adopted assembly is a new version of the scene, with the takes it used."""

    from .commands import Actor, record_assembly

    root = Path(job["project_root"])
    summary = job["result"]["summary"]
    media = Path(placed[0]).resolve().relative_to(root.resolve()).as_posix()
    notes = " ".join(summary["notes"])
    if summary.get("voices"):
        notes = f"Heard in the cast's own voices: {', '.join(summary['voices'])}. " + notes
    if summary.get("sound"):
        laid = ", ".join(f"{item['id']} ({item['kind']}, {item['start']:g} s)" for item in summary["sound"])
        notes = f"Sound laid: {laid}. " + notes
    if summary.get("loudness"):
        tracks = " and ".join(f"{name} ({value:.1f} LUFS)" for name, value in summary["loudness"].items())
        notes = f"Tracks: {tracks}. " + notes
    record_assembly(
        root,
        scene_id=job["params"]["scene"],
        assembly_id=job["params"]["version"],
        actor=Actor(id="assembly-job", kind="system"),
        media=media,
        summary=(job["params"].get("summary") or f"Assembled from the selected takes (job {job['id']})")
        + (f". Notes: {notes}" if notes else "."),
        duration_seconds=summary["duration_seconds"],
        takes=summary["takes"],
        renditions={item["rendition"]: Path(path).resolve().relative_to(root.resolve()).as_posix()
                    for item, path in zip(job["result"]["files"], placed) if item.get("rendition")},
    )


register(JobKind("assemble", _validate_assemble, _run_assemble, _adopted_assemble))


def _block_context(root: Path, scene_id: str, block_id: str):
    from .blocks import scene_blocks
    from .project import load_scene
    from .takes import work_directory_for

    scene = load_scene(root, scene_id)
    if scene is None:
        raise ValidationError(f"No scene {scene_id!r}")
    work = work_directory_for(root / scene["file"])
    block = next((item for item in scene_blocks(scene, work, root) if item.id == block_id), None)
    if block is None:
        raise ValidationError(f"{scene_id} has no block {block_id!r}")
    return scene, work, block


def _validate_slice(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    scene_id, block_id = str(params.get("scene", "")).strip(), str(params.get("block", "")).strip()
    _, work, block = _block_context(root, scene_id, block_id)
    if not block.clip:
        raise ValidationError(f"Block {block_id} of {scene_id} has no clip (expected b{block_id}.mp4 in {work.name}/)")
    if not block.contiguous:
        raise ValidationError(f"Block {block_id} of {scene_id} is not a run of consecutive shots")
    clip = str(params.get("clip") or "").strip()
    if clip:
        # A version by its file name or its path: `b2-1.mp4`.
        match = next((item for item in block.versions if item == clip or item.rsplit("/", 1)[-1] == clip), None)
        if match is None:
            raise ValidationError(f"Block {block_id} has no clip {clip!r}; it has {', '.join(block.versions)}")
        return {"scene": scene_id, "block": block_id, "clip": match}
    return {"scene": scene_id, "block": block_id}


def _run_slice(context: JobContext) -> dict[str, Any]:
    """Find where each shot starts in the block's clip, and cut one take per shot."""

    from .blocks import clip_info, decide, reference_picture
    from .takes import TAKES_DIRECTORIES, shot_key

    root = context.project_root
    scene, work, block = _block_context(root, context.params["scene"], context.params["block"])
    clip = root / (context.params.get("clip") or block.clip)
    version = clip.stem.partition("-")[2]
    length, fps = clip_info(clip)
    shots = {shot["id"]: shot for shot in scene["shots"]}
    references = [reference_picture(work, root, scene, shots[shot_id]) for shot_id in block.shots]
    context.progress(0.05, "Finding the cuts")
    slicing = decide(clip, block.durations, references, fps)
    ffmpeg = shutil.which("ffmpeg")
    ends = slicing.starts[1:] + [round(length * fps)]
    takes_dir = work / TAKES_DIRECTORIES[0]
    files, slices = [], []
    for index, (shot_id, start, end) in enumerate(zip(block.shots, slicing.starts, ends)):
        number = shot_key(shots[shot_id]["number"])
        digits = "".join(ch for ch in number if ch.isdigit())
        stem = f"c{int(digits):02d}{number[len(digits):]}" if digits else f"c{number}"
        base = f"block-{block.id}" + (f"v{version}" if version else "")
        slug, attempt = base, 1
        while (takes_dir / f"{stem}-{slug}.mp4").exists():
            attempt += 1
            slug = f"{base}-{attempt}"
        name = f"{stem}-{slug}.mp4"
        context.run_process(
            [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{start / fps:.4f}", "-to", f"{end / fps:.4f}", "-i", str(clip),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", str(context.staging / name)],
            expected_seconds=(end - start) / fps, message=f"Cutting {shot_id}",
            span=(0.1 + 0.85 * index / len(block.shots), 0.1 + 0.85 * (index + 1) / len(block.shots)),
        )
        provenance = {
            "kind": "block-slice", "block": block.id, "clip": clip.relative_to(root).as_posix(), "frames": [start, end],
            "seconds": [round(start / fps, 3), round(end / fps, 3)], "method": slicing.method,
            "detected": slicing.detected, "requested": slicing.requested, "note": slicing.note,
            "reference": references[index].relative_to(root).as_posix() if references[index] else "",
            "job": context.job_id,
        }
        # The generation that made the block made this slice: its record travels with it.
        from .takes import JOB_SUFFIX, _read_json

        block_job = _read_json(clip.with_name(clip.name + JOB_SUFFIX))
        if block_job:
            provenance["generation"] = {**block_job, "shared_by": len(block.shots)}
        # And what the block was made from, when Cine Toaster made it.
        block_made = _read_json(clip.with_name(clip.name + ".provenance.json"))
        if block_made:
            provenance["block_generation"] = block_made
        (context.staging / f"{name}.provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
        destination = (takes_dir / name).relative_to(root).as_posix()
        files += [{"staged": name, "destination": destination},
                  {"staged": f"{name}.provenance.json", "destination": destination + ".provenance.json"}]
        slices.append({"shot": shot_id, "take": slug.upper(), "seconds": provenance["seconds"]})
    return {"files": files, "summary": {"block": block.id, "method": slicing.method, "note": slicing.note, "slices": slices}}


register(JobKind("slice_block", _validate_slice, _run_slice))


def _sequence_plan(root: Path, sequence_id: str):
    """Each scene of the sequence, in order, by its approved version or else its latest."""

    from .assembly import Plan, Segment, _resolve_join, probe
    from .project import load_production

    production = load_production(root)
    sequence = next((item for item in production["sequences"] if item["id"] == sequence_id), None)
    if sequence is None or sequence_id == "unassigned":
        raise ValidationError(f"No sequence {sequence_id!r}")
    scenes = {scene["id"]: scene for scene in production["scenes"]}
    plan = Plan(scene=sequence_id)
    joins: dict[str, Any] = {}
    for scene_id in sequence["scene_ids"]:
        scene = scenes[scene_id]
        versions = [item for item in scene.get("assemblies") or [] if item.get("media") and (root / item["media"]).is_file()]
        approved = scene.get("approved_assembly") or {}
        chosen = next((item for item in versions if item["id"] == approved.get("id")), None) or (versions[0] if versions else None)
        if chosen is None:
            plan.notes.append(f"{scene_id} has no assembled version with a file; it is left out.")
            continue
        if chosen["id"] != approved.get("id"):
            plan.notes.append(f"{scene_id} has no approved version; its latest, {chosen['id']}, is used.")
        length = probe(root / chosen["media"])["duration"]
        enter = scene.get("enter") or {}
        segment = Segment(scene_id, chosen["id"], chosen["media"], 0.0, round(length, 3), enter.get("type") or "hard",
                          "version", normalize=False, renditions=dict(chosen.get("renditions") or {}))
        spoken = root / (chosen["media"] + ".speech.json")
        if spoken.is_file():
            segment.speech_spans = [tuple(span) for span in json.loads(spoken.read_text(encoding="utf-8"))["speech"]]
        if plan.segments:
            # The join between scenes, declared on the incoming scene: a version has no sound beyond its
            # ends, so a J/L-cut between scenes is said to be straight (its handle is nothing).
            _resolve_join(root, plan, enter, segment, joins)
        elif enter:
            plan.notes.append(f"{scene_id} opens the sequence: there is no scene before it to enter from.")
        plan.segments.append(segment)
    if not plan.segments:
        raise ValidationError(f"No scene of {sequence_id!r} has an assembled version yet")
    if sequence.get("ambience") or sequence.get("music"):
        from .sounds import place

        cues, notes = place({"shots": [], "ambience": sequence.get("ambience"), "music": sequence.get("music")},
                            plan.segments)
        plan.cues = cues
        plan.notes.extend(note.replace(" in this version", " in this sequence version") for note in notes)
    return plan


def _validate_assemble_sequence(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    from .sequence_state import versions

    sequence_id = str(params.get("sequence", "")).strip()
    _sequence_plan(root, sequence_id)
    taken = {item["id"] for item in versions(root, sequence_id)}
    version = str(params.get("version") or "").strip()
    if not version:
        number = 1
        while f"v{number}" in taken:
            number += 1
        version = f"v{number}"
    if version in taken:
        raise ValidationError(f"{sequence_id} already has a version {version!r}")
    return {"sequence": sequence_id, "version": version, "summary": str(params.get("summary") or "")}


def _run_assemble_sequence(context: JobContext) -> dict[str, Any]:
    from .assembly import render

    from .formats import renditions as parse_renditions
    from .project import load_production
    from .styles import list_styles
    from .versions import sequence_versions

    root = context.project_root
    plan = _sequence_plan(root, context.params["sequence"])
    deliver, _ = parse_renditions(load_production(root).get("deliver"),
                                  {item["id"]: item for item in list_styles(root)})
    deliveries = [(item, copy.deepcopy(plan)) for item in deliver]
    share = 1.0 / (1 + len(deliveries))
    output = context.staging / "sequence.mp4"
    render(root, plan, output, context.staging / "work", context.run_process, span=(0.0, share))
    shutil.rmtree(context.staging / "work", ignore_errors=True)
    sequence_id, version = context.params["sequence"], context.params["version"]
    renditions = []
    for index, (item, copied) in enumerate(deliveries, 1):
        # Each scene's own rendition in this format, reframed and captioned already; a scene without one is
        # reframed here, centred, and said.
        for segment in copied.segments:
            if item["id"] in segment.renditions:
                segment.media = segment.renditions[item["id"]]
            else:
                plan.notes.append(f"{segment.shot}'s version {segment.take} has no {item['name']} rendition; "
                                  "the sequence's is reframed from it, centred and without captions.")
        copied.format = {"aspect": item["aspect"]}
        name = f"sequence.{item['id']}.mp4"
        render(root, copied, context.staging / name, context.staging / f"work-{item['id']}", context.run_process,
               span=(share * index, share * (index + 1)))
        shutil.rmtree(context.staging / f"work-{item['id']}", ignore_errors=True)
        renditions.append({"staged": name, "destination": f"{sequence_versions(sequence_id)}/{version}.{item['id']}.mp4",
                           "rendition": item["id"]})
    return {
        "files": [{"staged": "sequence.mp4", "destination": f"{sequence_versions(sequence_id)}/{version}.mp4"},
                  *renditions],
        "summary": {"scenes": plan.takes, "notes": plan.notes, "duration_seconds": plan.duration, "sound": plan.sound},
    }


def _adopted_assemble_sequence(job: dict[str, Any], placed: list[str]) -> None:
    from .commands import Actor, record_sequence_version

    root = Path(job["project_root"])
    summary = job["result"]["summary"]
    notes = " ".join(summary["notes"])
    if summary.get("sound"):
        laid = ", ".join(f"{item['id']} ({item['kind']}, {item['start']:g} s)" for item in summary["sound"])
        notes = f"Sound laid: {laid}. " + notes
    record_sequence_version(
        root,
        sequence_id=job["params"]["sequence"],
        version_id=job["params"]["version"],
        actor=Actor(id="assembly-job", kind="system"),
        media=Path(placed[0]).resolve().relative_to(root.resolve()).as_posix(),
        scenes=summary["scenes"],
        summary=(job["params"].get("summary") or f"Assembled from the scenes' versions (job {job['id']})")
        + (f". Notes: {notes}" if notes else "."),
        duration_seconds=summary["duration_seconds"],
        renditions={item["rendition"]: Path(path).resolve().relative_to(root.resolve()).as_posix()
                    for item, path in zip(job["result"]["files"], placed) if item.get("rendition")},
    )


register(JobKind("assemble_sequence", _validate_assemble_sequence, _run_assemble_sequence, _adopted_assemble_sequence))



# --- generating a block ------------------------------------------------------


#: Tests replace the RunPod transport; production code leaves it None.
GENERATION_TRANSPORT = None


def _generation_plan(root: Path, params: dict[str, Any]):
    """A block's plan, or -- with `shot` -- one shot outside any block."""

    from .generation import hourly_rate, plan_block, plan_shot
    from .project import load_production

    endpoint = os.environ.get("RUNPOD_LTX_ENDPOINT_ID", "")
    production = load_production(root)
    scene = str(params.get("scene", "")).strip()
    seed, rate = int(params.get("seed") or 1), hourly_rate(root, endpoint)
    if str(params.get("shot") or "").strip():
        plan = plan_shot(root, production, scene, str(params["shot"]).strip(), seed=seed, rate=rate)
    else:
        plan = plan_block(root, production, scene, str(params.get("block", "")).strip(), seed=seed, rate=rate)
    return plan, endpoint


def _single(context_or_params) -> bool:
    params = getattr(context_or_params, "params", context_or_params)
    return bool(str(params.get("shot") or "").strip())


def _validate_generate(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    from . import spend

    plan, endpoint = _generation_plan(root, params)
    if GENERATION_TRANSPORT is None and not (endpoint and os.environ.get("RUNPOD_API_KEY")):
        raise ValidationError("Generation needs RUNPOD_API_KEY and RUNPOD_LTX_ENDPOINT_ID in the environment "
                              "(toast generate --env-file <file> reads them without printing them)")
    if _single(params):
        spend.check(plan.estimate_usd, f"Shot {plan.block} of {plan.scene}")
        return {"scene": plan.scene, "shot": plan.block, "seed": plan.seed}
    spend.check(plan.estimate_usd, f"Block {plan.block} of {plan.scene}")
    return {"scene": plan.scene, "block": plan.block, "seed": plan.seed}


def _paid_transport(context: JobContext, endpoint: str, working: str):
    """The RunPod transport for a paid job: progress from its status, and a
    cancelled job cancels the remote work too, not only the waiting."""

    from .providers import runpod

    base = GENERATION_TRANSPORT or runpod.request
    remote = {"id": ""}

    def transport(path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if body is None and remote["id"] and context.cancelled():
            try:
                base(f"/{endpoint}/cancel/{remote['id']}", {})
            finally:
                raise JobCancelled()
        response = base(path, body)
        if path.endswith("/run"):
            remote["id"] = response.get("id", "")
        elif body is None:
            status = response.get("status", "")
            context.progress(0.1 if status == "IN_QUEUE" else 0.5,
                             {"IN_QUEUE": "Waiting for a worker", "IN_PROGRESS": working}.get(status, status.title()))
        return response

    return transport


def _remote_record(kind: str, identity: dict[str, Any]) -> Path:
    """Where a paid request's remote job is remembered until its result is adopted.

    Keyed by the request itself (what is asked, of what, with which seed), not by
    the job: a retry after the runtime died finds the remote job and waits for it,
    instead of sending -- and paying for -- the same work again.
    """

    import hashlib

    key = hashlib.sha256(json.dumps({"kind": kind, **identity}, sort_keys=True).encode()).hexdigest()[:24]
    return state_root() / "remote" / f"{kind}-{key}.job.json"


def _settle_remote(pending: Path, staged: Path | None) -> None:
    """After a paid call: keep the record for provenance, and free the request.

    A finished request (done, failed, cancelled) is forgotten, so asking again
    really asks again; one still running at the remote end is kept for a retry.
    """

    from .providers.runpod import TERMINAL_FAILURES

    if not pending.is_file():
        return
    record = json.loads(pending.read_text(encoding="utf-8") or "{}")
    finished = staged is not None or record.get("status") in (*TERMINAL_FAILURES, "COMPLETED")
    if staged is not None:
        shutil.copyfile(pending, staged)
    if finished:
        pending.unlink(missing_ok=True)


def _record_spend(context: JobContext, record_path: Path, rate: float, what: str, estimate_usd: float) -> float:
    """What the platform billed is spent whatever the outcome; returns it."""

    from . import spend
    from .providers import runpod

    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {}
    cost = runpod.cost_usd(record, rate) if record else 0.0
    if record.get("id"):
        spend.record(cost, what, job=context.job_id, remote=record["id"], status=record.get("status", ""),
                     estimate_usd=estimate_usd)
    return cost


def _run_generate(context: JobContext) -> dict[str, Any]:
    """One paid generation of the block, kept as a new version of its clip."""

    from . import spend
    from .blocks import block_versions
    from .generation import hourly_rate
    from .project import load_production
    from .providers.ltx import Guide, LtxProvider
    from .takes import JOB_SUFFIX, work_directory_for

    root = context.project_root
    plan, endpoint = _generation_plan(root, context.params)
    single = _single(context)
    what = f"{'Shot' if single else 'Block'} {plan.block} of {plan.scene}"
    spend.check(plan.estimate_usd, what)  # again: another job may have spent since this one was queued
    scene = next(item for item in load_production(root)["scenes"] if item["id"] == plan.scene)
    work = work_directory_for(root / scene["file"])
    if single:
        # One shot: the result is a take of it, beside the others (GEN, GEN-2…).
        from .takes import TAKES_DIRECTORIES, shot_key

        number = shot_key(next(shot["number"] for shot in scene["shots"] if shot["id"] == plan.block))
        digits = "".join(ch for ch in number if ch.isdigit())
        stem = f"c{int(digits):02d}{number[len(digits):]}" if digits else f"c{number}"
        home = work / TAKES_DIRECTORIES[0]
        slug, attempt = "gen", 1
        while (home / f"{stem}-{slug}.mp4").exists():
            attempt += 1
            slug = f"gen-{attempt}"
        name = f"{stem}-{slug}.mp4"
    else:
        home = work
        numbers = [int(path.stem.rpartition("-")[2]) for path in block_versions(work, plan.block) if "-" in path.stem]
        name = f"b{plan.block}-{max(numbers, default=0) + 1}.mp4"
    output = context.staging / name
    transport = _paid_transport(context, endpoint, "Generating")

    context.progress(0.02, "Sending the block")
    provider = LtxProvider(endpoint, transport=transport)
    guides = tuple(Guide(ref.path, ref.frame, ref.strength) for ref in plan.guides)
    record_path = output.with_name(name + JOB_SUFFIX)
    pending = _remote_record("generate_shot" if single else "generate_block", plan.public_dict(root))
    try:
        result = provider.generate(image=plan.image, output=output, seconds=plan.seconds, prompt=plan.prompt,
                                   seed=plan.seed, guides=guides, label=what, state_file=pending)
    except BaseException:
        cost = _record_spend(context, pending, hourly_rate(root, endpoint), what, plan.estimate_usd)
        if context.cancelled():
            pending.unlink(missing_ok=True)  # the remote job was cancelled with it
        _settle_remote(pending, None)
        raise
    cost = _record_spend(context, pending, hourly_rate(root, endpoint), what, plan.estimate_usd)
    _settle_remote(pending, record_path)
    provenance = {
        "kind": "shot-generation" if single else "block-generation", "scene": plan.scene, "block": plan.block,
        "shots": plan.shots,
        "provider": result.provider, "model": result.model, "seed": plan.seed, "seconds": plan.seconds,
        **plan.public_dict(root), "settings": result.provenance,
        "cost_usd": round(cost, 4), "job_id": context.job_id,
    }
    (context.staging / f"{name}.provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    destination = (home / name).relative_to(root).as_posix()
    files = [{"staged": name, "destination": destination},
             {"staged": record_path.name, "destination": destination + JOB_SUFFIX},
             {"staged": f"{name}.provenance.json", "destination": destination + ".provenance.json"}]
    return {"files": files, "summary": {"scene": plan.scene, "block": plan.block, "clip": destination,
                                        "shot": plan.block if single else "", "take": name.rsplit(".", 1)[0].split("-", 1)[1].upper() if single else "",
                                        "cost_usd": round(cost, 4), "estimate_usd": plan.estimate_usd}}


register(JobKind("generate_block", _validate_generate, _run_generate))


# --- converting a take's voice -------------------------------------------------


def _voice_plan(root: Path, params: dict[str, Any]):
    from .project import load_production
    from .voice import plan_conversion

    return plan_conversion(root, load_production(root), str(params.get("scene", "")).strip(),
                           str(params.get("shot", "")).strip(), str(params.get("take", "") or "").strip())


def _validate_voice(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    from .voice import voice_python

    plan = _voice_plan(root, params)
    if voice_python() is None:
        raise ValidationError("Voice conversion needs its own environment: make install-voice "
                              "(or set CINE_TOASTER_VOICE_PYTHON)")
    return {"scene": plan.scene, "shot": plan.shot, "take": plan.take}


def _run_voice(context: JobContext) -> dict[str, Any]:
    """The take's speech in the cast member's voice, as a new take beside it."""

    from .takes import REJECTED_DIRECTORIES, TAKES_DIRECTORIES
    from .voice import WORKER, mux_command, voice_python

    root = context.project_root
    plan = _voice_plan(root, context.params)
    python = voice_python()
    if python is None:
        raise ValidationError("The voice environment is gone (make install-voice)")
    work = context.staging / "voice-work"
    audio, report = context.staging / "voice.wav", context.staging / "voice-report.json"
    context.progress(0.02, f"Separating and converting {plan.speaker}'s voice")
    spec = context.staging / "voice-spec.json"
    spec.write_text(json.dumps(plan.spec(), indent=2), encoding="utf-8")
    context.run_process([str(python), str(WORKER), str(plan.media), str(spec), str(audio), str(work), str(report)],
                        message=f"Converting {plan.speaker}'s voice", span=(0.02, 0.9))
    # A converted take sits with the takes, even when its source is the cut's own or a rejected one.
    work_dir = plan.media.parent
    if work_dir.name in (*TAKES_DIRECTORIES, *REJECTED_DIRECTORIES):
        work_dir = work_dir.parent
    takes_dir = work_dir / TAKES_DIRECTORIES[0]
    stem, attempt = f"{plan.media.stem}-voice", 1
    while (takes_dir / f"{stem}.mp4").exists():
        attempt += 1
        stem = f"{plan.media.stem}-voice-{attempt}"
    name = f"{stem}.mp4"
    context.run_process(mux_command(plan.media, audio, context.staging / name), message="Putting the voice under the picture",
                        span=(0.9, 1.0))
    shutil.rmtree(work, ignore_errors=True)
    measured = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    provenance = {"kind": "voice-conversion", **plan.public_dict(root), "from_take": plan.take, **measured,
                  "job": context.job_id}
    (context.staging / f"{name}.provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    destination = (takes_dir / name).relative_to(root).as_posix()
    return {"files": [{"staged": name, "destination": destination},
                      {"staged": f"{name}.provenance.json", "destination": destination + ".provenance.json"}],
            "summary": {"scene": plan.scene, "shot": plan.shot, "from_take": plan.take, "file": name,
                        "media": destination, "similarity": measured.get("similarity"),
                        "similarity_by_speaker": measured.get("similarity_by_speaker"),
                        "unplaced": measured.get("unplaced") or []}}


register(JobKind("convert_voice", _validate_voice, _run_voice))


# --- deriving a master picture ---------------------------------------------------


def _picture_plan(root: Path, params: dict[str, Any]):
    from .pictures import plan_picture
    from .project import load_production

    from .providers.qwen_edit import HOURLY_RATE_USD

    endpoint = os.environ.get("RUNPOD_QWEN_ENDPOINT_ID", "")
    # The production's declared price for this endpoint, else the editor's own (not LTX's).
    rate = float(_declared_rates(root).get(endpoint, HOURLY_RATE_USD))
    feedback = params.get("feedback") if isinstance(params.get("feedback"), dict) else None
    plan = plan_picture(root, load_production(root), str(params.get("scene", "")).strip(),
                        str(params.get("shot", "")).strip(), seed=int(params.get("seed") or 1), rate=rate,
                        feedback=feedback)
    return plan, endpoint, rate


def _declared_rates(root: Path) -> dict[str, Any]:
    from .project import _read_yaml

    return _read_yaml(root / "project.yaml").get("generation_rates") or {}


def _validate_picture(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    from . import spend

    plan, endpoint, _ = _picture_plan(root, params)
    if GENERATION_TRANSPORT is None and not (endpoint and os.environ.get("RUNPOD_API_KEY")):
        raise ValidationError("A picture edit needs RUNPOD_API_KEY and RUNPOD_QWEN_ENDPOINT_ID in the environment "
                              "(toast picture --env-file <file> reads them without printing them)")
    spend.check(plan.estimate_usd, f"Picture {plan.shot} of {plan.scene}")
    checked = {"scene": plan.scene, "shot": plan.shot, "seed": plan.seed}
    if isinstance(params.get("feedback"), dict):
        checked["feedback"] = {"reasons": [str(item) for item in params["feedback"].get("reasons") or []],
                               "text": str(params["feedback"].get("text") or "")}
    return checked


def _run_picture(context: JobContext) -> dict[str, Any]:
    """One paid edit: the source repainted with the cast, kept as a new version of the picture."""

    from . import spend
    from .pictures import picture_versions
    from .project import load_production
    from .providers.qwen_edit import QwenEditProvider, edge_score
    from .takes import JOB_SUFFIX, work_directory_for

    root = context.project_root
    plan, endpoint, rate = _picture_plan(root, context.params)
    what = f"Picture {plan.shot} of {plan.scene}"
    spend.check(plan.estimate_usd, what)

    scene_file = next(item["file"] for item in load_production(root)["scenes"] if item["id"] == plan.scene)
    work = work_directory_for(root / scene_file)
    numbers = [int(path.stem.rpartition("-")[2]) for path in picture_versions(work, plan.stem)
               if path.stem != plan.stem]
    name = f"{plan.stem}-{max(numbers, default=0) + 1}.png"
    output = context.staging / name
    context.progress(0.02, "Sending the picture")
    provider = QwenEditProvider(endpoint, transport=_paid_transport(context, endpoint, "Painting"))
    record_path = output.with_name(name + JOB_SUFFIX)
    pending = _remote_record("derive_picture", plan.public_dict(root))
    try:
        settings = provider.edit(source=plan.source, references=[ref["path"] for ref in plan.references],
                                 prompt=plan.prompt, seed=plan.seed, size=plan.size, output=output, label=what,
                                 state_file=pending)
    except BaseException:
        cost = _record_spend(context, pending, rate, what, plan.estimate_usd)
        if context.cancelled():
            pending.unlink(missing_ok=True)
        _settle_remote(pending, None)
        raise
    cost = _record_spend(context, pending, rate, what, plan.estimate_usd)
    _settle_remote(pending, record_path)
    score = edge_score(output, plan.source)
    provenance = {"kind": "picture-derivation", **plan.public_dict(root), "settings": settings,
                  "feedback": context.params.get("feedback"),
                  "edge_score": score, "cost_usd": round(cost, 4), "job_id": context.job_id}
    (context.staging / f"{name}.provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    destination = (work / name).relative_to(root).as_posix()
    files = [{"staged": name, "destination": destination},
             {"staged": record_path.name, "destination": destination + JOB_SUFFIX},
             {"staged": f"{name}.provenance.json", "destination": destination + ".provenance.json"}]
    return {"files": files, "summary": {"scene": plan.scene, "shot": plan.shot, "picture": destination,
                                        "edge_score": score, "cost_usd": round(cost, 4),
                                        "estimate_usd": plan.estimate_usd}}


register(JobKind("derive_picture", _validate_picture, _run_picture))
