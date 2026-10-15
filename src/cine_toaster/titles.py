"""Titles: a catalog of title effects, chosen like transitions and camera moves (CT-0031).

An item is a manifest (`title_assets/<id>/title.toml`): what it says, when to
use it, its parameters with defaults, and the engine and effect that draw it.
A shot names one:

    title: {id: card, text: SINGULARITY, size: 40, fade: 1.4, reason: the words disappear}

Catalogs layer like the others: built in, `CINE_TOASTER_TITLES_PATH`, then
the production's `titles/`; a later layer replaces an item with the same id.

Every title is drawn by the compositing graph (C6, CT-0077):

- `graph`: text generated in the graph, with curves -- fades, typing, words one
  by one, a slide, a growth, a roll, a lower third, a flicker, a neon sign
  (`compositing/title_graphs.py`);
- `blender`: letters as 3D objects, rendered by Blender (an external program
  run on files, ADR 0011) with a transparent background, and laid by the graph
  (Blender is found on PATH, in `CINE_TOASTER_BLENDER`, or in `~/.local/opt`
  and `~/ferramentas-ext`).

An item whose engine is missing is refused, not replaced by another.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import tempfile
import threading
import tomllib
from pathlib import Path
from typing import Any

from .errors import ValidationError

BUILTIN = Path(__file__).with_name("title_assets")
BLENDER_SCRIPT = BUILTIN / "_blender" / "title.py"
CATEGORIES = ("cards", "reveal", "motion", "lower thirds", "credits", "texture", "3d")
ENGINES = ("graph", "blender")
EFFECTS = {"graph": ("fade", "typewriter", "words", "slide", "grow", "roll", "lower-third", "flicker", "neon",
                     "letters"),
           "blender": ("letters-turn-in", "letters-rise")}
#: Parameters every item has, whatever its own manifest says.
BASE_PARAMS: dict[str, Any] = {
    "text": "", "subtitle": "", "font": "", "size": 40, "color": "#E6E6E6", "position": "centre",
    "spaced": False, "fade_in": 1.0, "fade_out": 1.0, "enter_at": 0.0, "background": "black",
}
POSITIONS = ("centre", "bottom", "top")


# --- the catalog -------------------------------------------------------------------


def _roots(project_root: Path | None) -> list[tuple[str, Path]]:
    roots = [("built-in", BUILTIN)]
    for position, raw in enumerate(filter(None, os.environ.get("CINE_TOASTER_TITLES_PATH", "").split(os.pathsep)), 1):
        roots.append((f"external-{position}", Path(raw).expanduser()))
    if project_root is not None:
        roots.append(("project", Path(project_root).expanduser().resolve() / "titles"))
    return roots


def _load(path: Path, origin: str) -> dict[str, Any]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValidationError(f"Unreadable title {path}: {error}") from error
    render = raw.get("render") or {}
    return {
        "id": str(raw.get("id") or path.parent.name),
        "name": str(raw.get("name") or path.parent.name),
        "category": str(raw.get("category") or "cards"),
        "says": str(raw.get("says") or ""),
        "energy": str(raw.get("energy") or ""),
        "use_when": [str(item) for item in raw.get("use_when") or []],
        "avoid_when": [str(item) for item in raw.get("avoid_when") or []],
        "params": {**BASE_PARAMS, **(raw.get("params") or {})},
        "engine": str(render.get("engine") or "graph"),
        "effect": str(render.get("effect") or "fade"),
        # The primitives it is made of (C6, CT-0077).
        "primitives": [str(op) for op in render.get("primitives") or []],
        "origin": origin,
        "directory": str(path.parent),
    }


def list_titles(project_root: Path | None = None) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for origin, root in _roots(project_root):
        if root.is_dir():
            for manifest in sorted(root.glob("*/title.toml")):
                item = _load(manifest, origin)
                by_id[item["id"]] = item
    order = {name: index for index, name in enumerate(CATEGORIES)}
    return sorted(by_id.values(), key=lambda item: (order.get(item["category"], 99), item["name"]))


def expand(raw: Any, catalog: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    """A shot's `title` with its catalog item's defaults: (title, problem).

    A bare string is the text of a `card`. Keys other than id, text,
    subtitle and reason are parameters.
    """

    if raw in (None, "", {}):
        return None, ""
    declared = {"id": "card", "text": str(raw)} if isinstance(raw, str) else dict(raw)
    item = catalog.get(str(declared.get("id") or "card"))
    if item is None:
        return {**declared, "unknown": True}, (f"names the title {declared.get('id')!r}, which is not in the title "
                                                "catalog")
    params = dict(item["params"])
    for key, value in declared.items():
        if key not in ("id", "reason"):
            params[key] = value
    if params.get("position") not in POSITIONS:
        return None, f"puts its title at {params.get('position')!r}; the positions are {', '.join(POSITIONS)}"
    from .compositing.title_graphs import style_problem

    if style_problem(params.get("style")):
        return None, f"gives its title a style that {style_problem(params.get('style'))}"
    return {"id": item["id"], "text": str(params.get("text") or ""), "params": params, "engine": item["engine"],
            "effect": item["effect"], "reason": str(declared.get("reason") or "")}, ""


# --- engines ------------------------------------------------------------------------


def blender_binary() -> str | None:
    configured = os.environ.get("CINE_TOASTER_BLENDER")
    if configured and Path(configured).expanduser().is_file():
        return str(Path(configured).expanduser())
    found = shutil.which("blender")
    if found:
        return found
    candidates = sorted(glob.glob(str(Path.home() / ".local/opt/blender-*/blender"))
                        + glob.glob(str(Path.home() / "ferramentas-ext/blender-*/blender")))
    return candidates[-1] if candidates else None


def engine_missing(engine: str) -> str:
    """Why an engine cannot run here, or ''."""

    if engine in ("ffmpeg", "graph"):  # the graph reads and writes its frames through FFmpeg
        return "" if shutil.which("ffmpeg") else "FFmpeg is not installed"
    if engine == "blender":
        return "" if blender_binary() else "Blender is not found (install it, or set CINE_TOASTER_BLENDER)"
    return f"the engine {engine!r} is not known"


def font_file(params: dict[str, Any], root: Path | None = None) -> str:
    """The title's font: the production's, else the system's sans."""

    declared = str(params.get("font") or "").strip()
    if declared:
        path = (root / declared) if root and not Path(declared).is_absolute() else Path(declared).expanduser()
        if not path.is_file():
            raise ValidationError(f"The title's font {declared!r} is not there")
        return str(path.resolve())
    try:
        found = subprocess.run(["fc-match", "-f", "%{file}", "sans:bold"], capture_output=True, text=True,
                               timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        found = ""
    if found and Path(found).is_file():
        return found
    for fallback in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if Path(fallback).is_file():
            return fallback
    raise ValidationError("No font for titles: give the title a font (a .ttf in the production)")


def _blender_overlay(title: dict[str, Any], duration: float, width: int, height: int, font: str,
                     work: Path, run) -> Path:
    """Render a Blender title as a transparent PNG sequence; returns its pattern."""

    blender = blender_binary()
    if not blender:
        raise ValidationError(engine_missing("blender"))
    frames = work / "blender"
    frames.mkdir(parents=True, exist_ok=True)
    spec = work / "blender.json"
    spec.write_text(json.dumps({"effect": title["effect"], "params": title["params"], "font": font, "width": width,
                                "height": height, "fps": 24, "frames": max(2, round(duration * 24)),
                                "output": str(frames)}), encoding="utf-8")
    run([blender, "--background", "--factory-startup", "--python", str(BLENDER_SCRIPT), "--", str(spec)])
    return frames / "f_%04d.png"


def _blender_clip(title: dict[str, Any], duration: float, width: int, height: int, font: str, run) -> str:
    """A Blender title's letters as one clip with alpha, rendered once and kept by what they are (CT-0077)."""

    import hashlib

    from .jobs import state_root

    hashed = hashlib.sha256(json.dumps([title["effect"], title["params"], font, duration, width, height],
                                       sort_keys=True, default=str).encode())
    hashed.update(BLENDER_SCRIPT.read_bytes())
    clip = state_root() / "titles" / f"{hashed.hexdigest()[:20]}.mov"
    if not clip.is_file():
        clip.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="title-") as scratch:
            pattern = _blender_overlay(title, duration, width, height, font, Path(scratch), run)
            partial = clip.with_name(f".{clip.name}.part.mov")
            run([shutil.which("ffmpeg") or "ffmpeg", "-v", "error", "-y", "-framerate", "24", "-i", str(pattern),
                 "-t", f"{duration:.3f}", "-c:v", "qtrle", "-pix_fmt", "argb", str(partial)])
            partial.replace(clip)
    return str(clip)


