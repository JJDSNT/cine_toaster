"""Visual effects: a catalog of effects, chosen like titles and transitions (CT-0031).

Two kinds of item, one catalog (`vfx_assets/<id>/effect.toml`, layered:
built in, `CINE_TOASTER_VFX_PATH`, the production's `vfx/`):

- **procedural** effects FFmpeg draws on the picture itself: film grain, a
  vignette, a light leak, chromatic aberration, a glitch, a camera shake, a
  flash, a defocus, old film;
- **element** effects that composite a stock element over the picture: fire,
  smoke, sparks, an explosion, a muzzle flash. Elements come from a
  library of the production's own (`vfx_elements/<id>/element.toml`, or
  `CINE_TOASTER_VFX_ELEMENTS_PATH`), in the forms stock libraries deliver
  them: with alpha (ProRes 4444, PNG sequences), on black (blended with
  `screen` or `add`), or on green (keyed). Nothing is downloaded or
  bundled: the person brings the packs they are licensed for, and each
  element records where it came from.

A shot lists its effects in order, before its title:

    effects: [{id: film-grain, strength: 0.4}, {id: fire-over, element: fire-01, x: 0.6, scale: 0.5}]
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from .errors import ValidationError

BUILTIN = Path(__file__).with_name("vfx_assets")
CATEGORIES = ("frame", "texture", "lens", "light", "motion", "glitch", "particles", "weather", "electricity", "destruction",
              "liquids", "holograms", "elements")
EFFECTS = ("mirror", "crop", "fade-out", "grain", "vignette", "light-leak", "aberration", "glitch", "shake", "flash", "defocus", "old-film",
           "element", "sparks-burst", "disintegrate", "look", "ofx", "hologram", "fog", "rain", "snow", "lightning",
           "shatter", "melt", "liquid-splash")
ENGINES = ("graph", "ffmpeg", "blender", "ofx")
#: OpenFX plugins run in Natron, an OFX host driven headless (vfx_assets/_natron/chain.py).
NATRON_CHAIN_SCRIPT = BUILTIN / "_natron" / "chain.py"
#: Effects Blender renders as an element on the fly (vfx_assets/_blender/element.py).
BLENDER_EFFECTS = ("sparks-burst", "disintegrate", "rain", "snow", "lightning", "shatter", "melt", "liquid-splash")
BLENDER_ELEMENT_SCRIPT = BUILTIN / "_blender" / "element.py"
VIDEO_SUFFIXES = (".mp4", ".mov", ".webm", ".mkv", ".avi")
BLENDS = ("screen", "add", "alpha", "key")
ELEMENT_CATEGORIES = ("fire", "smoke", "sparks", "explosion", "muzzle-flash", "dust", "debris", "water", "weather",
                      "light", "other")


# --- catalogs --------------------------------------------------------------------------


def _layers(builtin: Path | None, variable: str, project_root: Path | None, folder: str) -> list[tuple[str, Path]]:
    roots = [("built-in", builtin)] if builtin else []
    for position, raw in enumerate(filter(None, os.environ.get(variable, "").split(os.pathsep)), 1):
        roots.append((f"external-{position}", Path(raw).expanduser()))
    if project_root is not None:
        roots.append(("project", Path(project_root).expanduser().resolve() / folder))
    return roots


def _toml(path: Path, what: str) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValidationError(f"Unreadable {what} {path}: {error}") from error


def list_effects(project_root: Path | None = None) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for origin, root in _layers(BUILTIN, "CINE_TOASTER_VFX_PATH", project_root, "vfx"):
        for manifest in sorted(root.glob("*/effect.toml")) if root.is_dir() else []:
            raw = _toml(manifest, "effect")
            render = raw.get("render") or {}
            item = {
                "id": str(raw.get("id") or manifest.parent.name), "name": str(raw.get("name") or manifest.parent.name),
                "category": str(raw.get("category") or "texture"), "says": str(raw.get("says") or ""),
                "energy": str(raw.get("energy") or ""),
                "use_when": [str(item) for item in raw.get("use_when") or []],
                "avoid_when": [str(item) for item in raw.get("avoid_when") or []],
                "params": dict(raw.get("params") or {}), "effect": str(render.get("effect") or "grain"),
                "engine": str(render.get("engine") or "ffmpeg"),
                # The primitives it is made of, when the compositing graph draws it (C6, CT-0077).
                "primitives": [str(op) for op in render.get("primitives") or []],
                "plugin": str(render.get("plugin") or ""),
                "element_category": str(render.get("element_category") or ""), "origin": origin,
                "directory": str(manifest.parent),
            }
            by_id[item["id"]] = item
    order = {name: index for index, name in enumerate(CATEGORIES)}
    return sorted(by_id.values(), key=lambda item: (order.get(item["category"], 99), item["name"]))


def list_elements(project_root: Path | None = None) -> list[dict[str, Any]]:
    """The stock elements the production has brought, by id: file, category, blend, source."""

    by_id: dict[str, dict[str, Any]] = {}
    for origin, root in _layers(None, "CINE_TOASTER_VFX_ELEMENTS_PATH", project_root, "vfx_elements"):
        for manifest in sorted(root.glob("*/element.toml")) if root.is_dir() else []:
            raw = _toml(manifest, "element")
            folder = manifest.parent
            file = str((folder / str(raw.get("file") or "")).resolve()) if raw.get("file") else ""
            project = str((folder / str(raw["project"])).resolve()) if raw.get("project") else ""
            volume = str((folder / str(raw["volume"])).resolve()) if raw.get("volume") else ""
            usd = str((folder / str(raw["usd"])).resolve()) if raw.get("usd") else ""
            splat = str((folder / str(raw["splat"])).resolve()) if raw.get("splat") else ""
            alembic = str((folder / str(raw["alembic"])).resolve()) if raw.get("alembic") else ""
            matte = str((folder / str(raw["matte"])).resolve()) if raw.get("matte") else ""
            element = {
                "id": str(raw.get("id") or folder.name), "label": str(raw.get("label") or folder.name),
                "category": str(raw.get("category") or "other"), "blend": str(raw.get("blend") or "screen"),
                "key_color": str(raw.get("key_color") or "0x00FF00"), "file": file, "matte": matte,
                "project": project, "volume": volume, "usd": usd, "splat": splat, "alembic": alembic,
                "frames": int(raw.get("frames") or 0),
                # How the renderer shades it (a volume's density, fire, spin...), overridable per shot.
                "params": dict(raw.get("params") or {}),
                # Scene-linear EXR by default; display-encoded otherwise. `view` picks the OCIO view.
                "colorspace": str(raw.get("colorspace") or ""), "view": str(raw.get("view") or ""),
                "source": str(raw.get("source") or ""), "license": str(raw.get("license") or ""),
                "loop": bool(raw.get("loop")), "origin": origin,
            }
            element["format"] = _format(element)
            element["exists"] = _exists(element)
            by_id[element["id"]] = element
    return sorted(by_id.values(), key=lambda item: (item["category"], item["id"]))


def _format(element: dict[str, Any]) -> str:
    """How the element is delivered: video, png or exr sequence, or a Blender project to render."""

    if element["project"]:
        return "blender-project"
    if element.get("volume"):
        return "openvdb"
    if element.get("usd"):
        return "openusd"
    if element.get("splat"):
        return "gaussian-splat"
    if element.get("alembic"):
        return "alembic"
    name = element["file"].lower()
    if name.endswith(".exr"):
        return "exr-sequence" if "%" in name else "exr"
    if "%" in name:
        return "image-sequence"
    if name.endswith((".png", ".tif", ".tiff")):
        return "image"
    return "video"


def _exists(element: dict[str, Any]) -> bool:
    from .color import _frames

    if element["project"]:
        return Path(element["project"]).is_file()
    if element.get("volume"):
        return bool(_frames(element["volume"])) if "%" in element["volume"] else Path(element["volume"]).is_file()
    if element.get("usd"):
        return Path(element["usd"]).is_file()
    if element.get("splat"):
        return Path(element["splat"]).is_file()
    if element.get("alembic"):
        return Path(element["alembic"]).is_file()
    if not element["file"]:
        return False
    present = bool(_frames(element["file"])) if "%" in element["file"] else Path(element["file"]).is_file()
    return present and (not element["matte"] or bool(_frames(element["matte"])) or Path(element["matte"]).is_file())


def expand(raw: Any, catalog: dict[str, dict[str, Any]], elements: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """A shot's `effects`, each with its item's defaults: (effects, problems)."""

    declared = raw if isinstance(raw, list) else [raw] if raw else []
    effects, problems = [], []
    for entry in declared:
        entry = {"id": entry} if isinstance(entry, str) else dict(entry or {})
        item = catalog.get(str(entry.get("id") or ""))
        if item is None:
            problems.append(f"names the effect {entry.get('id')!r}, which is not in the effect catalog")
            continue
        params = {**item["params"], **{key: value for key, value in entry.items() if key not in ("id", "reason")}}
        effect = {"id": item["id"], "effect": item["effect"], "params": params, "reason": str(entry.get("reason") or "")}
        if item.get("engine") == "ofx":
            effect.update(effect="ofx", plugin=item["plugin"])
        elif item.get("engine") == "blender":
            # Rendered by Blender when the shot is drawn, then composited like an element with alpha.
            effect["effect"] = "element"
            effect["element"] = {"id": f"{item['id']} (Blender)", "blend": "alpha", "format": "generated",
                                 "generated": item["effect"], "file": "", "matte": "", "colorspace": "",
                                 "view": str(params.get("view") or ""), "loop": False}
        elif item["effect"] == "element":
            element = elements.get(str(params.get("element") or ""))
            if element is None:
                wanted = item["element_category"]
                candidates = [e["id"] for e in elements.values() if e["category"] == wanted]
                problems.append(f"composites a {wanted or 'stock'} element, but names none the production has"
                                + (f" (it has {', '.join(candidates)})" if candidates else
                                   f" (add one under vfx_elements/<id>/element.toml, category {wanted})"))
                continue
            if not element["exists"]:
                problems.append(f"composites {element['id']}, whose file is missing")
                continue
            if element["blend"] not in BLENDS:
                problems.append(f"composites {element['id']} with the blend {element['blend']!r}; the blends are "
                                + ", ".join(BLENDS))
                continue
            effect["element"] = element
        effects.append(effect)
    return effects, problems


# --- drawing ------------------------------------------------------------------------


def _number(params: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError) as error:
        raise ValidationError(f"The effect parameter {key} must be a number") from error


def natron_binary() -> str | None:
    import glob

    configured = os.environ.get("CINE_TOASTER_NATRON")
    if configured and Path(configured).expanduser().is_file():
        return str(Path(configured).expanduser())
    found = shutil.which("NatronRenderer")
    if found:
        return found
    candidates = sorted(glob.glob(str(Path.home() / ".local/opt/Natron*/bin/NatronRenderer")))
    return candidates[-1] if candidates else None


def _ofx(effects: list[dict[str, Any]], duration: float, work: Path, *, background: Path | None, start: float,
         width: int, height: int, fps: int, run) -> Path:
    """Run OpenFX plugins through Natron over the picture; returns the treated clip (sound kept)."""

    import json

    natron = natron_binary()
    if not natron:
        raise ValidationError("OpenFX effects run in Natron, which is not found (install it, or set CINE_TOASTER_NATRON)")
    ffmpeg = shutil.which("ffmpeg")
    frames = max(1, round(duration * fps))
    if background is None:
        background, start = render([], duration, work / "source.mp4", width=width, height=height, fps=fps, run=run), 0.0
    (work / "in").mkdir()
    (work / "out").mkdir()
    size = f"{width}:{height}"
    run([ffmpeg, "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(background),
         "-vf", f"scale={size}:force_original_aspect_ratio=decrease,pad={size}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
         "-frames:v", str(frames), "-start_number", "1", str(work / "in" / "f_%04d.png")])
    spec = work / "spec.json"
    spec.write_text(json.dumps({"input": str(work / "in" / "f_####.png"), "output": str(work / "out" / "o_####.png"),
                                "frames": frames, "width": width, "height": height,
                                "effects": [{"plugin": effect["plugin"], "params": effect["params"]}
                                            for effect in effects]}), encoding="utf-8")
    environment = {**os.environ, "CINE_TOASTER_OFX_SPEC": str(spec)}
    completed = subprocess.run([natron, "-w", "Out", f"1-{frames}", str(NATRON_CHAIN_SCRIPT)], cwd=work,
                               env=environment, capture_output=True, text=True, timeout=3600)
    rendered = sorted((work / "out").glob("o_*.png"))
    if completed.returncode != 0 or not rendered:
        raise ValidationError("Natron could not run the OpenFX chain",
                              detail=(completed.stderr or completed.stdout)[-600:])
    treated = work / "treated.mp4"
    first = int(rendered[0].stem.split("_")[-1])
    run([ffmpeg, "-v", "error", "-y", "-framerate", str(fps), "-start_number", str(first), "-i",
         str(work / "out" / "o_%04d.png"), "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(background),
         "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(treated)])
    return treated


def _sequence_input(pattern: str, fps: int, loop: bool) -> list[str]:
    from .color import _frames

    frames = _frames(pattern)
    first = int("".join(ch for ch in frames[0].stem if ch.isdigit())[-6:] or 0) if frames else 1
    return [*(["-stream_loop", "-1"] if loop else []), "-framerate", str(fps), "-start_number", str(first),
            "-i", pattern]


def _element_input(element: dict[str, Any], file: str, duration: float, width: int, height: int, fps: int,
                   params: dict[str, Any], run, *, matte: bool = False) -> list[str]:
    """The FFmpeg input for an element, rendering or converting it first when it needs it.

    Blender projects and generated effects are rendered (cached); EXR frames
    go through OpenColorIO to the picture's encoding (cached); video and
    display-encoded image sequences are read as they are.
    """

    from .color import LINEAR_SPACE, VIEW, exr_to_display
    from .jobs import state_root

    cache = state_root() / "vfx-elements"
    loop = bool(element.get("loop"))
    kind = element.get("format")
    if not matte and kind == "gaussian-splat":
        return _sequence_input(_splat_element(element, params, max(2, round(duration * fps)), width, height, cache),
                               fps, loop)
    if not matte and kind in ("generated", "blender-project", "openvdb", "openusd", "alembic"):
        frames = element.get("frames") or max(2, round(duration * fps))
        rendered = _blender_element(element, params, frames, width, height, fps, cache, run)
        file, kind = rendered, "exr-sequence"
    if not matte and kind in ("exr", "exr-sequence"):
        pattern, _ = exr_to_display(file, cache / "display", colorspace=element.get("colorspace") or LINEAR_SPACE,
                                    view=element.get("view") or VIEW)
        return _sequence_input(pattern, fps, loop)
    if "%" in file:
        return _sequence_input(file, fps, loop)
    if Path(file).suffix.lower() in VIDEO_SUFFIXES:
        return [*(["-stream_loop", "-1"] if loop else []), "-i", file]
    return ["-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}", "-i", file]


def _splat_element(element: dict[str, Any], params: dict[str, Any], frames: int, width: int, height: int,
                   cache: Path) -> str:
    """A Gaussian splat on a turntable, drawn by Spark in a headless browser (cached)."""

    import hashlib
    import json

    from .splat import render as render_splat, turntable_poses

    settings = {**(element.get("params") or {}), **params}
    source = Path(element["splat"])
    stat = source.stat()
    hashed = hashlib.sha256(json.dumps([settings, frames, width, height, str(source), stat.st_size, stat.st_mtime_ns],
                                       sort_keys=True, default=str).encode())
    hashed.update(Path(__file__).with_name("splat.py").read_bytes())
    folder = cache / "splat" / hashed.hexdigest()[:16]
    pattern = folder / "f_%04d.png"
    if not (folder / "done").is_file():
        folder.mkdir(parents=True, exist_ok=True)
        poses = turntable_poses(frames, radius=float(settings.get("radius", 2.5)), height=float(settings.get("height", 0.3)),
                                degrees=float(settings.get("spin", 60)), lens_mm=float(settings.get("lens_mm", 35)))
        render_splat(source, poses, folder, width=width, height=height,
                     transform={"rotation": settings.get("rotation", [180, 0, 0]), "scale": settings.get("scale", 1.0),
                                "centre": True})
        (folder / "done").write_text("", encoding="utf-8")
    return str(pattern)


def _blender_element(element: dict[str, Any], params: dict[str, Any], frames: int, width: int, height: int,
                     fps: int, cache: Path, run) -> str:
    """Render a generated effect or a production's .blend to an EXR sequence with alpha, once."""

    import hashlib
    import json

    from .titles import blender_binary

    blender = blender_binary()
    if not blender:
        raise ValidationError(f"{element['id']} is rendered by Blender, which is not found "
                              "(install it, or set CINE_TOASTER_BLENDER)")
    spec = {"effect": element.get("generated") or "", "params": {**(element.get("params") or {}), **params},
            "width": width, "height": height, "fps": fps, "frames": frames, "formats": ["exr"]}
    if element.get("volume"):
        spec["volume"] = element["volume"]
    if element.get("usd"):
        spec["usd"] = element["usd"]
    if element.get("alembic"):
        spec["alembic"] = element["alembic"]
    hashed = hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode())
    script = (BLENDER_ELEMENT_SCRIPT if element.get("generated") else BUILTIN / "_blender" / (
        "volume.py" if element.get("volume") else "usd.py" if element.get("usd") or element.get("alembic")
        else "project.py"))
    hashed.update(script.read_bytes())
    for source in filter(None, (element.get("project"), element.get("volume"), element.get("usd"), element.get("alembic"))):
        stat = Path(source.replace("%04d", "0001")).stat()  # large files: their size and time, not their bytes
        hashed.update(f"{source}{stat.st_size}{stat.st_mtime_ns}".encode())
    folder = cache / "blender" / hashed.hexdigest()[:16]
    pattern = folder / "exr" / "f_%04d.exr"
    if not (folder / "done").is_file():
        folder.mkdir(parents=True, exist_ok=True)
        spec["output"] = str(folder)
        (folder / "spec.json").write_text(json.dumps(spec, default=str), encoding="utf-8")
        command = [blender, "--background", "--factory-startup"]
        if element.get("project"):
            command += [element["project"]]
        run([*command, "--python", str(script), "--", str(folder / "spec.json")])
        (folder / "done").write_text("", encoding="utf-8")
    return str(pattern)


