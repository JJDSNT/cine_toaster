"""Hosting the assistant beside the control room (ADR 0017, ADR 0018).

`toast serve --assistant` runs three things on this machine, and the page
talks to one origin:

- the runtime (this process) — the control room and every command;
- the assistant, a LangGraph agent over AG-UI, in a thread of this process;
- the Copilot Runtime, one bundled Node file, supervised: restarted if it
  stops. `/api/copilotkit` on the runtime is proxied to it.

Nothing here is needed without `--assistant`; the core never imports the
`agents` extra.
"""

from __future__ import annotations

import http.client
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

BUNDLE = Path(__file__).with_name("web_assets") / "copilot" / "copilot-runtime.mjs"
PROXY_PREFIX = "/api/copilotkit"
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "proxy-authorization",
              "proxy-authenticate", "host", "content-length"}


def unavailable_reason() -> str:
    """Why the assistant cannot run here, or an empty string."""

    try:
        import ag_ui_langgraph  # noqa: F401
        import langgraph  # noqa: F401
    except ImportError:
        return "the agents extra is not installed (make install-agents)"
    if not shutil.which("node"):
        return "Node is not installed (it runs the Copilot Runtime)"
    if not BUNDLE.is_file():
        return "the Copilot Runtime is not built (make ui)"
    from .agents.models import model_from_env

    try:
        model = model_from_env()
    except Exception as error:
        return getattr(error, "message", str(error))
    reason = model.available() if hasattr(model, "available") else ""
    return reason


class AssistantHost:
    def __init__(self, runtime_url: str, agent_port: int, copilot_port: int) -> None:
        self.runtime_url = runtime_url
        self.agent_port = agent_port
        self.copilot_port = copilot_port
        self._stop = threading.Event()
        self._process: subprocess.Popen | None = None
        self.restarts = 0

    def start(self) -> None:
        from .agents.server import serve_in_thread

        serve_in_thread(self.runtime_url, self.agent_port)
        threading.Thread(target=self._supervise, name="copilot-runtime", daemon=True).start()

    def _supervise(self) -> None:
        env = {**os.environ, "COPILOTKIT_TELEMETRY_DISABLED": "true", "DO_NOT_TRACK": "1",
               "CINE_TOASTER_COPILOT_PORT": str(self.copilot_port),
               "CINE_TOASTER_ASSISTANT_URL": f"http://127.0.0.1:{self.agent_port}/"}
        delay = 1.0
        while not self._stop.is_set():
            started = time.monotonic()
            self._process = subprocess.Popen(["node", str(BUNDLE)], env=env, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.PIPE, text=True)
            self._process.wait()
            if self._stop.is_set():
                return
            # A runtime that dies is started again; one that keeps dying at once is
            # started less often, so a broken install does not spin.
            self.restarts += 1
            delay = 1.0 if time.monotonic() - started > 30 else min(delay * 2, 60.0)
            self._stop.wait(delay)

    def stop(self) -> None:
        self._stop.set()
        if self._process and self._process.poll() is None:
            self._process.terminate()


def proxy(handler, port: int) -> None:
    """Forward one request to the Copilot Runtime and stream its answer back as it comes."""

    length = int(handler.headers.get("Content-Length") or 0)
    body = handler.rfile.read(length) if length else None
    headers = {key: value for key, value in handler.headers.items() if key.lower() not in HOP_BY_HOP}
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=600)
    try:
        connection.request(handler.command, handler.path, body=body, headers=headers)
        response = connection.getresponse()
    except OSError:
        handler.send_response(503)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(b'{"error": {"code": "assistant_unavailable", "message": "The assistant is starting or stopped."}}')
        return
    handler.send_response(response.status)
    for key, value in response.getheaders():
        if key.lower() not in HOP_BY_HOP:
            handler.send_header(key, value)
    handler.send_header("Connection", "close")
    handler.end_headers()
    try:
        while True:
            chunk = response.read1(65536)
            if not chunk:
                break
            handler.wfile.write(chunk)
            handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        connection.close()
        handler.close_connection = True
