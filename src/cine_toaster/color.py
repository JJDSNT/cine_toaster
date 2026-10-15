"""Colour management with OpenColorIO (CT-0047).

Elements delivered in scene-linear light (OpenEXR from a renderer or a
simulation) are converted by an OCIO processor, not by guesswork -- today to
the display encoding before they are composited, which clips them at white
(SPEC-0012's range rule, not met yet). Looks (a film response, a grade) are
OCIO transforms applied in the compositing graph (`colour.lut`, CT-0077);
`bake_look` still writes one as a .cube, for another tool.

The config is `CINE_TOASTER_OCIO`, else `$OCIO`, else OCIO's built-in ACES
studio config (`ocio://studio-config-latest`), which ships inside the
`opencolorio` wheel: nothing to download.
"""

from __future__ import annotations

import glob
import hashlib
import os
import re
from pathlib import Path
from typing import Any

from .errors import ValidationError

BUILTIN_CONFIG = "ocio://studio-config-latest"
#: What the pictures of a film are, here: sRGB-encoded Rec.709.
PICTURE_SPACE = "sRGB Encoded Rec.709 (sRGB)"
LINEAR_SPACE = "Linear Rec.709 (sRGB)"
DISPLAY, VIEW = "sRGB - Display", "Un-tone-mapped"


def available() -> str:
    """Why colour management cannot run here, or ''."""

    try:
        import OpenEXR  # noqa: F401
        import PyOpenColorIO  # noqa: F401
    except ImportError:
        return "OpenColorIO and OpenEXR are not installed (make install-vfx)"
    return ""


def config():
    import PyOpenColorIO as ocio

    source = os.environ.get("CINE_TOASTER_OCIO") or os.environ.get("OCIO") or BUILTIN_CONFIG
    try:
        return ocio.Config.CreateFromFile(source)
    except Exception as error:  # OCIO raises its own exception type
        raise ValidationError(f"The OpenColorIO config {source!r} cannot be read: {error}") from error


def _processor(source: str, *, display: str = DISPLAY, view: str = VIEW, target: str = ""):
    import PyOpenColorIO as ocio

    cfg = config()
    names = {space.getName() for space in cfg.getColorSpaces()}
    if source not in names:
        raise ValidationError(f"The colour space {source!r} is not in the OCIO config",
                              examples=sorted(name for name in names if "Linear" in name or "sRGB" in name)[:8])
    if target:
        return cfg.getProcessor(source, target).getDefaultCPUProcessor()
    transform = ocio.DisplayViewTransform(src=source, display=display, view=view)
    return cfg.getProcessor(transform).getDefaultCPUProcessor()


def _frames(pattern: str) -> list[Path]:
    """The files of a `%04d` sequence, in order."""

    match = re.search(r"%0?(\d*)d", pattern)
    if not match:
        return [Path(pattern)] if Path(pattern).is_file() else []
    wildcard = pattern[:match.start()] + "*" + pattern[match.end():]
    number = re.compile(re.escape(pattern[:match.start()]) + r"(\d+)" + re.escape(pattern[match.end():]) + "$")
    found = [(int(m.group(1)), Path(path)) for path in glob.glob(wildcard) if (m := number.search(path))]
    return [path for _, path in sorted(found)]


def exr_layers(path: Path) -> dict:
    """Every layer of an EXR, from every part -- Blender 5 writes a multilayer EXR as one part per pass, and
    reading the first part alone loses the rest (found in CT-0081). Keys are the layers' names without the
    view layer ("Combined", "Depth", "Object Index", or "RGBA" for a plain file); values float32 arrays,
    (height, width) for one channel, (height, width, n) for several. Two layers of one name (two view layers'
    Depth) are refused, never one chosen for the other."""

    import numpy as np
    import OpenEXR

    found: dict[str, dict[str | None, Any]] = {}
    with OpenEXR.File(str(path)) as file:
        for part in file.parts:
            for name, channel in part.channels.items():
                pieces, axis = name.split("."), None
                if len(pieces) > 1 and len(pieces[-1]) == 1:  # a pass's channel: "ViewLayer.Depth.Z", "Normal.X"
                    pieces, axis = pieces[:-1], pieces[-1]
                if len(pieces) > 1:  # the view layer: "ViewLayer.Combined"
                    pieces = pieces[1:]
                key = ".".join(pieces)
                if axis in found.setdefault(key, {}):
                    raise ValidationError(f"{Path(path).name} has two layers called {key!r} (another is {name!r} "
                                          f"in {part.name()!r}): which one is meant cannot be told")
                found[key][axis] = np.asarray(channel.pixels, dtype=np.float32)
    layers: dict = {}
    order = "RGBAXYZUVW"
    for key, channels in found.items():
        if None in channels and len(channels) > 1:
            raise ValidationError(f"{Path(path).name} has a layer {key!r} both whole and by channel")
        if len(channels) == 1:
            layers[key] = next(iter(channels.values()))
        else:  # one channel a name -- X, Y, Z of a Normal pass -- stacked in their order
            axes = sorted(channels, key=lambda axis: (order.find(axis) if axis in order else len(order), axis))
            layers[key] = np.stack([channels[axis] for axis in axes], axis=-1)
    return layers


