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
CATEGORIES = ("texture", "lens", "light", "motion", "glitch", "particles", "elements")
EFFECTS = ("grain", "vignette", "light-leak", "aberration", "glitch", "shake", "flash", "defocus", "old-film",
           "element", "sparks-burst", "disintegrate", "look")
ENGINES = ("ffmpeg", "blender")
#: Effects Blender renders as an element on the fly (vfx_assets/_blender/element.py).
BLENDER_EFFECTS = ("sparks-burst", "disintegrate")
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
            matte = str((folder / str(raw["matte"])).resolve()) if raw.get("matte") else ""
            element = {
                "id": str(raw.get("id") or folder.name), "label": str(raw.get("label") or folder.name),
                "category": str(raw.get("category") or "other"), "blend": str(raw.get("blend") or "screen"),
                "key_color": str(raw.get("key_color") or "0x00FF00"), "file": file, "matte": matte,
                "project": project, "volume": volume, "usd": usd, "frames": int(raw.get("frames") or 0),
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
        if item.get("engine") == "blender":
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


def _chain(effect: dict[str, Any], label: str, out: str, duration: float, width: int, height: int,
           element_input: int | None) -> str:
    """One effect as a filter-graph step from [label] to [out]."""

    params, kind = effect["params"], effect["effect"]
    strength = _number(params, "strength", 0.5)
    start = _number(params, "start", 0.0)
    if kind == "grain":
        return f"[{label}]noise=alls={max(1, round(strength * 40))}:allf=t+u[{out}]"
    if kind == "vignette":
        return f"[{label}]vignette=angle={0.2 + strength * 0.6:.3f}[{out}]"
    if kind == "light-leak":
        # A warm glow drifting across the frame, laid over the picture.
        colour = str(params.get("color") or "#FF8A3C").lstrip("#")
        r, g, b = (int(colour[i:i + 2], 16) for i in (0, 2, 4))
        return (f"color=c=black:s={width}x{height}:d={duration:.3f},format=rgba,"
                f"geq=r={r}:g={g}:b={b}:"
                f"a='{255 * strength:.0f}*exp(-pow((X-W*(0.2+0.6*T/{max(0.1, duration):.3f}))/(W*0.3),2))'[{label}leak];"
                f"[{label}][{label}leak]overlay=format=auto:shortest=1,format=yuv420p[{out}]")
    if kind == "aberration":
        shift = max(1, round(strength * 8 * width / 1280))
        return f"[{label}]rgbashift=rh=-{shift}:bh={shift}[{out}]"
    if kind == "glitch":
        # Bursts of a split, noisy copy over the picture, several times a second.
        shift = max(2, round(strength * 24 * width / 1280))
        rate = _number(params, "rate", 0.15)
        return (f"[{label}]split[{label}a][{label}b];[{label}b]rgbashift=rh={shift}:bh=-{shift}:edge=wrap,"
                f"noise=alls={max(1, round(strength * 30))}:allf=t[{label}g];"
                f"[{label}a][{label}g]overlay=enable='gt(mod(t*12\\,1)\\,{1 - rate:.3f})'[{out}]")
    if kind == "shake":
        amount = max(2, round(strength * 20 * width / 1280))
        return (f"[{label}]crop=iw-{2 * amount}:ih-{2 * amount}:"
                f"'{amount}+{amount}*sin(t*37)*sin(t*13)':'{amount}+{amount}*sin(t*29)*cos(t*17)',"
                f"scale={width}:{height}[{out}]")
    if kind == "flash":
        length = _number(params, "length", 0.4)
        return (f"[{label}]eq=brightness='{min(1.0, strength):.3f}*max(0,1-abs(t-{start:.3f})/{length:.3f})':"
                f"eval=frame[{out}]")
    if kind == "defocus":
        length = _number(params, "length", 1.2)
        # Out of focus, coming into focus: the blur shrinks over `length`.
        return (f"[{label}]split[{label}s][{label}b];[{label}b]gblur=sigma={4 + strength * 16:.1f}[{label}bl];"
                f"[{label}s][{label}bl]blend=all_expr='A*min(1,T/{length:.3f})+B*(1-min(1,T/{length:.3f}))'[{out}]")
    if kind == "old-film":
        return (f"[{label}]colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131,"
                f"noise=alls={max(1, round(strength * 30))}:allf=t+u,vignette=angle=0.6,"
                f"eq=brightness='0.03*sin(t*23)':eval=frame[{out}]")
    if kind == "look":
        # An OpenColorIO view baked to a 3D LUT (cached), for FFmpeg to apply.
        from .color import bake_look
        from .jobs import state_root

        view = str(params.get("view") or "ACES 2.0 - SDR 100 nits (Rec.709)")
        name = "".join(ch if ch.isalnum() else "-" for ch in view).strip("-").lower()
        lut = state_root() / "looks" / f"{name}.cube"
        if not lut.is_file():
            bake_look(lut, view=view)
        path = str(lut).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        mix = min(1.0, max(0.0, strength))
        return (f"[{label}]split[{label}o][{label}l];[{label}l]lut3d=file='{path}'[{label}g];"
                f"[{label}o][{label}g]blend=all_expr='A*(1-{mix:.3f})+B*{mix:.3f}'[{out}]")
    if kind == "element":
        element = effect["element"]
        scale = _number(params, "scale", 1.0)
        x, y = _number(params, "x", 0.5), _number(params, "y", 0.5)
        opacity = _number(params, "opacity", 1.0)
        # Fitted inside `scale` of the frame, its proportion kept, never larger than the frame.
        box_w, box_h = max(2, round(width * min(scale, 1.0) / 2) * 2), max(2, round(height * min(scale, 1.0) / 2) * 2)
        size = f"{box_w}:{box_h}:force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2"
        source = f"[{element_input}:v]setpts=PTS-STARTPTS+{start:.3f}/TB"
        if element.get("_matte_input") is not None:
            # A separate matte: its brightness is the element's opacity.
            matte = f"[{element['_matte_input']}:v]setpts=PTS-STARTPTS+{start:.3f}/TB,format=gray[{label}m]"
            source = f"{matte};{source},format=rgba[{label}c];[{label}c][{label}m]alphamerge"
        source += f",scale={size}"
        place = f"x='W*{x:.3f}-w/2':y='H*{y:.3f}-h/2'"
        if element["blend"] in ("screen", "add"):
            mode = "screen" if element["blend"] == "screen" else "addition"
            # A black-backed element: padded to the frame and blended.
            return (f"{source},pad={width}:{height}:'{width}*{x:.3f}-iw/2':'{height}*{y:.3f}-ih/2':black,"
                    f"format=gbrp[{label}e];[{label}]format=gbrp[{label}p];"
                    f"[{label}p][{label}e]blend=all_mode={mode}:all_opacity={opacity:.3f}:shortest=0,format=yuv420p[{out}]")
        if element["blend"] == "key":
            source += f",colorkey={element['key_color']}:{_number(params, 'similarity', 0.3):.3f}:0.1"
        return (f"{source},format=yuva420p,colorchannelmixer=aa={opacity:.3f}[{label}e];"
                f"[{label}][{label}e]overlay={place}:eof_action=pass:format=auto[{out}]")
    raise ValidationError(f"The effect {kind!r} is not one Cine Toaster draws", effects=list(EFFECTS))


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
    if not matte and kind in ("generated", "blender-project", "openvdb", "openusd"):
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
    hashed = hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode())
    script = (BLENDER_ELEMENT_SCRIPT if element.get("generated") else BUILTIN / "_blender" / (
        "volume.py" if element.get("volume") else "usd.py" if element.get("usd") else "project.py"))
    hashed.update(script.read_bytes())
    for source in filter(None, (element.get("project"), element.get("volume"), element.get("usd"))):
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
    size = f"{width}:{height}"
    if background is not None:
        inputs = ["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(background)]
        graph = [f"[0:v]scale={size}:force_original_aspect_ratio=decrease,pad={size}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
                 f"fps={fps},format=yuv420p[v0]"]
        sound = ["-map", "0:a?"]
    else:
        # A neutral picture for previews: a soft gradient with a figure-like shape.
        inputs = ["-f", "lavfi", "-i", f"gradients=s={width}x{height}:c0=0x2a3a4a:c1=0x6a5a4a:d={duration:.3f}:r={fps}:speed=0.01:seed=7"]
        graph = [f"[0:v]drawbox=x=iw*0.46:y=ih*0.35:w=iw*0.08:h=ih*0.65:color=0x1c1f22:t=fill,format=yuv420p[v0]"]
        sound = []
    label = "v0"
    for index, effect in enumerate(effects, 1):
        element_input = None
        if effect["effect"] == "element":
            element = effect["element"] = dict(effect["element"])
            element_input = len([part for part in inputs if part == "-i"])
            inputs += _element_input(element, element["file"], duration, width, height, fps, effect["params"], run)
            element["_matte_input"] = None
            if element.get("matte"):
                element["_matte_input"] = element_input + 1
                inputs += _element_input(element, element["matte"], duration, width, height, fps, {}, run,
                                         matte=True)
        graph.append(_chain(effect, label, f"v{index}", duration, width, height, element_input))
        label = f"v{index}"
    output.parent.mkdir(parents=True, exist_ok=True)
    run([ffmpeg, "-v", "error", "-y", *inputs, "-filter_complex", ";".join(graph), "-map", f"[{label}]", *sound,
         "-t", f"{duration:.3f}", "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt",
         "yuv420p", "-c:a", "aac", str(output)])
    return output


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
