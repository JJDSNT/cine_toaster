"""Images from Codex's built-in image generation, on the person's ChatGPT subscription (CT-0101).

`codex exec` runs one non-interactive turn in which the agent is told to call
its `image_gen` tool once. The tool saves under
`$CODEX_HOME/generated_images/<thread id>/` and takes no destination, so the
file is found by the thread id the `thread.started` event gives, and copied to
the output. Learned by the probe of 2026-10-16 (CT-0099):

- the prompt goes before `-i`, which takes several files and would swallow it;
- stdin is closed, or `exec` waits on it for more input;
- the model is not reported, and the cost is subscription quota, not dollars:
  provenance says so instead of inventing a price.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from . import ProviderError, ProviderNotConfigured

#: Runs argv in cwd within timeout seconds: (returncode, stdout, stderr). Replaced in tests.
Runner = Callable[[list[str], Path, int], tuple[int, str, str]]

INSTRUCTION = ("Generate exactly one image with your built-in image generation tool, then stop. Do not run shell "
               "commands and do not write, copy or move files. ")
REFERENCES = ("The {count} attached image(s) are references, in the order attached; the description says what "
              "to take from each. ")


def _run(argv: list[str], cwd: Path, timeout: int) -> tuple[int, str, str]:
    try:
        done = subprocess.run(argv, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise ProviderError(f"codex did not finish in {timeout} s") from error
    return done.returncode, done.stdout, done.stderr


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instruction(prompt: str, references: int) -> str:
    return INSTRUCTION + (REFERENCES.format(count=references) if references else "") + "Image: " + " ".join(
        prompt.split())


class CodexImageProvider:
    id = "codex-image"
    #: What the image is made by; Codex does not name the model behind image_gen.
    model = "codex image_gen"

    def __init__(self, binary: str | None = None, *, codex_home: Path | None = None,
                 runner: Runner | None = None) -> None:
        self.binary = binary or os.environ.get("CINE_TOASTER_CODEX") or shutil.which("codex") or ""
        self.codex_home = Path(codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        self.runner = runner or _run

    def version(self) -> str:
        if not self.binary:
            return ""
        code, out, _ = self.runner([self.binary, "--version"], Path.cwd(), 30)
        return out.strip() if code == 0 else ""

    def generate(self, *, prompt: str, references: list[Path], output: Path, label: str = "image",
                 timeout: int = 900) -> dict[str, Any]:
        """One image from a description and reference pictures; returns its provenance."""

        if not self.binary:
            raise ProviderNotConfigured("codex is not installed (npm install -g @openai/codex, then codex login)")
        for reference in references:
            if not reference.is_file():
                raise ProviderError(f"{label}: no reference at {reference}")
        text = instruction(prompt, len(references))
        argv = [self.binary, "exec", "--skip-git-repo-check", "-s", "read-only", "--json", text]
        if references:
            argv += ["-i", *[str(reference) for reference in references]]
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="cine-toaster-codex-") as directory:
            code, out, err = self.runner(argv, Path(directory), timeout)
        seconds = round(time.monotonic() - started, 1)

        thread, usage, messages, failures = "", {}, [], []
        for line in out.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind == "thread.started":
                thread = str(event.get("thread_id") or "")
            elif kind == "turn.completed":
                usage = event.get("usage") or {}
            elif kind in ("turn.failed", "error"):
                failures.append(str(event.get("error") or event.get("message") or event))
            elif kind == "item.completed" and (event.get("item") or {}).get("type") == "agent_message":
                messages.append(str(event["item"].get("text") or ""))
        if code != 0 or failures:
            last = err.strip().splitlines()[-1] if err.strip() else f"exit {code}"
            raise ProviderError(f"{label}: codex failed: {'; '.join(failures) or last}")
        folder = self.codex_home / "generated_images" / thread if thread else None
        made = sorted(folder.glob("*.png"), key=lambda path: path.stat().st_mtime) if folder and folder.is_dir() else []
        if not made:
            said = messages[-1][:300] if messages else "nothing"
            raise ProviderError(f"{label}: codex made no image (thread {thread or 'unknown'}; it said: {said})")

        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ".tmp")
        shutil.copy2(made[-1], temporary)
        os.replace(temporary, output)
        return {
            "provider": self.id,
            "made_with": self.version() or "codex",
            "model": "not reported by codex",
            "thread": thread,
            "codex_file": str(made[-1]),
            "images_made": len(made),
            "instruction": text,
            "references": [{"file": str(reference), "sha256": _sha256(reference)} for reference in references],
            "seconds": seconds,
            "usage": usage,
            "cost": {"kind": "subscription quota", "usd": None},
        }

    # --- as a PictureProvider (ADR 0025) ----------------------------------------------------

    needs_source = False
    cost = "quota"

    def prompt(self, request: str, *, source: bool, references: int) -> str:
        parts = []
        if source:
            parts.append("Image 1 is the composition: keep its camera, framing and where everything is, and "
                         "redraw what is in it.")
        if references:
            first = 2 if source else 1
            parts.append(f"Image{'s' if references > 1 else ''} {first}"
                         + (f" to {first + references - 1}" if references > 1 else "")
                         + " say who each person is: take identity from them, not their composition or background.")
        parts.append(" ".join(request.split()))
        return " ".join(parts)

    def size(self, source: Path | None) -> tuple[int, int] | None:
        return None  # codex chooses; the result's size is recorded

    def estimate_usd(self, rate: float | None = None) -> float:
        return 0.0

    def make(self, *, source: Path | None, references: list[Path], prompt: str, seed: int,
             size: tuple[int, int] | None, output: Path, label: str = "picture",
             state_file: Path | None = None) -> dict[str, Any]:
        made = self.generate(prompt=prompt, references=([source] if source else []) + list(references),
                             output=output, label=label)
        made["seed"] = "not supported by codex"
        return made