def exr_layer(path: Path, layer: str | None = None):
    """One layer of an EXR, named -- or, unnamed, its only one. A file of several layers read without a name is
    refused with their names: a depth is never the first channel that happens to be there."""

    layers = exr_layers(Path(path))
    if layer is None:
        if len(layers) != 1:
            raise ValidationError(f"{Path(path).name} has the layers {', '.join(sorted(layers))}: say which "
                                  "(`layer`)")
        return next(iter(layers.values()))
    if layer not in layers:
        raise ValidationError(f"{Path(path).name} has no layer {layer!r}; it has {', '.join(sorted(layers))}")
    return layers[layer]


def read_exr(path: Path):
    """An EXR's RGBA as float32 (height, width, 4); alpha 1 when it has none. A multilayer EXR's `Combined` pass
    is its picture."""

    import numpy as np
    import OpenEXR

    with OpenEXR.File(str(path)) as file:
        channels = file.channels()
        if not any(name in channels for name in ("RGBA", "RGB", "R")):
            combined = {name: layer for name, layer in exr_layers(path).items() if name.endswith("Combined")}
            if combined:
                pixels = next(iter(combined.values()))
                if pixels.ndim == 3 and pixels.shape[2] == 4:
                    return pixels
        if "RGBA" in channels:
            pixels = np.asarray(channels["RGBA"].pixels, dtype=np.float32)
        elif "RGB" in channels:
            rgb = np.asarray(channels["RGB"].pixels, dtype=np.float32)
            pixels = np.concatenate([rgb, np.ones(rgb.shape[:2] + (1,), np.float32)], axis=2)
        else:
            planes = [np.asarray(channels[name].pixels, dtype=np.float32) if name in channels else None
                      for name in ("R", "G", "B", "A")]
            if any(plane is None for plane in planes[:3]):
                raise ValidationError(f"{path.name} has no R, G and B channels", channels=sorted(channels))
            alpha = planes[3] if planes[3] is not None else np.ones_like(planes[0])
            pixels = np.stack([*planes[:3], alpha], axis=2)
    return pixels


def exr_to_display(pattern: str, output: Path, *, colorspace: str = LINEAR_SPACE, display: str = DISPLAY,
                   view: str = VIEW) -> tuple[str, int]:
    """Convert a scene-linear EXR sequence to display-encoded RGBA PNGs; returns (pattern, first number).

    EXR alpha is premultiplied: the colour is divided by it before the
    (non-linear) display transform, and the PNGs carry straight alpha. The
    result is cached by the frames' names, sizes and times and the transform.
    """

    import numpy as np
    from PIL import Image

    missing = available()
    if missing:
        raise ValidationError(missing)
    frames = _frames(pattern)
    if not frames:
        raise ValidationError(f"No EXR frames match {pattern}")
    hashed = hashlib.sha256(f"{colorspace}|{display}|{view}".encode())
    for frame in frames:
        stat = frame.stat()
        hashed.update(f"{frame.name}{stat.st_size}{stat.st_mtime_ns}".encode())
    folder = output / hashed.hexdigest()[:16]
    target = folder / "f_%04d.png"
    if (folder / "done").is_file():
        return str(target), 1
    folder.mkdir(parents=True, exist_ok=True)
    processor = _processor(colorspace, display=display, view=view)
    for index, frame in enumerate(frames, 1):
        pixels = read_exr(frame)
        alpha = pixels[..., 3:4]
        colour = np.ascontiguousarray(np.where(alpha > 1e-6, pixels[..., :3] / np.maximum(alpha, 1e-6), 0.0),
                                      dtype=np.float32)
        processor.applyRGB(colour)
        rgba = np.concatenate([np.clip(colour, 0, 1), np.clip(alpha, 0, 1)], axis=2)
        Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA").save(folder / f"f_{index:04d}.png")
    (folder / "done").write_text(str(len(frames)), encoding="utf-8")
    return str(target), 1