def render(effects: list[dict[str, Any]], duration: float, output: Path, *, background: Path | None = None,
           start: float = 0.0, width: int = 1280, height: int = 720, fps: int = 24, run=None) -> Path:
    """Apply effects in order to a clip (from `start`) or to a neutral picture; write `output`, sound kept."""

    run = run or (lambda command: subprocess.run(command, check=True, capture_output=True))
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValidationError("FFmpeg is needed to draw effects")
    width, height = width // 2 * 2, height // 2 * 2
    plugins = [effect for effect in effects if effect["effect"] == "ofx"]
    if plugins:
        # OpenFX plugins first, in order, in one Natron chain; then the rest here.
        with tempfile.TemporaryDirectory(prefix="ofx-") as scratch:
            treated = _ofx(plugins, duration, Path(scratch), background=background, start=start, width=width,
                           height=height, fps=fps, run=run)
            rest = [effect for effect in effects if effect["effect"] != "ofx"]
            return render(rest, duration, output, background=treated, start=0.0, width=width, height=height,
                          fps=fps, run=run)
    return render_graph(prepared(effects, duration, width, height, fps, run), duration, output,
                        background=background, start=start, width=width, height=height, fps=fps, run=run)


def prepared(effects: list[dict[str, Any]], duration: float, width: int, height: int, fps: int,
             run) -> list[dict[str, Any]]:
    """The effects with their elements turned into clips the graph reads (`prepare_element`)."""

    return [dict(effect, prepared=prepare_element(effect, duration, width, height, fps, run))
            if effect["effect"] == "element" else effect for effect in effects]


