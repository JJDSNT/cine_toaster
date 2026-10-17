"""Generation Operations: the role that watches a generation and continues the work (ADR 0034).

When a role starts paid or slow generation the person consented to, and the
job outlives the turn, the role leaves a *wait*: this thread waits for that
job. The waits are operational state (`$XDG_STATE_HOME/cine-toaster/
agent-waits.json`), disposable without losing the film: the work they resume
is rebuilt from the production's records, as KDP Studio's held flows are.

A watcher in the assistant server reads the job through the runtime. When it
ends, it runs one turn on that thread, opened by a Generation Operations
message rather than a person's:

- a job that succeeded hands the turn back to the role that waited, which
  keeps the result and carries on (inspection, review) within its budgets --
  but starts no new generation: nobody is there to consent;
- a job that failed is diagnosed -- its error, the recipe's endpoint health,
  the failure patterns measured for that path -- and the turn ends asking the
  person, since a retry is paid work only they can start.

The role is deterministic: no model is asked. It never creates, scales or
changes an endpoint.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

TERMINAL = ("succeeded", "failed", "cancelled", "interrupted")
#: Job kinds a role may wait on, and the recipe that ran them.
RECIPE_OF = {"generate_reference": "codex-image", "generate_block": "ltx-2-5", "derive_picture": "qwen-image-edit"}


class WaitStore:
    """Which conversation waits for which job. One small file, written atomically."""

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            from ..jobs import state_root
            path = state_root() / "agent-waits.json"
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []  # disposable: a lost file forgets waits, never the film
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False,
                                         prefix=".waits-") as handle:
            json.dump(items, handle, indent=2)
        os.replace(handle.name, self.path)

    def add(self, *, thread: str, project_id: str, job: str, role: str) -> None:
        with self._lock:
            items = [item for item in self._read() if item.get("job") != job]
            items.append({"thread": thread, "project_id": project_id, "job": job, "role": role,
                          "since": time.time()})
            self._write(items)

    def take(self, job: str) -> dict[str, Any] | None:
        """Remove and return the wait for `job`: a finished job continues once."""

        with self._lock:
            items = self._read()
            found = next((item for item in items if item.get("job") == job), None)
            if found:
                self._write([item for item in items if item is not found])
            return found

    def all(self, project_id: str = "") -> list[dict[str, Any]]:
        return [item for item in self._read() if not project_id or item.get("project_id") == project_id]


def resumed_job(state: dict[str, Any]) -> str:
    """The job a Generation Operations continuation names, bound to the message that opened the turn."""

    resume = state.get("resume") or {}
    job = str(resume.get("job") or "") if isinstance(resume, dict) else ""
    last = (state.get("messages") or [None])[-1]
    if not job or len(job) > 80 or not all(c.isalnum() or c in "-_" for c in job):
        return ""
    return job if last is not None and getattr(last, "id", None) == resume.get("message") else ""


def continuation(job: dict[str, Any]) -> dict[str, Any]:
    """The input of the turn a finished job opens: a message from this role, not from a person."""

    message = f"operations-{job['id']}-{uuid.uuid4().hex[:6]}"
    said = (f"Generation Operations: the job {job['id']} ended ({job['state']}). "
            + ("Resuming the work that waited for it." if job["state"] == "succeeded" else "Diagnosing it."))
    return {"messages": [AIMessage(content=said, id=message)], "resume": {"job": job["id"], "message": message}}


def diagnosis(job: dict[str, Any], transport=None) -> str:
    """What failed, what the endpoint shows, and which measured patterns resemble it."""

    from ..providers.recipes import RECIPES, health, known_failures

    recipe_id = (job.get("params") or {}).get("provider") or RECIPE_OF.get(job.get("kind", ""), "")
    error = str(job.get("error") or "no error was recorded")
    lines = [f"O job {job['id']} ({job.get('kind')}) terminou em {job['state']}: {error[:500]}"]
    recipe = RECIPES.get(recipe_id)
    if recipe:
        state = health(recipe_id, transport)
        lines.append(f"Receita {recipe_id}: " + (
            f"{state['warm_workers']} worker(s) aquecido(s), fila {state['jobs'].get('inQueue', 0)}"
            + (f", {state['unhealthy']} com problema" if state["unhealthy"] else "")
            if state["readable"] else f"saúde do endpoint não lida ({state['reason']})"))
        # Crude on purpose: two shared word stems, said as a resemblance, never as the cause.
        stems = _stems(error)
        similar = [item for item in known_failures(recipe)
                   if len(stems & _stems(f"{item['id']} {item['claim']}")) >= 2]
        for item in similar[:3]:
            lines.append(f"Parecido com uma falha medida ({item['id']}): {item['workaround']}")
        if not similar:
            lines.append("Nenhuma falha medida desta receita se parece com este erro.")
    lines.append("Tentar de novo é trabalho pago ou de cota: só recomeço com o seu consentimento.")
    return "\n".join(lines)


_COMMON = {"with", "that", "this", "from", "when", "where", "there", "have", "were", "will", "into", "than"}


def _stems(text: str) -> set[str]:
    words = "".join(c if c.isalnum() else " " for c in text.lower()).split()
    return {word[:4] for word in words if len(word) >= 4 and word not in _COMMON}


def node(runtime: Any, waits: WaitStore | None):
    """The deterministic Generation Operations node of the CoAgent graph."""

    def operations(state: dict[str, Any]) -> dict[str, Any]:
        job_id = state.get("operations_job", "")
        stop = {"completed_turn": state.get("turn", ""), "proposal": {}}
        try:
            job = runtime.job(job_id)
        except Exception as error:
            return {**stop, "messages": [AIMessage(content=f"Não consegui ler o job {job_id}: {error}")],
                    "agent_status": {"role": "generation_operations", "state": "blocked"}}
        if job.get("state") not in TERMINAL:
            if waits is not None and state.get("operations_wait"):
                waits.add(**state["operations_wait"])  # not finished after all: keep waiting
            return {**stop, "messages": [AIMessage(content=f"O job {job_id} ainda está {job.get('state')}.")],
                    "agent_status": {"role": "generation_operations", "state": "waiting_for_job"}}
        role = (state.get("operations_wait") or {}).get("role") or "art_direction"
        if job["state"] == "succeeded" and role == "art_direction":
            return {"active_role": "art_direction", "art_job": job_id, "art_waiting": True,
                    "agent_status": {"role": "art_direction", "state": "working", "detail": "job finished"}}
        return {**stop, "messages": [AIMessage(content=diagnosis(job))],
                "agent_status": {"role": "generation_operations", "state": "needs_direction"}}

    return operations


class Watcher:
    """Reads the waited jobs and opens a continuation turn when one ends. One per assistant server."""

    def __init__(self, graph: Any, runtime: Any, waits: WaitStore, interval: float = 10.0) -> None:
        self.graph, self.runtime, self.waits, self.interval = graph, runtime, waits, interval
        self._stop = threading.Event()

    def tick(self) -> list[str]:
        """One pass: the jobs whose wait was continued."""

        try:
            project_id = self.runtime.production().get("id", "")
        except Exception:
            return []  # the runtime is not reachable now; the waits stay
        continued = []
        for wait in self.waits.all(project_id):
            try:
                job = self.runtime.job(wait["job"])
            except Exception:
                continue
            if job.get("state") not in TERMINAL:
                continue
            config = {"configurable": {"thread_id": wait["thread"]}}
            try:
                if self.graph.get_state(config).next:
                    continue  # the thread is mid-turn or waits for a person: try again next pass
            except Exception:
                pass  # no checkpoint (a restart): the turn is rebuilt from records
            if not self.waits.take(wait["job"]):
                continue
            self.graph.invoke({**continuation(job), "operations_wait": wait}, config)
            continued.append(wait["job"])
        return continued

    def run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.tick()
            except Exception:
                pass  # a failed pass must not end the watcher; the waits remain for the next

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self.run, name="generation-operations", daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop.set()