def exr_to_working(pattern: str, output: Path, *, colorspace: str = LINEAR_SPACE, lead: int = 0,
                   loop_to: int = 0) -> str:
    """A scene-linear EXR sequence in the compositing graph's working space, still float, its light above white
    kept (SPEC-0012's range rule, CT-0077); `lead` transparent frames first (an element that starts later), and
    the frames repeated until there are `loop_to` (a looping element).
    Alpha stays premultiplied. Cached by the frames' names, sizes and times. Returns the new pattern."""

    import numpy as np
    import OpenEXR

    frames = _frames(pattern)
    if not frames:
        raise ValidationError(f"No EXR frames match {pattern}")
    hashed = hashlib.sha256(f"{colorspace}|{lead}|{loop_to}|working".encode())
    for frame in frames:
        stat = frame.stat()
        hashed.update(f"{frame.name}{stat.st_size}{stat.st_mtime_ns}".encode())
    folder = output / hashed.hexdigest()[:16]
    target = folder / "f_%04d.exr"
    if (folder / "done").is_file():
        return str(target)
    folder.mkdir(parents=True, exist_ok=True)
    convert = None if colorspace == LINEAR_SPACE else _processor(colorspace, target=LINEAR_SPACE)

    def write(index: int, pixels) -> None:
        OpenEXR.File({"type": OpenEXR.scanlineimage, "compression": OpenEXR.ZIP_COMPRESSION},
                     {"RGBA": pixels.astype(np.float16)}).write(str(folder / f"f_{index:04d}.exr"))

    first = read_exr(frames[0])
    for index in range(1, lead + 1):
        write(index, np.zeros_like(first))
    if loop_to > len(frames):
        frames = [frames[index % len(frames)] for index in range(loop_to)]
    for index, frame in enumerate(frames, lead + 1):
        pixels = read_exr(frame)
        if convert is not None:  # a transform need not be linear: applied to the straight colour
            alpha = pixels[..., 3:4]
            colour = np.ascontiguousarray(np.where(alpha > 1e-6, pixels[..., :3] / np.maximum(alpha, 1e-6), 0.0),
                                          dtype=np.float32)
            convert.applyRGB(colour)
            pixels = np.concatenate([colour * alpha, alpha], axis=2)
        write(index, pixels)
    (folder / "done").write_text(str(len(frames) + lead), encoding="utf-8")
    return str(target)


def bake_look(output: Path, *, source: str = PICTURE_SPACE, working: str = "ACEScg", display: str = DISPLAY,
              view: str = "ACES 2.0 - SDR 100 nits (Rec.709)", size: int = 33) -> Path:
    """A 3D LUT (.cube) taking a display picture through a scene-referred look back to the display.

    The picture is decoded to linear, lifted into `working`, and shown
    through `view` (ACES 2.0's tone scale by default): a film response,
    measured by OCIO, as a .cube for another tool (the graph applies the transform itself, `colour.lut`).
    """

    import numpy as np

    missing = available()
    if missing:
        raise ValidationError(missing)
    to_linear = _processor(source, target=working)
    to_display = _processor(working, display=display, view=view)
    grid = np.linspace(0.0, 1.0, size, dtype=np.float32)
    # .cube order: red fastest, then green, then blue.
    b, g, r = np.meshgrid(grid, grid, grid, indexing="ij")
    table = np.ascontiguousarray(np.stack([r, g, b], axis=-1).reshape(-1, 3), dtype=np.float32)
    to_linear.applyRGB(table)
    table = np.ascontiguousarray(table * 1.0, dtype=np.float32)
    to_display.applyRGB(table)
    table = np.clip(table, 0.0, 1.0)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"TITLE \"{source} -> {working} -> {view}\"", f"LUT_3D_SIZE {size}"]
    lines += [f"{red:.6f} {green:.6f} {blue:.6f}" for red, green, blue in table]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def describe() -> dict[str, Any]:
    cfg = config()
    return {"config": os.environ.get("CINE_TOASTER_OCIO") or os.environ.get("OCIO") or BUILTIN_CONFIG,
            "picture": PICTURE_SPACE, "linear": LINEAR_SPACE, "display": DISPLAY,
            "views": list(cfg.getViews(DISPLAY))}