def effects_graph(effects: list[dict[str, Any]], duration: float, *, width: int = 1280, height: int = 720,
                  fps: int = 24, run=None) -> dict[str, Any]:
    """The effects, in order, as a graph with one port, `picture`: what a shot's graph chains after its picture.
    OpenFX plugins are Natron's, which reads and writes files: they are not in it (`render` runs them first)."""

    from .compositing.effects import graph_for

    run = run or (lambda command: subprocess.run(command, check=True, capture_output=True))
    if any(effect["effect"] == "ofx" for effect in effects):
        raise ValidationError("OpenFX plugins are drawn by Natron, outside the graph")
    width, height = width // 2 * 2, height // 2 * 2
    return graph_for(prepared(effects, duration, width, height, fps, run), duration, fps)


def prepare_element(effect: dict[str, Any], duration: float, width: int, height: int, fps: int,
                    run) -> dict[str, Any]:
    """An element's frames as one clip with alpha -- and its matte as another -- for the graph to read, made once
    and kept by what they are (CT-0077). Whatever form a stock library delivers it in (a video, a sequence, EXR
    frames, a Blender render, a splat) is turned into frames here; laying it is the graph's."""

    import hashlib
    import json

    from .jobs import state_root

    element = effect["element"]
    sources = [element.get(key) for key in ("file", "matte", "project", "splat", "volume", "usd", "alembic")]
    stats = [(source, Path(source.replace("%04d", "0001")).stat().st_size)
             for source in sources if source and Path(source.replace("%04d", "0001")).exists()]
    hashed = hashlib.sha256(json.dumps([element, effect["params"], duration, width, height, fps, stats],
                                       sort_keys=True, default=str).encode()).hexdigest()[:20]
    folder = state_root() / "vfx-elements" / "clips"
    folder.mkdir(parents=True, exist_ok=True)

    def made(name: str, file: str, matte: bool) -> str:
        clip = folder / f"{hashed}-{name}.mov"
        if not clip.is_file():
            inputs = _element_input(element, file, duration, width, height, fps, effect["params"], run, matte=matte)
            partial = clip.with_name(f".{clip.name}.part.mov")
            # Nothing until its `start` (frame access, not compositing: the graph lays what the clip holds), and
            # RGB with alpha even for a matte -- QuickTime RLE has no grey; FFmpeg would fall back to a palette.
            delay = max(0.0, float(effect["params"].get("start", 0.0) or 0.0))
            pad = [f"format=argb,tpad=start_duration={delay:.3f}:color=black@0"] if delay else ["format=argb"]
            run([shutil.which("ffmpeg") or "ffmpeg", "-v", "error", "-y", *inputs, "-vf", ",".join(pad),
                 "-t", f"{duration:.3f}", "-r", str(fps), "-an", "-c:v", "qtrle", "-pix_fmt", "argb", str(partial)])
            partial.replace(clip)
        return str(clip)

    kind = element.get("format")
    if kind in ("generated", "blender-project", "openvdb", "openusd", "alembic", "exr", "exr-sequence"):
        # Scene-linear light stays float in the working space, its highlights kept (SPEC-0012's range rule).
        from .color import LINEAR_SPACE, exr_to_working

        if kind in ("exr", "exr-sequence"):
            pattern = element.get("file") or ""
        else:
            frames = element.get("frames") or max(2, round(duration * fps))
            pattern = _blender_element(element, effect["params"], frames, width, height, fps,
                                       state_root() / "vfx-elements", run)
        delay = max(0.0, float(effect["params"].get("start", 0.0) or 0.0))
        clip = exr_to_working(pattern, state_root() / "vfx-elements" / "working",
                              colorspace=element.get("colorspace") or LINEAR_SPACE, lead=round(delay * fps),
                              loop_to=round(duration * fps) if element.get("loop") else 0)
    else:
        clip = made("picture", element.get("file") or "", False)
    prepared = {"_clip": clip, "_blend": element.get("blend", "alpha"), "_key_color": element.get("key_color") or "0x00FF00"}
    if element.get("matte"):
        prepared["_matte"] = made("matte", element["matte"], True)
    return prepared


