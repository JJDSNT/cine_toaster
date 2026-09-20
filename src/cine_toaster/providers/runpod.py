from __future__ import annotations

import copy
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

from . import ProviderError, ProviderNotConfigured


RUN_BASE = "https://api.runpod.ai/v2"
TERMINAL_FAILURES = ("FAILED", "CANCELLED", "TIMED_OUT")
RETRIABLE_STATUS = {429, 500, 502, 503, 504}
POLL_SECONDS = 5
REQUEST_TIMEOUT = 300
MAX_TRANSPORT_ATTEMPTS = 5

# Only the data plane lives here: submit a job, wait, take the result. Creating
# pods, volumes and endpoints is infrastructure work that runpodctl and the
# Runpod MCP already do, and a film tool has no business duplicating it.

Transport = Callable[[str, dict[str, Any] | None], dict[str, Any]]


def load_credentials(env_file: Path | None = None) -> None:
    """Read `.env` into the environment without ever printing a value.

    A token was once exposed in a tool result on this production. Nothing here
    logs or returns a credential; a caller gets a missing-key error instead of a
    value it might echo.
    """

    if env_file is None or not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _api_key() -> str:
    key = os.environ.get("RUNPOD_API_KEY", "").strip()
    if not key:
        raise ProviderNotConfigured("RUNPOD_API_KEY is not set")
    return key


def request(path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """One call against the serverless API. POST when there is a body."""

    payload = json.dumps(body).encode() if body is not None else None
    http = urllib.request.Request(
        f"{RUN_BASE}{path}", data=payload, method="POST" if payload else "GET"
    )
    http.add_header("Authorization", f"Bearer {_api_key()}")
    http.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(http, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read())


def _write_atomically(path: Path, state: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _unique_output_prefix(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Give this job its own output prefix.

    Workers share one output directory on the network volume, and two workers'
    counters can collide. Without a per-job suffix, one clip silently overwrites
    another.
    """

    payload = copy.deepcopy(payload)
    suffix = uuid.uuid4().hex
    for node in payload.get("workflow", {}).values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if isinstance(inputs, dict) and isinstance(inputs.get("filename_prefix"), str):
            inputs["filename_prefix"] += "-" + suffix
    return payload, suffix


def run_job(
    endpoint_id: str,
    payload: dict[str, Any],
    *,
    state_file: Path,
    label: str = "job",
    transport: Transport | None = None,
    poll_seconds: float = POLL_SECONDS,
    on_progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Submit one job and wait, surviving an interrupted session.

    The state file is the point. Generation is slow and paid for; a lost
    connection must not resubmit work already queued. Before sending anything
    the request is recorded with a digest of itself, so resuming can tell "the
    same request, still running" from "a different request that needs sending",
    and refuse the ambiguous case rather than spend money guessing.
    """

    if not endpoint_id:
        raise ProviderNotConfigured("No endpoint id was given for this provider")
    send = transport or request

    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    state: dict[str, Any] = {}
    if state_file.is_file():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}

    if state and state.get("status") not in TERMINAL_FAILURES:
        if state.get("sha256") != digest or state.get("endpoint") != endpoint_id:
            raise ProviderError(
                f"{state_file} records a different pending request. Check the queue "
                "before resending, so paid work is not duplicated.",
                state_file=str(state_file),
            )
        if not state.get("id"):
            raise ProviderError(
                f"{state_file} records a submission with no confirmed id. Check the "
                "queue before resending.",
                state_file=str(state_file),
            )
    else:
        state = {"endpoint": endpoint_id, "sha256": digest, "status": "SUBMITTING"}
        payload, suffix = _unique_output_prefix(payload)
        state["output_suffix"] = suffix
        state_file.parent.mkdir(parents=True, exist_ok=True)
        _write_atomically(state_file, state)
        response = send(f"/{endpoint_id}/run", {"input": payload})
        state.update(id=response["id"], status=response.get("status", "IN_QUEUE"))
        _write_atomically(state_file, state)

    job_id = state["id"]
    while True:
        status = _poll(send, endpoint_id, job_id, state, state_file)
        state.update(
            {key: status[key] for key in ("status", "delayTime", "executionTime", "workerId") if key in status}
        )
        _write_atomically(state_file, state)
        if on_progress is not None:
            on_progress(label, dict(state))
        if status.get("status") in ("COMPLETED", *TERMINAL_FAILURES):
            break
        time.sleep(poll_seconds)

    output = status.get("output")
    failed = status.get("status") != "COMPLETED" or (
        isinstance(output, dict) and output.get("error")
    )
    if failed:
        state["status"] = "FAILED"
        _write_atomically(state_file, state)
        detail = output.get("error") if isinstance(output, dict) else None
        raise ProviderError(
            f"{label}: {status.get('error') or detail or status.get('status')}",
            job_id=job_id,
            endpoint=endpoint_id,
        )
    return output if isinstance(output, dict) else {}


def _poll(
    send: Transport,
    endpoint_id: str,
    job_id: str,
    state: dict[str, Any],
    state_file: Path,
) -> dict[str, Any]:
    for attempt in range(MAX_TRANSPORT_ATTEMPTS):
        try:
            return send(f"/{endpoint_id}/status/{job_id}", None)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                # The job left the queue: the endpoint was drained or
                # reconfigured after we recorded it. Terminal, so the next
                # attempt is free to resubmit.
                state["status"] = "FAILED"
                _write_atomically(state_file, state)
                raise ProviderError(
                    f"Job {job_id} is no longer in the queue (404)", job_id=job_id
                ) from error
            if error.code not in RETRIABLE_STATUS or attempt == MAX_TRANSPORT_ATTEMPTS - 1:
                raise ProviderError(f"Job {job_id}: HTTP {error.code}", job_id=job_id) from error
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt == MAX_TRANSPORT_ATTEMPTS - 1:
                raise ProviderError(f"Job {job_id}: {error}", job_id=job_id) from error
        time.sleep(2**attempt)
    raise ProviderError(f"Job {job_id}: exhausted transport attempts", job_id=job_id)


def cost_usd(status: dict[str, Any], hourly_rate: float) -> float:
    """What the job actually cost, from the time the platform reports."""

    seconds = (status.get("delayTime", 0) + status.get("executionTime", 0)) / 1000
    return seconds * hourly_rate / 3600
