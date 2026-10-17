"""The model behind the assistant, behind an adapter (ADR 0017).

- `claude-cli`: the Claude Code CLI with the person's own login.
  `claude -p` runs one turn headless, with no tools, no settings and no session
  kept, and answers in a JSON shape we give it.
- `claude-api`: the Claude API through the official SDK, for use beyond one
  person's machine. Credentials come from the environment as the SDK resolves
  them (`ANTHROPIC_API_KEY`, or an `ant auth login` profile).
- `codex-cli`: isolated, ephemeral Codex CLI requests with saved CLI login.

Each adapter declares what its transport carries (`capabilities`); all three
carry images inside the request, never as a file tool. What a model is good at
is described by the catalogue (`catalog.py`, ADR 0034), not decided here.

The host supplies an adapter selection or falls back to the current CLI's
environment signal; filmmaking roles do not choose providers. These adapters do
not attach to existing provider sessions (SPEC-0001 remains separate work).
The agent decides what to do with the answer; the model only answers.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Protocol

from ..errors import CineToasterError


class ModelUnavailable(CineToasterError):
    code = "model_unavailable"
    http_status = 503


#: What an adapter's transport can carry. A role declares what it needs (`roles.py`);
#: the adapter declares what it has. Nothing is inferred from a provider's name.
CAPABILITIES = ("structured_output", "vision", "web")


class Model(Protocol):
    name: str
    capabilities: frozenset[str]

    def ask(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


def supports(model: Any, capability: str) -> bool:
    """Whether this model can serve a role that needs `capability`.

    An adapter that declares no capabilities (a test double, a host's own) is
    taken at its methods: images need `ask_images`, everything else `ask`.
    """

    declared = getattr(model, "capabilities", None)
    if capability == "vision" and not callable(getattr(model, "ask_images", None)):
        return False
    return capability in declared if declared is not None else capability != "web"


def _image_bytes(images: list[dict]) -> list[tuple[str, bytes]]:
    """Bounded, typed raster inputs: the same limits whichever adapter carries them."""

    import base64

    if len(images) > 8:
        raise ModelUnavailable("Visual review is limited to eight images")
    found, total = [], 0
    for image in images:
        kind = image.get("mime_type")
        if kind not in ("image/png", "image/jpeg", "image/webp"):
            raise ModelUnavailable("Unsupported visual input format")
        try:
            data = base64.b64decode(image["data"], validate=True)
        except (ValueError, KeyError) as error:
            raise ModelUnavailable("Invalid visual input") from error
        total += len(data)
        if len(data) > 8 * 1024 * 1024 or total > 24 * 1024 * 1024:
            raise ModelUnavailable("Visual input exceeds the bounded review size")
        found.append((kind, data))
    return found


def _image_blocks(images: list[dict]) -> list[dict[str, Any]]:
    import base64

    return [{"type": "image", "source": {"type": "base64", "media_type": kind,
                                         "data": base64.b64encode(data).decode()}}
            for kind, data in _image_bytes(images)]


class ClaudeCli:
    """`claude -p`, the Claude Code CLI, with the person's own login: no API key."""

    name = "claude-cli"
    capabilities = frozenset({"structured_output", "vision"})

    def __init__(self, executable: str | None = None, timeout: float = 180, model: str = "") -> None:
        self.executable = executable or os.environ.get("CINE_TOASTER_MODEL_CLI", "claude")
        self.timeout = timeout
        self.model = model  # empty: whatever the person's Claude Code configuration uses
        self.last: dict[str, Any] = {}

    def available(self) -> str:
        """Why it cannot run here, or an empty string."""

        return "" if shutil.which(self.executable) else f"{self.executable} is not on PATH (install Claude Code)"

    def ask(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return self._ask(system, prompt, schema, [])

    def ask_images(self, system: str, prompt: str, schema: dict[str, Any], images: list[dict]) -> dict[str, Any]:
        """Pictures travel inside the message (stream-json input), as KDP Studio does: shown, never a file tool."""
        return self._ask(system, prompt, schema, images)

    def _ask(self, system: str, prompt: str, schema: dict[str, Any], images: list[dict]) -> dict[str, Any]:
        reason = self.available()
        if reason:
            raise ModelUnavailable(reason)
        command = [self.executable, "-p", "--tools", "", "--no-session-persistence",
                   "--setting-sources", "", "--system-prompt", system, "--json-schema", json.dumps(schema),
                   *(["--model", self.model] if self.model else [])]
        if images:
            command += ["--input-format", "stream-json", "--output-format", "stream-json", "--verbose"]
            sent = json.dumps({"type": "user", "message": {"role": "user", "content": [
                {"type": "text", "text": prompt}, *_image_blocks(images)]}}) + "\n"
        else:
            command += ["--output-format", "json"]
            sent = prompt
        try:
            completed = subprocess.run(command, input=sent, capture_output=True, text=True,
                                       timeout=self.timeout * (2 if images else 1))
        except subprocess.TimeoutExpired as error:
            raise ModelUnavailable(f"The model took longer than {self.timeout:.0f} s") from error
        if completed.returncode:
            raise ModelUnavailable(f"The model CLI failed: {completed.stderr.strip()[:300]}")
        if images:
            events = []
            for line in completed.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
            answer = next((event for event in reversed(events)
                           if isinstance(event, dict) and event.get("type") == "result"), None)
            if answer is None:
                raise ModelUnavailable("The model CLI gave no result")
        else:
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
    capabilities = frozenset({"structured_output", "vision"})
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
        return self._ask(system, prompt, schema, [])

    def ask_images(self, system: str, prompt: str, schema: dict[str, Any], images: list[dict]) -> dict[str, Any]:
        return self._ask(system, prompt, schema, images)

    def _ask(self, system: str, prompt: str, schema: dict[str, Any], images: list[dict]) -> dict[str, Any]:
        reason = self.available()
        if reason:
            raise ModelUnavailable(reason)
        import anthropic

        # Pictures are checked against the bounds before anything is sent.
        content = [{"type": "text", "text": prompt}, *_image_blocks(images)] if images else prompt
        client = self.client or anthropic.Anthropic()
        try:
            response = client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": content}],
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


def _strict(schema: dict[str, Any]) -> dict[str, Any]:
    """Codex structured output requires every object property to be required.

    Preserve optional semantics as nullable fields rather than requiring the
    model to invent values for tools it is not using.
    """

    value = {key: _strict(item) if isinstance(item, dict) else item for key, item in schema.items()}
    if value.get("type") == "object":
        required = set(value.get("required") or [])
        value["properties"] = {
            key: _strict(item) if key in required else {"anyOf": [_strict(item), {"type": "null"}]}
            for key, item in value.get("properties", {}).items()
        }
        value["required"] = list(value["properties"])
        value["additionalProperties"] = False
    return value


class CodexCli:
    """A model adapter, not a second executor or a resumed development session."""

    name = "codex-cli"
    capabilities = frozenset({"structured_output", "vision"})

    def __init__(self, executable: str | None = None, timeout: float = 180, model: str = "") -> None:
        self.executable = executable or os.environ.get("CINE_TOASTER_CODEX_CLI", "codex")
        self.timeout = timeout
        self.model = model  # empty: whatever the person's Codex configuration uses
        self.last: dict[str, Any] = {}

    def available(self) -> str:
        return "" if shutil.which(self.executable) else f"{self.executable} is not on PATH (install Codex CLI)"

    def ask(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return self._ask(system, prompt, schema, [])

    def ask_images(self, system: str, prompt: str, schema: dict[str, Any], images: list[dict]) -> dict[str, Any]:
        """Optional provider capability: initial images, never filesystem tools."""
        return self._ask(system, prompt, schema, images)

    def _ask(self, system: str, prompt: str, schema: dict[str, Any], images: list[dict]) -> dict[str, Any]:
        reason = self.available()
        if reason:
            raise ModelUnavailable(reason)
        with tempfile.TemporaryDirectory(prefix="cine-toaster-model-") as directory:
            folder = Path(directory)
            schema_file = folder / "schema.json"
            answer_file = folder / "answer.json"
            schema_file.write_text(json.dumps(_strict(schema)), encoding="utf-8")
            command = [self.executable, "exec", "--ignore-user-config", "--ignore-rules",
                       "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
                       "--output-schema", str(schema_file), "--output-last-message", str(answer_file),
                       *(["--model", self.model] if self.model else []),
                       "--json", "--color", "never", "-c", "approval_policy=\"never\"",
                       "-c", "web_search=\"disabled\"", "-c", "skills.bundled.enabled=false",
                       "-c", "project_doc_max_bytes=0",
                       "-c", "developer_instructions=" + json.dumps(system)]
            suffixes = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
            for index, (kind, data) in enumerate(_image_bytes(images)):
                path = folder / f"input-{index}{suffixes[kind]}"
                path.write_bytes(data)
                command.extend(["--image", str(path)])
            # No inherited user MCP/tools, development instructions or project cwd.
            # The LangGraph role, not this model subprocess, owns application tools.
            for feature in ("shell_tool", "apps", "plugins", "memories", "multi_agent",
                            "browser_use", "computer_use", "image_generation", "view_image", "hooks"):
                command.extend(["--disable", feature])
            command.extend(["--enable", "skip_host_skill_discovery", "-"])
            try:
                completed = subprocess.run(command, input=prompt, capture_output=True, text=True,
                                           timeout=self.timeout, cwd=folder)
            except subprocess.TimeoutExpired as error:
                raise ModelUnavailable(f"The model took longer than {self.timeout:.0f} s") from error
            except OSError as error:
                raise ModelUnavailable("The Codex CLI could not be started") from error
            if completed.returncode:
                # Provider stderr may contain configuration, paths or secrets.
                raise ModelUnavailable(f"The Codex CLI failed (exit {completed.returncode}); check CLI login and compatibility")
            try:
                answer = json.loads(answer_file.read_text(encoding="utf-8"))
                if not isinstance(answer, dict):
                    raise ValueError("expected an object")
            except (OSError, ValueError) as error:
                raise ModelUnavailable("The Codex CLI did not return the expected structured answer") from error
            self.last = {}
            for line in completed.stdout.splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("type") == "turn.completed":
                    self.last = {"usage": event.get("usage") or {}}
            return answer


ADAPTERS = {"claude-cli": ClaudeCli, "claude-api": ClaudeApi, "codex-cli": CodexCli}


def current_cli_provider() -> str:
    """Best-effort launcher signals, not authentication or provider session binding.

    Never scan installed executables, keys, stored transcripts or unrelated
    processes. Ambiguous inherited signals need an explicit host choice.
    """

    candidates = []
    if os.environ.get("CODEX_THREAD_ID", "").strip():
        candidates.append("codex-cli")
    if os.environ.get("CLAUDECODE") == "1":
        candidates.append("claude-cli")
    if len(candidates) > 1:
        raise ModelUnavailable("Ambiguous current CLI (Codex and Claude); select --agent-provider explicitly")
    return candidates[0] if candidates else ""


def model_from_env(provider: str | None = None) -> Model:
    """Host flag > host environment > current CLI; no installed-provider guess.

    An explicit selection overrides the environment for this host only.
    Absent configuration may use the current CLI, as authorised by the director;
    it is not permission to pick another installed CLI or use an arbitrary key.
    """

    selection = provider if provider is not None else os.environ.get("CINE_TOASTER_MODEL")
    kind = selection.strip() if selection is not None else current_cli_provider()
    if not kind:
        raise ModelUnavailable(
            "No agent provider selected and no current CLI detected. Use --agent-provider ADAPTER or set CINE_TOASTER_MODEL "
            f"explicitly; available: {', '.join(ADAPTERS)}. No existing provider session is attached."
        )
    if kind in ADAPTERS:
        return ADAPTERS[kind]()
    raise ModelUnavailable(f"Unknown model adapter {kind!r}; available: {', '.join(ADAPTERS)}")
