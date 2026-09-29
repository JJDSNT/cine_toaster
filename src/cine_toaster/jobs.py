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


def _run_assemble(context: JobContext) -> dict[str, Any]:
    from .assembly import plan_scene, render
    from .project import load_scene

    scene = load_scene(context.project_root, context.params["scene"])
    plan = plan_scene(context.project_root, scene)
    context.progress(0.01, f"{len(plan.segments)} shots")
    output = context.staging / "assembly.mp4"
    render(context.project_root, plan, output, context.staging / "work", context.run_process)
    shutil.rmtree(context.staging / "work", ignore_errors=True)
    scene_id, version = context.params["scene"], context.params["version"]
    return {
        "files": [{"staged": "assembly.mp4", "destination": f"renders/assemblies/{scene_id}/{version}.mp4"}],
        "summary": {"segments": [asdict(segment) for segment in plan.segments], "notes": plan.notes,
                    "duration_seconds": plan.duration, "takes": plan.takes},
    }


def _adopted_assemble(job: dict[str, Any], placed: list[str]) -> None:
    """An adopted assembly is a new version of the scene, with the takes it used."""

    from .commands import Actor, record_assembly

    root = Path(job["project_root"])
    summary = job["result"]["summary"]
    media = Path(placed[0]).resolve().relative_to(root.resolve()).as_posix()
    notes = "; ".join(summary["notes"])
    record_assembly(
        root,
        scene_id=job["params"]["scene"],
        assembly_id=job["params"]["version"],
        actor=Actor(id="assembly-job", kind="system"),
        media=media,
        summary=(job["params"].get("summary") or f"Assembled from the selected takes (job {job['id']})")
        + (f". Not rendered: {notes}" if notes else ""),
        duration_seconds=summary["duration_seconds"],
        takes=summary["takes"],
    )


register(JobKind("assemble", _validate_assemble, _run_assemble, _adopted_assemble))

