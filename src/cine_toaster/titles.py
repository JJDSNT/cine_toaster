"""Titles: a catalog of title effects, chosen like transitions and camera moves (CT-0031).

An item is a manifest (`title_assets/<id>/title.toml`): what it says, when to
use it, its parameters with defaults, and the engine and effect that draw it.
A shot names one:

    title: {id: card, text: SINGULARITY, size: 40, fade: 1.4, reason: the words disappear}

Catalogs layer like the others: built in, `CINE_TOASTER_TITLES_PATH`, then
the production's `titles/`; a later layer replaces an item with the same id.

Engines are external programs run on files, never linked (ADR 0011):

- `ffmpeg`: drawtext effects -- fades, typing, words one by one, a slide, a
  growth, a roll, a lower third, a flicker;
- `blender`: letters as 3D objects, rendered with a transparent background
  and laid over the picture (Blender is found on PATH, in
  `CINE_TOASTER_BLENDER`, or in `~/.local/opt` and `~/ferramentas-ext`).

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
ENGINES = ("ffmpeg", "blender")
EFFECTS = {"ffmpeg": ("fade", "typewriter", "words", "slide", "grow", "roll", "lower-third", "flicker", "neon"),
           "blender": ("letters-turn-in", "letters-rise")}
#: Parameters every item has, whatever its own manifest says.
BASE_PARAMS: dict[str, Any] = {
    "text": "", "subtitle": "", "font": "", "size": 40, "color": "#E6E6E6", "position": "centre",
    "spaced": False, "fade_in": 1.0, "fade_out": 1.0, "enter_at": 0.0, "background": "black",
}
POSITIONS = ("centre", "bottom", "top")
#: The frame sizes are those of 720p; sizes scale with the picture's height.
REFERENCE_HEIGHT = 720


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
        "engine": str(render.get("engine") or "ffmpeg"),
        "effect": str(render.get("effect") or "fade"),
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

    if engine == "ffmpeg":
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


def _escape(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _spaced(text: str) -> str:
    """Letters apart by a thin space, words by two em spaces: tracked-out capitals that do not run together."""

    return "  ".join(" ".join(word) for word in text.split(" "))


def _alpha(params: dict[str, Any], duration: float) -> str:
    enter, fade_in, fade_out = float(params["enter_at"]), max(0.001, float(params["fade_in"])), max(0.001, float(params["fade_out"]))
    hold = max(enter + fade_in, duration - fade_out)
    return (f"if(lt(t,{enter:.3f}),0,if(lt(t,{enter + fade_in:.3f}),(t-{enter:.3f})/{fade_in:.3f},"
            f"if(lt(t,{hold:.3f}),1,max(0,({duration:.3f}-t)/{fade_out:.3f}))))")


def _colour(value: str) -> str:
    value = str(value or "#E6E6E6").strip()
    return "0x" + value[1:] if value.startswith("#") else value


def ffmpeg_filters(title: dict[str, Any], duration: float, width: int, height: int, font: str,
                   work: Path) -> str:
    """The drawtext chain that draws a title over a picture of this size and duration.

    Text goes through files (`textfile`), so quotes, colons and accents in a
    title never need escaping.
    """

    params, effect = title["params"], title["effect"]
    scale = height / REFERENCE_HEIGHT
    size = float(params["size"]) * scale
    text = str(params.get("text") or "")
    if params.get("spaced"):
        text = _spaced(text)
    y = {"centre": "(h-text_h)/2", "bottom": f"h-text_h-{46 * scale:.0f}", "top": "h*0.16"}[params["position"]]
    base = f"fontfile='{_escape(font)}':fontcolor={_colour(params['color'])}:x=(w-text_w)/2"
    alpha = _alpha(params, duration)
    work.mkdir(parents=True, exist_ok=True)
    counter = iter(range(10_000))

    def text_file(value: str) -> str:
        path = work / f"title-{next(counter)}.txt"
        path.write_text(value, encoding="utf-8")
        return _escape(str(path))

    def draw(value: str, extra: str) -> str:
        return f"drawtext={base}:textfile='{text_file(value)}':{extra}"

    enter = float(params["enter_at"])
    span = max(0.2, duration - enter - float(params["fade_out"]))
    if effect == "fade":
        filters = [draw(text, f"fontsize={size:.1f}:y={y}:alpha='{alpha}'")]
        if params.get("subtitle"):
            filters.append(draw(str(params["subtitle"]), f"fontsize={size * 0.45:.1f}:y={y}+{size * 1.6:.0f}:alpha='{alpha}'"))
    elif effect == "typewriter":
        # One drawtext per prefix, each shown until the next letter arrives.
        typing = float(params.get("typing_seconds") or min(span * 0.6, 0.08 * len(text) + 0.4))
        step = typing / max(1, len(text))
        filters = []
        for index in range(1, len(text) + 1):
            start = enter + (index - 1) * step
            end = enter + index * step if index < len(text) else duration
            fade = f"max(0,({duration:.3f}-t)/{max(0.001, float(params['fade_out'])):.3f})" if index == len(text) else "1"
            filters.append(draw(text[:index], f"fontsize={size:.1f}:y={y}:alpha='min(1,{fade})':"
                                              f"enable='between(t,{start:.3f},{end:.3f})'"))
    elif effect == "words":
        words = str(params.get("text") or "").split()
        step = span * 0.6 / max(1, len(words))
        filters = []
        for index in range(1, len(words) + 1):
            start = enter + (index - 1) * step
            end = enter + index * step if index < len(words) else duration
            value = " ".join(words[:index])
            filters.append(draw(_spaced(value) if params.get("spaced") else value,
                                f"fontsize={size:.1f}:y={y}:alpha='min(1,max(0,({duration:.3f}-t)/{max(0.001, float(params['fade_out'])):.3f}))':"
                                f"enable='between(t,{start:.3f},{end:.3f})'"))
    elif effect == "slide":
        travel = 60 * scale
        rise = f"{travel:.0f}*max(0,1-(t-{enter:.3f})/{max(0.001, float(params['fade_in'])):.3f})"
        filters = [draw(text, f"fontsize={size:.1f}:y='{y}+{rise}':alpha='{alpha}'")]
    elif effect == "grow":
        grow = f"{size:.1f}*(0.6+0.4*min(1,max(0,(t-{enter:.3f})/{span:.3f})))"
        filters = [draw(text, f"fontsize='{grow}':y=(h-text_h)/2:alpha='{alpha}'")]
    elif effect == "roll":
        lines = str(params.get("text") or "").replace("\\n", "\n")
        filters = [f"drawtext={base}:textfile='{text_file(lines)}':fontsize={size:.1f}:line_spacing={size * 0.6:.0f}:"
                   f"y=h-(h+text_h)*(t-{enter:.3f})/{max(0.5, duration - enter):.3f}"]
    elif effect == "lower-third":
        bar_y = f"h-{150 * scale:.0f}"  # drawtext's h is the frame's; drawbox's is the box's, hence ih below
        slide = f"w*max(0,1-(t-{enter:.3f})/{max(0.001, float(params['fade_in'])):.3f})"
        bar = (f"drawbox=x=0:y=i{bar_y}:w=iw*0.42:h={92 * scale:.0f}:color={_colour(params.get('bar_color') or '#101315')}@0.75:t=fill:"
               f"enable='between(t,{enter:.3f},{duration:.3f})'")
        filters = [bar,
                   f"drawtext={base.replace('x=(w-text_w)/2', f"x='{40 * scale:.0f}-{slide}'")}:textfile='{text_file(text)}':"
                   f"fontsize={size:.1f}:y={bar_y}+{14 * scale:.0f}:alpha='{alpha}'"]
        if params.get("subtitle"):
            filters.append(f"drawtext={base.replace('x=(w-text_w)/2', f"x='{40 * scale:.0f}-{slide}'")}:"
                           f"textfile='{text_file(str(params['subtitle']))}':fontsize={size * 0.55:.1f}:"
                           f"fontcolor={_colour(params.get('subtitle_color') or '#9AA3A8')}:y={bar_y}+{56 * scale:.0f}:alpha='{alpha}'")
    elif effect == "flicker":
        flicker = f"({alpha})*(0.55+0.45*gt(random(0),0.25))"
        filters = [draw(text, f"fontsize={size:.1f}:y={y}:alpha='{flicker}'")]
    else:
        raise ValidationError(f"The title effect {effect!r} is not one FFmpeg draws",
                              effects=list(EFFECTS["ffmpeg"]))
    return ",".join(filters)


def _neon_graph(picture: str, title: dict[str, Any], duration: float, width: int, height: int, fps: int, font: str,
                work: Path, root: Path | None = None) -> str:
    """A neon sign: tubes of light over the picture, lighting it, striking with a stutter.

    Each line of the sign (the title, and `line2` if given, each with its
    own font, colour and size) is drawn as a tube -- a hollow stroke with a
    pale core line inside when `tube` is on, solid letters otherwise --
    over two halos and a wide spill of its colour. The halos and the spill
    are *added* to the picture, so a wall behind the sign is lit by it. All
    layers share one deterministic flicker (sines of time), so they blink
    together: a tube striking, then a faint buzz.
    """

    params = title["params"]
    scale = height / REFERENCE_HEIGHT
    work.mkdir(parents=True, exist_ok=True)
    enter, ignite = float(params["enter_at"]), max(0.05, float(params.get("ignite", 0.9)))
    fade_out = max(0.001, float(params["fade_out"]))
    # geq names time T; inside its quoted expressions commas need no escaping.
    flicker = "gt(sin(T*97)*sin(T*61+1.3),-0.2)"
    buzz = "(0.88+0.12*gt(sin(T*53)*sin(T*29+0.7),0.55))"
    lit = (f"if(lt(T,{enter:.3f}),0,if(lt(T,{enter + ignite:.3f}),{flicker},{buzz}))"
           f"*min(1,max(0,({duration:.3f}-T)/{fade_out:.3f}))")
    glow = float(params.get("glow", 1.0))
    tube = bool(params.get("tube", False))
    lines = [{"text": str(params.get("text") or ""), "font": font, "color": params.get("color") or "#FF2E9A",
              "size": float(params["size"]), "y": params.get("y")}]
    if params.get("line2"):
        lines.append({"text": str(params["line2"]),
                      "font": font_file({"font": params.get("line2_font") or ""}, root) if params.get("line2_font") else font,
                      "color": params.get("line2_color") or "#FF2E9A", "size": float(params.get("line2_size") or params["size"]),
                      "y": params.get("line2_y")})
    if len(lines) == 2:  # two lines stacked about the centre unless placed
        lines[0]["y"] = lines[0]["y"] if lines[0]["y"] is not None else 0.38
        lines[1]["y"] = lines[1]["y"] if lines[1]["y"] is not None else 0.66
    core = _colour(params.get("core_color") or "#FFF6FB")
    steps, halos, cores = [], [], []
    for index, line in enumerate(lines):
        text = _spaced(line["text"]) if params.get("spaced") and index == 0 else line["text"]
        path = work / f"neon-{index}.txt"
        path.write_text(text, encoding="utf-8")
        size = line["size"] * scale
        if line["y"] is not None:
            y = f"h*{float(line['y']):.3f}-text_h/2"
        else:
            y = {"centre": "(h-text_h)/2", "bottom": f"h-text_h-{46 * scale:.0f}", "top": "h*0.16"}[params["position"]]
        colour = _colour(line["color"])
        stroke = max(2, round(size * 0.07))  # the tube's thickness, from the letter size

        def letters(fill: str, border: int, border_colour: str) -> str:
            return (f"drawtext=fontfile='{_escape(line['font'])}':textfile='{_escape(str(path))}':fontsize={size:.1f}:"
                    f"fontcolor={fill}:borderw={border}:bordercolor={border_colour}:x=(w-text_w)/2:y={y}")

        # A tube is a hollow stroke; otherwise the letters are filled.
        shape = letters(f"{colour}@0", stroke, colour) if tube else letters(colour, max(1, stroke // 2), colour)
        on_black = f"color=c=black:s={width}x{height}:r={fps}:d={duration:.3f}"
        for name, sigma, gain in ((f"spill{index}", 90, 1.1), (f"far{index}", 20, 1.2), (f"near{index}", 6, 1.4)):
            steps.append(f"{on_black},{shape},gblur=sigma={max(1, round(sigma * scale * glow))},format=gbrp,"
                         f"geq=r='min(255,r(X,Y)*{gain * glow:.2f}*({lit}))':g='min(255,g(X,Y)*{gain * glow:.2f}*({lit}))':"
                         f"b='min(255,b(X,Y)*{gain * glow:.2f}*({lit}))'[{name}]")
            halos.append(name)
        # The tube itself: its colour, and a pale core line along its middle.
        inner = letters(f"{core}@0", max(1, stroke // 3), core) if tube else letters(core, 0, core)
        steps.append(f"color=c=black@0.0:s={width}x{height}:r={fps}:d={duration:.3f},format=rgba,{shape},{inner},"
                     f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*({lit})'[tube{index}]")
        cores.append(f"tube{index}")
    graph = steps + [f"{picture},format=gbrp[lit0]"]
    current = "lit0"
    for index, name in enumerate(halos, 1):  # light adds up: the wall behind is lit
        graph.append(f"[{current}][{name}]blend=all_mode=addition[lit{index}]")
        current = f"lit{index}"
    graph.append(f"[{current}]format=rgba[withlight]")
    current = "withlight"
    for index, name in enumerate(cores):
        graph.append(f"[{current}][{name}]overlay=format=auto[signed{index}]")
        current = f"signed{index}"
    graph.append(f"[{current}]format=yuv420p[v]")
    return ";".join(graph)


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


def render(title: dict[str, Any], duration: float, output: Path, *, width: int = 1280, height: int = 720,
           background: Path | None = None, start: float = 0.0, root: Path | None = None, run=None,
           fps: int = 24) -> Path:
    """Draw the title over a picture (a clip from `start`) or over its background colour; write `output`.

    `run(command)` runs a process (a job's runner, or subprocess by default).
    The picture's sound, if any, is kept.
    """

    run = run or (lambda command: subprocess.run(command, check=True, capture_output=True))
    missing = engine_missing(title["engine"])
    if missing:
        raise ValidationError(f"The title {title['id']!r} needs {title['engine']}: {missing}")
    ffmpeg = shutil.which("ffmpeg")
    font = font_file(title["params"], root)
    with tempfile.TemporaryDirectory(prefix="title-") as scratch:
        work = Path(scratch)
        size = f"{width // 2 * 2}:{height // 2 * 2}"
        if background is not None:
            inputs = ["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(background)]
            picture = f"[0:v]scale={size}:force_original_aspect_ratio=decrease,pad={size}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p"
            sound = ["-map", "0:a?"]
        else:
            colour = str(title["params"].get("background") or "black")
            inputs = ["-f", "lavfi", "-i", f"color=c={colour}:s={width // 2 * 2}x{height // 2 * 2}:r={fps}:d={duration:.3f}"]
            picture = "[0:v]format=yuv420p"
            sound = []
        if title["engine"] == "ffmpeg" and title["effect"] == "neon":
            graph = _neon_graph(picture, title, duration, width // 2 * 2, height // 2 * 2, fps, font, work, root)
        elif title["engine"] == "ffmpeg":
            graph = f"{picture},{ffmpeg_filters(title, duration, width, height, font, work)}[v]"
        else:
            pattern = _blender_overlay(title, duration, width, height, font, work, run)
            inputs += ["-framerate", str(fps), "-i", str(pattern)]
            graph = f"{picture}[base];[base][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
        output.parent.mkdir(parents=True, exist_ok=True)
        run([ffmpeg, "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[v]", *sound,
             "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac",
             str(output)])
    return output


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
