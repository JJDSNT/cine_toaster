"""The model behind the agent, reached through the Claude Code CLI: no API key.

`claude -p` runs one turn headless with the user's own login. No tools, no
settings, no session kept: the agent decides what to do with the answer;
the model only answers, in a JSON shape we give it.
"""

from __future__ import annotations

import json
import os
import subprocess

CLI = os.environ.get("CINE_TOASTER_MODEL_CLI", "claude")


def ask(system: str, prompt: str, schema: dict, timeout: float = 120) -> dict:
    completed = subprocess.run(
        [CLI, "-p", "--output-format", "json", "--tools", "", "--no-session-persistence",
         "--setting-sources", "", "--system-prompt", system, "--json-schema", json.dumps(schema)],
        input=prompt, capture_output=True, text=True, timeout=timeout,
    )
    if completed.returncode:
        raise RuntimeError(f"model CLI failed: {completed.stderr.strip()[:300]}")
    answer = json.loads(completed.stdout)
    usage = answer.get("usage") or {}
    ask.last = {"seconds": answer.get("duration_ms", 0) / 1000,
                "input": usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
                + usage.get("cache_read_input_tokens", 0), "output": usage.get("output_tokens", 0)}
    return answer.get("structured_output") or json.loads(answer.get("result") or "{}")


ask.last = {}
