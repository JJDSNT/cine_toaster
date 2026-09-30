"""The model behind the assistant, behind an adapter (ADR 0017).

- `claude-cli` (the default): the Claude Code CLI with the person's own login.
  `claude -p` runs one turn headless, with no tools, no settings and no session
  kept, and answers in a JSON shape we give it.
- `claude-api`: the Claude API through the official SDK, for use beyond one
  person's machine. Credentials come from the environment as the SDK resolves
  them (`ANTHROPIC_API_KEY`, or an `ant auth login` profile).

Either way the agent decides what to do with the answer; the model only answers.
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


def _closed(schema: dict[str, Any]) -> dict[str, Any]:
    """The schema with every object closed (`additionalProperties: false`), as structured output wants."""

    if not isinstance(schema, dict):
        return schema
    closed = {key: _closed(value) if isinstance(value, dict) else value for key, value in schema.items()}
    if closed.get("type") == "object":
        closed["properties"] = {key: _closed(value) for key, value in (closed.get("properties") or {}).items()}
        closed.setdefault("additionalProperties", False)
    return closed


class ClaudeApi:
    """The Claude API through the official SDK: structured output, refusals handled.

    The model defaults to Claude Opus 5.5 (`CINE_TOASTER_MODEL_ID` overrides it)
    at low effort, since each turn is a short conversational answer
    (`CINE_TOASTER_MODEL_EFFORT` overrides it). If the model declines a turn, the
    API's own fallback serves it; a turn declined by every model is said in the
    chat, not raised.
    """

    name = "claude-api"
    FALLBACK_BETA = "server-side-fallback-2026-07-01"

    def __init__(self, model: str | None = None, effort: str | None = None, client: Any = None) -> None:
        self.model = model or os.environ.get("CINE_TOASTER_MODEL_ID", "claude-opus-5-5")
        self.effort = effort or os.environ.get("CINE_TOASTER_MODEL_EFFORT", "low")
        self.client = client
        self.last: dict[str, Any] = {}

    def available(self) -> str:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return "the anthropic SDK is not installed (make install-agents)"
        return ""

    def ask(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        reason = self.available()
        if reason:
            raise ModelUnavailable(reason)
        import anthropic

        client = self.client or anthropic.Anthropic()
        try:
            response = client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": self.effort,
                               "format": {"type": "json_schema", "schema": _closed(schema)}},
                betas=[self.FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as error:
            raise ModelUnavailable("The Claude API rejected the credentials (ANTHROPIC_API_KEY or `ant auth login`)") from error
        except anthropic.RateLimitError as error:
            raise ModelUnavailable("The Claude API is rate limiting; try again in a moment") from error
        except anthropic.APIStatusError as error:
            raise ModelUnavailable(f"The Claude API answered {error.status_code}: {error.message}") from error
        except anthropic.APIConnectionError as error:
            raise ModelUnavailable("The Claude API is not reachable from here") from error
        if response.stop_reason == "refusal":
            raise ModelUnavailable("The model declined to answer this turn")
        usage = getattr(response, "usage", None)
        self.last = {"model": response.model, "output_tokens": getattr(usage, "output_tokens", 0)}
        text = next((block.text for block in response.content if block.type == "text"), "")
        try:
            return json.loads(text)
        except ValueError as error:
            raise ModelUnavailable("The model's answer was not the expected shape") from error


ADAPTERS = {"claude-cli": ClaudeCli, "claude-api": ClaudeApi}


def model_from_env() -> Model:
    kind = os.environ.get("CINE_TOASTER_MODEL", "claude-cli")
    if kind in ADAPTERS:
        return ADAPTERS[kind]()
    raise ModelUnavailable(f"Unknown model adapter {kind!r}; available: {', '.join(ADAPTERS)}")