def title_graph(title: dict[str, Any], duration: float, *, width: int = 1280, height: int = 720, fps: int = 24,
                root: Path | None = None, run=None) -> dict[str, Any]:
    """The title as a graph with one port, `picture`, the shot it is laid over: its font resolved, a Blender
    title's letters rendered and kept (CT-0077). One graph for a title alone or inside a shot's graph."""

    from .compositing.title_graphs import graph_for

    run = run or (lambda command: subprocess.run(command, check=True, capture_output=True))
    missing = engine_missing(title["engine"])
    if missing:
        raise ValidationError(f"The title {title['id']!r} needs {title['engine']}: {missing}")
    width, height = width // 2 * 2, height // 2 * 2
    font = font_file(title["params"], root)
    params = {**title["params"], "font": font}
    prepared = ({"_clip": _blender_clip(title, duration, width, height, font, run)}
                if title["engine"] == "blender" else {})
    return graph_for({**title, "params": params, "prepared": prepared}, duration, fps)


def card_picture(title: dict[str, Any], width: int, height: int):
    """The card a title stands on when it has no shot: its background colour, linear, opaque."""

    import numpy as np

    from .compositing.effects import _linear

    colour = str(title["params"].get("background") or "black")
    named = {"black": "#000000", "white": "#FFFFFF"}.get(colour.lower(), "#" + colour.lower().removeprefix("0x").lstrip("#"))
    still = np.zeros((height // 2 * 2, width // 2 * 2, 4), np.float32)
    still[..., :3], still[..., 3] = _linear(named, "#000000"), 1.0
    return still


def render(title: dict[str, Any], duration: float, output: Path, *, width: int = 1280, height: int = 720,
           background: Path | None = None, start: float = 0.0, root: Path | None = None, run=None,
           fps: int = 24) -> Path:
    """Draw the title over a picture (a clip from `start`) or over its background colour; write `output`.

    Drawn by the compositing graph (C6, CT-0077): GL when it can, the reference otherwise; a Blender title's
    letters are rendered by Blender and laid by the graph. `run(command)` runs a process (a job's runner, or
    subprocess by default). The picture's sound, if any, is kept. A shot in a cut draws its title inside its
    own graph instead (`assembly`, one drawing per shot).
    """

    from .compositing.drawing import over_picture

    run = run or (lambda command: subprocess.run(command, check=True, capture_output=True))
    graph = title_graph(title, duration, width=width, height=height, fps=fps, root=root, run=run)
    still = card_picture(title, width, height) if background is None else None
    return over_picture(graph, duration, output, background=background, still=still, start=start,
                        width=width // 2 * 2, height=height // 2 * 2, fps=fps, root=root, run=run)


def preview(item: dict[str, Any], *, text: str = "", root: Path | None = None, at: float = 0.6) -> bytes:
    """One frame of the item over a dark picture, as PNG: drawn by its own engine, not imitated."""

    title, problem = expand({"id": item["id"], **({"text": text} if text else {})}, {item["id"]: item})
    if problem or title is None:
        raise ValidationError(problem or "No title")
    if not title["text"]:
        title["params"]["text"] = title["text"] = item["name"].upper()
    duration = 4.0
    with tempfile.TemporaryDirectory(prefix="title-preview-") as scratch:
        clip = Path(scratch) / "preview.mp4"
        title["params"]["background"] = "0x1a1f22"
        render(title, duration, clip, width=640, height=360, root=root)
        frame = Path(scratch) / "frame.png"
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-ss", f"{duration * at:.2f}", "-i", str(clip),
                        "-frames:v", "1", str(frame)], check=True, capture_output=True)
        return frame.read_bytes()


def cached_preview(item: dict[str, Any], *, text: str = "", root: Path | None = None) -> Path:
    """The preview as a file, drawn once per manifest, text and engine script: Blender takes seconds."""

    import hashlib

    from .jobs import state_root

    hashed = hashlib.sha256()
    for part in (Path(item["directory"]) / "title.toml", BLENDER_SCRIPT, Path(__file__)):
        hashed.update(part.read_bytes() if part.is_file() else b"")
    hashed.update(text.encode())
    path = state_root() / "title-previews" / f"{item['id']}-{hashed.hexdigest()[:16]}.png"
    with _PREVIEW_GUARD:
        lock = _PREVIEW_LOCKS.setdefault(path.name, threading.Lock())
    with lock:  # the same preview asked twice at once is drawn once
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            data = preview(item, text=text, root=root)
            temporary = path.with_name(f".{path.name}.{os.getpid()}-{threading.get_ident()}")
            temporary.write_bytes(data)
            temporary.replace(path)
    return path


_PREVIEW_GUARD = threading.Lock()
_PREVIEW_LOCKS: dict[str, threading.Lock] = {}
