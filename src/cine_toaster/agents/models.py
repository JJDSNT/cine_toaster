"""The model behind the assistant, behind an adapter (ADR 0017).

The first adapter is the Claude Code CLI with the person's own login: `claude -p`
runs one turn headless, with no tools, no settings and no session kept, and
answers in a JSON shape we give it. The agent decides what to do with it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Protocol

from ..errors import CineToasterError


class ModelUnavailable(CineToasterError):
    code = "model_unavailable"
    http_status = 503


class Model(Protocol):
    name: str

    def ask(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


class ClaudeCli:
    """`claude -p`, the Claude Code CLI, with the person's own login: no API key."""

    name = "claude-cli"

    def __init__(self, executable: str | None = None, timeout: float = 180) -> None:
        self.executable = executable or os.environ.get("CINE_TOASTER_MODEL_CLI", "claude")
        self.timeout = timeout
        self.last: dict[str, Any] = {}

    def available(self) -> str:
        """Why it cannot run here, or an empty string."""

        return "" if shutil.which(self.executable) else f"{self.executable} is not on PATH (install Claude Code)"

    def ask(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        reason = self.available()
        if reason:
            raise ModelUnavailable(reason)
        try:
            completed = subprocess.run(
                [self.executable, "-p", "--output-format", "json", "--tools", "", "--no-session-persistence",
                 "--setting-sources", "", "--system-prompt", system, "--json-schema", json.dumps(schema)],
                input=prompt, capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise ModelUnavailable(f"The model took longer than {self.timeout:.0f} s") from error
        if completed.returncode:
            raise ModelUnavailable(f"The model CLI failed: {completed.stderr.strip()[:300]}")
        answer = json.loads(completed.stdout)
        usage = answer.get("usage") or {}
        self.last = {"seconds": answer.get("duration_ms", 0) / 1000, "output_tokens": usage.get("output_tokens", 0)}
        if answer.get("is_error"):
            raise ModelUnavailable(str(answer.get("result") or "The model answered with an error")[:300])
        return answer.get("structured_output") or json.loads(answer.get("result") or "{}")


def model_from_env() -> Model:
    kind = os.environ.get("CINE_TOASTER_MODEL", "claude-cli")
    if kind == "claude-cli":
        return ClaudeCli()
    raise ModelUnavailable(f"Unknown model adapter {kind!r}; available: claude-cli")
