"""What works here, what does not, and the exact line that fixes it.

Someone who has just cloned this repository needs one command that tells the
truth about their machine. The alternative is finding out capability by
capability, at the moment each one fails, which is how a tool earns a
reputation for being broken when it is merely incomplete.

Every missing capability carries its own remedy. A report that says what is
wrong without saying what to type is half a report.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


OK = "ok"
MISSING = "missing"


@dataclass(frozen=True, slots=True)
class Capability:
    """One thing the tool can or cannot do, and what it costs to fix."""

    name: str
    what_it_enables: str
    required: bool
    status: str
    detail: str = ""
    remedy: str = ""
    #: False while Cine Toaster can detect the tool but does not use it yet.
    #: Reporting a capability as working when nothing calls it would be a lie
    #: told by the one command whose whole job is to tell the truth.
    wired: bool = True

    def public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enables": self.what_it_enables,
            "required": self.required,
            "status": self.status,
            "detail": self.detail,
            "remedy": self.remedy,
            "wired": self.wired,
        }


def _module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _binary(name: str) -> str:
    return shutil.which(name) or ""


def _python() -> Capability:
    version = ".".join(str(part) for part in sys.version_info[:3])
    ok = sys.version_info[:2] >= (3, 12)
    return Capability(
        name="Python 3.12+",
        what_it_enables="everything",
        required=True,
        status=OK if ok else MISSING,
        detail=f"running {version}",
        remedy="" if ok else "Install Python 3.12 or newer.",
    )


def _yaml() -> Capability:
    ok = _module("yaml")
    return Capability(
        name="PyYAML",
        what_it_enables="reading a production",
        required=True,
        status=OK if ok else MISSING,
        remedy="" if ok else "uv sync   (or: pip install -e .)",
    )


def _media() -> Capability:
    present = [name for name in ("numpy", "PIL", "cv2") if _module(name)]
    ok = len(present) == 3
    return Capability(
        name="Media libraries",
        what_it_enables="drawing cards, grading, focus, relight",
        required=False,
        status=OK if ok else MISSING,
        detail=f"{len(present)} of 3 present" if not ok else "numpy, pillow, opencv",
        remedy="" if ok else "uv sync --extra media   (or: pip install -e '.[media]')",
    )


def _piper() -> Capability:
    ok = _module("piper")
    return Capability(
        name="Piper narration",
        what_it_enables="speaking a production's lines, offline and free",
        required=False,
        status=OK if ok else MISSING,
        remedy="" if ok else "uv sync --extra audio   (or: pip install -e '.[audio]')",
    )


def _ffmpeg() -> Capability:
    path = _binary("ffmpeg")
    return Capability(
        name="FFmpeg",
        what_it_enables="encoding a render, mixing audio",
        required=False,
        status=OK if path else MISSING,
        detail=path,
        remedy=""
        if path
        else "Linux: sudo apt install ffmpeg | macOS: brew install ffmpeg | "
        "Windows: winget install ffmpeg",
    )


def _ffprobe() -> Capability:
    path = _binary("ffprobe")
    return Capability(
        name="FFprobe",
        what_it_enables="verifying a render is what it claims",
        required=False,
        status=OK if path else MISSING,
        detail=path,
        remedy="" if path else "Ships with FFmpeg; install that.",
    )


def _transitions() -> Capability:
    from .transitions import list_transitions

    try:
        count = len(list_transitions())
    except Exception as error:  # pragma: no cover - a broken catalog is a bug
        return Capability(
            name="Transition catalog",
            what_it_enables="choosing an edit from a shared vocabulary",
            required=True,
            status=MISSING,
            detail=str(error),
            remedy="This ships with the package; reinstall it.",
        )
    return Capability(
        name="Transition catalog",
        what_it_enables="choosing an edit from a shared vocabulary",
        required=True,
        status=OK if count else MISSING,
        detail=f"{count} built-in",
        remedy="" if count else "This ships with the package; reinstall it.",
    )


def _demos() -> Capability:
    from .cli import DEMO_TEMPLATES, demo_template_path

    found = []
    for template_id in DEMO_TEMPLATES:
        try:
            if demo_template_path(template_id).is_dir():
                found.append(template_id)
        except Exception:
            continue
    ok = len(found) == len(DEMO_TEMPLATES)
    return Capability(
        name="Demo productions",
        what_it_enables="seeing a production without having one",
        required=False,
        status=OK if ok else MISSING,
        detail=", ".join(found) or "none found",
        remedy="" if ok else "Run from a source checkout, or reinstall the package.",
    )


def _sox() -> Capability:
    path = _binary("sox")
    return Capability(
        name="SoX",
        what_it_enables="normalising, trimming and shaping the audio of a take",
        required=False,
        status=OK if path else MISSING,
        detail=path,
        remedy=""
        if path
        else "Linux: sudo apt install sox | macOS: brew install sox | "
        "Windows: winget install sox",
        wired=False,
    )


def _blender() -> Capability:
    path = _binary("blender")
    return Capability(
        name="Blender",
        what_it_enables="3D titles, set previsualisation, and compositing passes",
        required=False,
        status=OK if path else MISSING,
        detail=path,
        remedy="" if path else "https://www.blender.org/download/  (4.2 LTS or newer)",
        wired=False,
    )


def _moderngl() -> Capability:
    ok = _module("moderngl")
    return Capability(
        name="ModernGL",
        what_it_enables="running a transition's GLSL shader instead of an FFmpeg stand-in",
        required=False,
        status=OK if ok else MISSING,
        remedy="" if ok else "uv sync --extra gpu   (or: pip install -e '.[gpu]')",
        wired=False,
    )


def _whisper() -> Capability:
    path = _binary("whisper-cli") or _binary("whisper-cpp") or _binary("main")
    ok = bool(path) or _module("faster_whisper")
    return Capability(
        name="Transcription",
        what_it_enables="subtitles, and reading source footage that arrives without a script",
        required=False,
        status=OK if ok else MISSING,
        detail=path,
        remedy=""
        if ok
        else "pip install faster-whisper   (or build whisper.cpp)",
        wired=False,
    )


CHECKS: tuple[Callable[[], Capability], ...] = (
    _python,
    _yaml,
    _transitions,
    _demos,
    _media,
    _piper,
    _ffmpeg,
    _ffprobe,
    # Detected, not yet used. See `report`.
    _sox,
    _blender,
    _moderngl,
    _whisper,
)


def examine() -> list[Capability]:
    """Every capability, in the order someone needs them."""

    return [check() for check in CHECKS]


def report(capabilities: list[Capability] | None = None) -> str:
    """The human-facing report. Leads with what works."""

    capabilities = capabilities if capabilities is not None else examine()
    live = [item for item in capabilities if item.wired]
    planned = [item for item in capabilities if not item.wired]
    working = [item for item in live if item.status == OK]
    missing = [item for item in live if item.status != OK]

    lines = ["", "Cine Toaster", ""]
    for item in working:
        detail = f"  ({item.detail})" if item.detail else ""
        lines.append(f"  ok      {item.name:22} {item.what_it_enables}{detail}")
    for item in missing:
        mark = "BLOCKED" if item.required else "  --   "
        lines.append(f"  {mark} {item.name:22} {item.what_it_enables}")
        if item.remedy:
            lines.append(f"          {item.remedy}")

    if planned:
        lines.append("")
        lines.append("  Studio toolchain — Cine Toaster does not call these yet:")
        for item in planned:
            mark = "found" if item.status == OK else "  --  "
            lines.append(f"  {mark}   {item.name:22} {item.what_it_enables}")
            if item.status != OK and item.remedy:
                lines.append(f"          {item.remedy}")

    blocked_items = [item for item in missing if item.required]
    lines.append("")
    if blocked_items:
        lines.append(f"{len(blocked_items)} required capability missing; the tool will not run.")
    elif missing:
        lines.append(
            f"Ready. {len(missing)} optional capability not installed — "
            "reading, deciding, and checking work without them."
        )
    else:
        lines.append("Ready, with everything installed.")
    lines.append("")
    return "\n".join(lines)


def blocked(capabilities: list[Capability] | None = None) -> bool:
    capabilities = capabilities if capabilities is not None else examine()
    return any(item.required and item.status != OK for item in capabilities)


def project_root_hint() -> Path:
    return Path.cwd()