def render_graph(effects: list[dict[str, Any]], duration: float, output: Path, *, background: Path | None = None,
                 start: float = 0.0, width: int = 1280, height: int = 720, fps: int = 24, run=None) -> Path:
    """Effects drawn by the compositing graph (C6, CT-0077) over a clip, its sound kept; without a clip, over a
    neutral picture for previews (a soft gradient with a dark figure in the middle)."""

    import numpy as np

    from .compositing.drawing import over_picture
    from .compositing.effects import graph_for

    still = None
    if background is None:
        width, height = width // 2 * 2, height // 2 * 2
        ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
        still = np.dstack([0.05 + 0.08 * xs / width, 0.07 + 0.05 * ys / height, 0.1 + 0.03 * xs / width,
                           np.ones_like(xs)]).astype(np.float32)
        still[int(height * 0.35):, int(width * 0.46):int(width * 0.54), :3] = 0.012
    return over_picture(graph_for(effects, duration, fps), duration, output, background=background, still=still,
                        start=start, width=width, height=height, fps=fps, run=run)


def preview_clip(item: dict[str, Any], output: Path, *, root: Path | None = None, element: str = "") -> Path:
    """Two seconds of the effect on a neutral picture: most effects move, a still would hide them."""

    elements = {entry["id"]: entry for entry in list_elements(root)}
    entry: dict[str, Any] = {"id": item["id"]}
    if item["effect"] == "element":
        entry["element"] = element or next((e["id"] for e in elements.values()
                                            if e["category"] == item["element_category"] and e["exists"]), "")
    effects, problems = expand([entry], {item["id"]: item}, elements)
    if problems:
        raise ValidationError(problems[0])
    return render(effects, 2.0, output, width=640, height=360)


def preview(item: dict[str, Any], *, root: Path | None = None, element: str = "", at: float = 0.5) -> bytes:
    """One frame of the effect on a neutral picture, drawn by FFmpeg, as PNG."""

    elements = {entry["id"]: entry for entry in list_elements(root)}
    entry: dict[str, Any] = {"id": item["id"]}
    if item["effect"] == "element":
        chosen = element or next((e["id"] for e in elements.values()
                                  if e["category"] == item["element_category"] and e["exists"]), "")
        entry["element"] = chosen
    effects, problems = expand([entry], {item["id"]: item}, elements)
    if problems:
        raise ValidationError(problems[0])
    duration = 2.0
    with tempfile.TemporaryDirectory(prefix="vfx-preview-") as scratch:
        clip = render(effects, duration, Path(scratch) / "preview.mp4", width=640, height=360)
        frame = Path(scratch) / "frame.png"
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-ss", f"{duration * at:.2f}", "-i", str(clip),
                        "-frames:v", "1", str(frame)], check=True, capture_output=True)
        return frame.read_bytes()


def cached_preview(item: dict[str, Any], *, root: Path | None = None) -> Path:
    """The preview clip, drawn once per manifest and element library state."""

    import hashlib
    import threading

    from .jobs import state_root

    hashed = hashlib.sha256(Path(__file__).read_bytes())
    hashed.update((Path(item["directory"]) / "effect.toml").read_bytes())
    for element in list_elements(root):
        hashed.update(f"{element['id']}{element['file']}{element['exists']}".encode())
    path = state_root() / "vfx-previews" / f"{item['id']}-{hashed.hexdigest()[:16]}.mp4"
    with _GUARD:
        lock = _LOCKS.setdefault(path.name, threading.Lock())
    with lock:
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.stem}.{os.getpid()}-{threading.get_ident()}.mp4")
            preview_clip(item, temporary, root=root)
            temporary.replace(path)
    return path


import threading as _threading  # noqa: E402

_GUARD = _threading.Lock()
_LOCKS: dict[str, Any] = {}
