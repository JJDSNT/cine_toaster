"""The reference: SPEC-0012's operations evaluated in NumPy, as the colour contract says (ADR 0022 §5).

Float, scene-linear, premultiplied. It defines the right result; every
renderer is checked against it. It is not meant to be fast.

    pictures = evaluate(graph, inputs={"from": a, "to": b}, frames=48, size=(160, 90), fps=24)

Values inside:

- a picture is an (H, W, 4) float32 array, linear, premultiplied;
- a matte an (H, W) float32 array;
- a signal an (H, W) or (H, W, C) array, with its kind;
- a curve a function from seconds to a number or a vector.

Inputs are files (read once, converted into the working space at the source,
SPEC-0012 §2), arrays already in the working space, or curves. Only the ops in
`IMPLEMENTED` are evaluated; any other is refused by name, never guessed.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from ..errors import ValidationError
from .schema import validate

#: The default spaces, converted by the exact sRGB transfer function; any other goes through OCIO.
LINEAR = "Linear Rec.709 (sRGB)"
ENCODED = "sRGB Encoded Rec.709 (sRGB)"
REC709 = (0.2126, 0.7152, 0.0722)


# --- colour --------------------------------------------------------------------------


def decode_srgb(values: np.ndarray) -> np.ndarray:
    """sRGB-encoded values to linear light (IEC 61966-2-1)."""

    return np.where(values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4).astype(np.float32)


def encode_srgb(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, 0.0, None)
    return np.where(clipped <= 0.0031308, clipped * 12.92, 1.055 * clipped ** (1 / 2.4) - 0.055).astype(np.float32)


def convert(rgb: np.ndarray, source: str, target: str) -> np.ndarray:
    """Between colour spaces: the default pair exactly, any other through OCIO."""

    if source == target:
        return rgb
    if (source, target) == (ENCODED, LINEAR):
        return decode_srgb(rgb)
    if (source, target) == (LINEAR, ENCODED):
        return encode_srgb(rgb)
    from ..color import config

    processor = config().getProcessor(source, target).getDefaultCPUProcessor()
    flat = np.ascontiguousarray(rgb.reshape(-1, 3), dtype=np.float32)
    processor.applyRGB(flat)
    return flat.reshape(rgb.shape)


# --- reading and writing ----------------------------------------------------------------


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise ValidationError("FFmpeg is needed to read and write pictures")
    return path


def read(path: Path, frames: int, size: tuple[int, int], fps: float, *, start: float = 0.0,
         colorspace: str = ENCODED, alpha: str = "straight", working: str = LINEAR) -> np.ndarray:
    """A clip or a still as (frames, H, W, 4) in the working space, premultiplied (SPEC-0012 §2)."""

    width, height = size
    still = Path(path).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".exr", ".tif", ".tiff")
    source = ["-loop", "1", "-framerate", f"{fps:g}"] if still else ["-ss", f"{start:.4f}"]
    completed = subprocess.run(
        [_ffmpeg(), "-loglevel", "error", *source, "-i", str(path), "-frames:v", str(frames),
         "-vf", f"fps={fps:g},scale={width}:{height}:flags=bicubic", "-f", "rawvideo", "-pix_fmt", "rgba64le", "-"],
        capture_output=True, timeout=900)
    if completed.returncode != 0:
        raise ValidationError(f"Reading {Path(path).name} failed: {completed.stderr.decode()[-300:]}")
    data = np.frombuffer(completed.stdout, dtype="<u2").astype(np.float32) / 65535.0
    count = data.size // (width * height * 4)
    if count == 0:
        raise ValidationError(f"{Path(path).name} gave no frames")
    pictures = data[: count * width * height * 4].reshape(count, height, width, 4)
    if count < frames:  # a clip shorter than the extent holds its last frame
        pictures = np.concatenate([pictures, np.repeat(pictures[-1:], frames - count, axis=0)])
    rgb = convert(pictures[..., :3], colorspace, working)
    if alpha == "straight":
        rgb = rgb * pictures[..., 3:4]
    return np.concatenate([rgb, pictures[..., 3:4]], axis=-1).astype(np.float32)


def write(pictures: np.ndarray, destination: Path, fps: float, *, working: str = LINEAR,
          display: str = ENCODED) -> Path:
    """(frames, H, W, 4) linear premultiplied to an H.264 file in the display encoding, over black."""

    frames, height, width, _ = pictures.shape
    rgb = convert(np.clip(pictures[..., :3], 0.0, None), working, display)  # premultiplied: already over black
    data = (np.clip(rgb, 0.0, 1.0) * 65535.0 + 0.5).astype("<u2")
    completed = subprocess.run(
        [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb48le", "-s", f"{width}x{height}",
         "-r", f"{fps:g}", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv444p",
         str(destination)],
        input=data.tobytes(), capture_output=True, timeout=900)
    if completed.returncode != 0:
        raise ValidationError(f"Writing {destination.name} failed: {completed.stderr.decode()[-300:]}")
    return destination


# --- curves -----------------------------------------------------------------------------

_EASES: dict[str, Callable[[float], float]] = {
    "linear": lambda x: x,
    "in": lambda x: x * x,
    "out": lambda x: 1 - (1 - x) * (1 - x),
    "in-out": lambda x: 3 * x * x - 2 * x * x * x,
    "hold": lambda x: 0.0,
}


def keys_curve(keys: list[Any]) -> Callable[[float], Any]:
    """`[t, value]` or `{t, value, ease}`: between keys the left key's ease; outside them, held (SPEC-0012 §6)."""

    points = []
    for key in keys:
        if isinstance(key, dict):
            points.append((float(key["t"]), np.asarray(key["value"], dtype=np.float32), str(key.get("ease", "linear"))))
        else:
            points.append((float(key[0]), np.asarray(key[1], dtype=np.float32), "linear"))
    points.sort(key=lambda point: point[0])

    def at(seconds: float) -> Any:
        if seconds <= points[0][0]:
            return points[0][1]
        for (t0, v0, ease), (t1, v1, _) in zip(points, points[1:]):
            if seconds < t1:
                x = _EASES.get(ease, _EASES["linear"])((seconds - t0) / (t1 - t0))
                return v0 + (v1 - v0) * x
        return points[-1][1]

    return at


def noise_curve(seed: int, frequency: float, amplitude: float, offset: float) -> Callable[[float], float]:
    """Smooth, repeatable value noise: the same seed gives the same curve on every renderer."""

    rng = np.random.default_rng(seed)
    knots = rng.uniform(-1.0, 1.0, 4096).astype(np.float32)

    def at(seconds: float) -> float:
        position = max(seconds, 0.0) * frequency
        index = int(position) % (len(knots) - 1)
        x = position - math.floor(position)
        x = 3 * x * x - 2 * x * x * x
        return float(offset + amplitude * (knots[index] + (knots[index + 1] - knots[index]) * x))

    return at


# --- the evaluator ----------------------------------------------------------------------


@dataclass
class Context:
    size: tuple[int, int]
    fps: float
    frames: int
    working: str = LINEAR
    root: Path | None = None  # where a source's relative path is read from
    cache: dict[tuple[str, int], Any] = field(default_factory=dict)


def _matte(value: Any) -> np.ndarray:
    """A picture used as a matte is its alpha (SPEC-0012 §1)."""

    return value[..., 3] if isinstance(value, np.ndarray) and value.ndim == 3 and value.shape[-1] == 4 else value


def _picture(value: Any) -> np.ndarray:
    """A matte used as a picture is grey with alpha 1 (SPEC-0012 §1)."""

    if isinstance(value, np.ndarray) and value.ndim == 2:
        return np.stack([value, value, value, np.ones_like(value)], axis=-1)
    return value


def _blur(image: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0:
        return image
    sigma = max(radius / 2.0, 1e-3)
    half = max(1, int(math.ceil(sigma * 3)))
    kernel = np.exp(-0.5 * (np.arange(-half, half + 1) / sigma) ** 2).astype(np.float32)
    kernel /= kernel.sum()
    out = image
    for axis in (0, 1):
        padded = np.pad(out, [(half, half) if dim == axis else (0, 0) for dim in range(out.ndim)], mode="edge")
        out = sum(kernel[i] * np.take(padded, range(i, i + out.shape[axis]), axis=axis) for i in range(len(kernel)))
    return out.astype(np.float32)


def _shape(node: dict[str, Any], size: tuple[int, int], scale: float) -> np.ndarray:
    from PIL import Image, ImageDraw

    width, height = size
    # Drawn at four times the size and reduced: an edge with coverage, not a staircase.
    big = Image.new("L", (width * 4, height * 4), 0)
    draw = ImageDraw.Draw(big)
    points = [(float(x), float(y)) for x, y in node.get("points") or [[0, 0], [1, 1]]]
    cx = sum(x for x, _ in points) / len(points)
    cy = sum(y for _, y in points) / len(points)
    scaled = [((cx + (x - cx) * scale) * width * 4, (cy + (y - cy) * scale) * height * 4) for x, y in points]
    kind = node.get("shape", "rectangle")
    if kind == "rectangle":
        (x0, y0), (x1, y1) = scaled[0], scaled[-1]
        draw.rectangle([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], fill=255)
    elif kind == "ellipse":
        (x0, y0), (x1, y1) = scaled[0], scaled[-1]
        draw.ellipse([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], fill=255)
    else:
        draw.polygon(scaled, fill=255)
    matte = np.asarray(big.resize((width, height), Image.BOX), dtype=np.float32) / 255.0
    feather = float(node.get("feather") or 0.0) * max(width, height)
    return _blur(matte, feather)


def _affine(image: np.ndarray, node: dict[str, Any], params: Callable[[str, Any], Any]) -> np.ndarray:
    """A 2D transform about a pivot, sampled bilinearly; outside the source is transparent (SPEC-0012 §3)."""

    height, width = image.shape[:2]
    translate = np.broadcast_to(np.asarray(params("translate", [0.0, 0.0]), dtype=np.float32), (2,))
    scale = np.broadcast_to(np.asarray(params("scale", [1.0, 1.0]), dtype=np.float32), (2,))
    rotate = np.asarray(params("rotate", 0.0), dtype=np.float32).reshape(-1)
    if rotate.size > 1 and (abs(rotate[0]) > 1e-6 or abs(rotate[1]) > 1e-6) or float(params("perspective", 0) or 0):
        raise ValidationError("The reference does not yet rotate out of the picture plane (perspective): C4")
    angle = math.radians(float(rotate[-1]))
    pivot = np.broadcast_to(np.asarray(params("pivot", [0.5, 0.5]), dtype=np.float32), (2,))
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    # Output pixel -> source pixel: undo translate, rotate, scale about the pivot (all in picture fractions).
    u = (xs + 0.5) / width - pivot[0] - translate[0]
    v = (ys + 0.5) / height - pivot[1] - translate[1]
    cos, sin = math.cos(-angle), math.sin(-angle)
    u, v = (u * cos - v * sin * height / width), (u * sin * width / height + v * cos)
    sx = (u / max(scale[0], 1e-6) + pivot[0]) * width - 0.5
    sy = (v / max(scale[1], 1e-6) + pivot[1]) * height - 0.5
    x0, y0 = np.floor(sx).astype(int), np.floor(sy).astype(int)
    fx, fy = (sx - x0)[..., None], (sy - y0)[..., None]
    padded = np.pad(image if image.ndim == 3 else image[..., None], ((1, 1), (1, 1), (0, 0)))

    def sample(px: np.ndarray, py: np.ndarray) -> np.ndarray:
        inside = (px >= -1) & (px <= width) & (py >= -1) & (py <= height)
        return padded[np.clip(py + 1, 0, height + 1), np.clip(px + 1, 0, width + 1)] * inside[..., None]

    out = (sample(x0, y0) * (1 - fx) * (1 - fy) + sample(x0 + 1, y0) * fx * (1 - fy)
           + sample(x0, y0 + 1) * (1 - fx) * fy + sample(x0 + 1, y0 + 1) * fx * fy)
    return out.astype(np.float32) if image.ndim == 3 else out[..., 0].astype(np.float32)


IMPLEMENTED = {
    "generate.source", "generate.solid", "generate.gradient",
    "signal.luminance", "signal.luma", "signal.channel",
    "matte.from_signal", "matte.threshold", "matte.combine", "matte.shape", "matte.key",
    "merge.over", "merge.mix", "merge.blend", "merge.porter_duff", "merge.channels",
    "warp.transform",
    "colour.grade", "colour.invert",
    "filter.blur",
    "curve.progress", "curve.keys", "curve.map", "curve.combine", "curve.noise",
}


def evaluate(graph: dict[str, Any], inputs: dict[str, Any], *, frames: int, size: tuple[int, int], fps: float,
             working: str = LINEAR, root: Path | None = None) -> np.ndarray:
    """The graph's output picture for every frame of its extent: (frames, H, W, 4), linear, premultiplied."""

    problems = validate(graph)
    if problems:
        raise ValidationError("The graph is not valid: " + "; ".join(message for _, message in problems))
    nodes = graph["nodes"]
    missing = sorted({node["op"] for node in nodes.values() if node["op"] not in IMPLEMENTED})
    if missing:
        raise ValidationError(f"The reference does not implement {', '.join(missing)} yet")
    context = Context(size, fps, frames, working, root)
    width, height = size
    length = frames / fps
    port_types = graph.get("ports") or {}
    curves: dict[str, Callable[[float], Any]] = {}
    clips: dict[str, np.ndarray] = {}
    for name, value in inputs.items():
        if callable(value):
            curves[name] = value
        elif isinstance(value, np.ndarray):
            clips[name] = value if value.ndim == 4 else np.repeat(value[None], frames, axis=0)
        else:
            clips[name] = read(Path(value), frames, size, fps, working=working)
    for name, kind in port_types.items():
        if kind == "curve" and name not in curves:
            curves[name] = lambda seconds: seconds / length if length else 0.0  # a join's progress, by default
        elif kind in ("picture", "matte") and name not in clips:
            raise ValidationError(f"The graph's port {name!r} was given no {kind}")

    def curve(reference: str) -> Callable[[float], Any]:
        if reference in curves:
            return curves[reference]
        node = nodes[reference]
        op = node["op"]
        if op == "curve.progress":
            made = lambda seconds: seconds / length if length else 0.0  # noqa: E731
        elif op == "curve.keys":
            made = keys_curve(node["keys"])
        elif op == "curve.noise":
            made = noise_curve(int(node.get("seed", 0)), float(node.get("frequency", 1.0)),
                               float(node.get("amplitude", 1.0)), float(node.get("offset", 0.0)))
        elif op == "curve.map":
            source, how = curve(node["in"]), node["how"]
            low, high = float(node.get("low", 0.0)), float(node.get("high", 1.0))
            out_low, out_high = float(node.get("out_low", 0.0)), float(node.get("out_high", 1.0))
            factor = float(node.get("factor", 1.0))
            ease = _EASES.get(str(node.get("ease", "in-out")), _EASES["linear"])
            mapping = {
                "invert": lambda x: 1.0 - x,
                "scale": lambda x: x * factor,
                "offset": lambda x: x + factor,
                "clamp": lambda x: np.clip(x, low, high),
                "remap": lambda x: out_low + (out_high - out_low) * np.clip((x - low) / ((high - low) or 1e-9), 0, 1),
                "ease": lambda x: ease(float(np.clip(x, 0, 1))),
            }[how]
            made = lambda seconds: mapping(source(seconds))  # noqa: E731
        elif op == "curve.combine":
            a, b = curve(node["a"]), curve(node["b"])
            how = {"add": np.add, "subtract": np.subtract, "multiply": np.multiply, "min": np.minimum,
                   "max": np.maximum}[node["how"]]
            made = lambda seconds: how(a(seconds), b(seconds))  # noqa: E731
        else:
            raise ValidationError(f"{reference} is not a curve")
        curves[reference] = made
        return made

    def value(reference: str, frame: int) -> Any:
        if reference in clips:
            return clips[reference][frame]
        if reference in curves or nodes.get(reference, {}).get("op", "").startswith("curve."):
            return curve(reference)((frame + 0.5) / fps)
        key = (reference, frame)
        if key not in context.cache:
            context.cache[key] = compute(reference, frame)
        return context.cache[key]

    def compute(name: str, frame: int) -> Any:
        node = nodes[name]
        op = node["op"]
        seconds = (frame + 0.5) / fps

        def param(key: str, default: Any = None) -> Any:
            given = node.get(key, default)
            if isinstance(given, dict) and "curve" in given:
                return curve(given["curve"])(seconds)
            return given

        if op == "generate.source":
            if name not in clips:
                path = Path(node.get("file") or node.get("take"))
                path = (root / path) if root and not path.is_absolute() else path
                clips[name] = read(path, frames, size, fps, start=float(node.get("start", 0.0)),
                                   colorspace=node.get("colorspace", ENCODED), alpha=node.get("alpha", "straight"),
                                   working=working)
            return clips[name][frame]
        if op == "generate.solid":
            colour = np.asarray(param("colour"), dtype=np.float32)
            rgba = np.concatenate([colour[:3], colour[3:4] if colour.size > 3 else [1.0]]).astype(np.float32)
            rgba[:3] *= rgba[3]
            return np.broadcast_to(rgba, (height, width, 4)).copy()
        if op == "generate.gradient":
            colours = np.asarray(param("colours", [[0, 0, 0, 1], [1, 1, 1, 1]]), dtype=np.float32)
            ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
            if param("kind", "linear") == "radial":
                x = np.hypot((xs + 0.5) / width - 0.5, (ys + 0.5) / height - 0.5) / math.hypot(0.5, 0.5)
            else:
                angle = math.radians(float(param("angle", 0.0)))
                x = ((xs + 0.5) / width - 0.5) * math.cos(angle) + ((ys + 0.5) / height - 0.5) * math.sin(angle) + 0.5
            x = np.clip(x, 0, 1)[..., None]
            out = colours[0] * (1 - x) + colours[-1] * x
            out[..., :3] *= out[..., 3:4]
            return out.astype(np.float32)
        if op in ("signal.luminance", "signal.luma"):
            picture = _picture(value(node["picture"], frame))
            alpha = picture[..., 3:4]
            straight = np.divide(picture[..., :3], alpha, out=np.zeros_like(picture[..., :3]), where=alpha > 1e-6)
            weights = np.asarray(node.get("weights") or REC709, dtype=np.float32)
            if op == "signal.luma":  # from encoded values: what video calls Y' (SPEC-0012 §2)
                straight = convert(straight, working, ENCODED)
            return (straight @ weights).astype(np.float32)
        if op == "signal.channel":
            picture = _picture(value(node["picture"], frame))
            index = {"red": 0, "green": 1, "blue": 2, "alpha": 3}.get(node["channel"])
            if index is None:
                raise ValidationError(f"The reference does not yet give {node['channel']} as a signal")
            return picture[..., index].copy()
        if op == "matte.from_signal":
            signal = value(node["signal"], frame)
            signal = signal if signal.ndim == 2 else signal[..., 0]
            low, high = float(param("low", 0.0)), float(param("high", 1.0))
            out = np.clip((signal - low) / ((high - low) or 1e-9), 0.0, 1.0) ** float(param("gamma", 1.0))
            return (1.0 - out if node.get("invert") else out).astype(np.float32)
        if op == "matte.threshold":
            matte = _matte(value(node["matte"], frame))
            spread = max(float(param("softness", 0.0) or 0.0), 0.002)
            progress = float(value(node["progress"], frame))
            # Progress spread so that 0 shows nothing and 1 everything, whatever the matte (SPEC-0011's rule).
            p = progress * (1 + 2 * spread) - spread
            return np.clip((p - matte) / (2 * spread) + 0.5, 0.0, 1.0).astype(np.float32)
        if op == "matte.combine":
            a, b = _matte(value(node["a"], frame)), _matte(value(node["b"], frame))
            return {"union": np.maximum(a, b), "intersect": np.minimum(a, b), "subtract": np.clip(a - b, 0, 1),
                    "multiply": a * b}[node["how"]].astype(np.float32)
        if op == "matte.shape":
            return _shape(node, size, float(param("size", 1.0)))
        if op == "matte.key":
            picture = _picture(value(node["picture"], frame))
            by = node["by"]
            alpha = picture[..., 3:4]
            straight = np.divide(picture[..., :3], alpha, out=np.zeros_like(picture[..., :3]), where=alpha > 1e-6)
            if by in ("luminance", "luma"):
                signal = (convert(straight, working, ENCODED) if by == "luma" else straight) @ np.asarray(REC709)
                low, high = float(param("low")), float(param("high"))
                key = np.clip((signal - low) / ((high - low) or 1e-9), 0, 1)
            else:
                raise ValidationError(f"The reference does not yet key by {by}")
            return (1.0 - key if node.get("invert") else key).astype(np.float32)
        if op == "merge.over":
            front, back = _picture(value(node["front"], frame)), _picture(value(node["back"], frame))
            if node.get("matte"):
                front = front * _matte(value(node["matte"], frame))[..., None]
            front = front * float(param("mix", 1.0))
            return (front + back * (1.0 - front[..., 3:4])).astype(np.float32)
        if op == "merge.mix":
            a, b = _picture(value(node["a"], frame)), _picture(value(node["b"], frame))
            by = value(node["by"], frame)
            weight = _matte(by)[..., None] if isinstance(by, np.ndarray) else float(by)
            return (a * (1 - weight) + b * weight).astype(np.float32)
        if op == "merge.porter_duff":
            a, b = _picture(value(node["a"], frame)), _picture(value(node["b"], frame))
            aa, ba = a[..., 3:4], b[..., 3:4]
            return {"over": a + b * (1 - aa), "under": b + a * (1 - ba), "in": a * ba, "out": a * (1 - ba),
                    "atop": a * ba + b * (1 - aa), "xor": a * (1 - ba) + b * (1 - aa)}[node["how"]].astype(np.float32)
        if op == "merge.blend":
            a, b = _picture(value(node["a"], frame)), _picture(value(node["b"], frame))
            mode = node["mode"]
            blended = {"screen": a + b - a * b, "add": a + b, "multiply": a * b, "lighten": np.maximum(a, b),
                       "darken": np.minimum(a, b), "difference": np.abs(a - b),
                       "overlay": np.where(a < 0.5, 2 * a * b, 1 - 2 * (1 - a) * (1 - b))}[mode]
            mix = float(param("mix", 1.0))
            out = a * (1 - mix) + blended * mix
            out[..., 3] = np.maximum(a[..., 3], b[..., 3])
            return out.astype(np.float32)
        if op == "merge.channels":
            out = np.zeros((height, width, 4), dtype=np.float32)
            out[..., 3] = 1.0
            for index, channel in enumerate(("red", "green", "blue", "alpha")):
                if node.get(channel):
                    given = value(node[channel], frame)
                    out[..., index] = given if given.ndim == 2 else given[..., 0]
            return out
        if op == "warp.transform":
            return _affine(value(node["in"], frame), node, param)
        if op == "colour.grade":
            picture = _picture(value(node["in"], frame)).copy()
            alpha = picture[..., 3:4]
            rgb = np.divide(picture[..., :3], alpha, out=np.zeros_like(picture[..., :3]), where=alpha > 1e-6)
            lift = np.asarray(param("lift", 0.0), dtype=np.float32)
            gain = np.asarray(param("gain", 1.0), dtype=np.float32)
            gamma = np.asarray(param("gamma", 1.0), dtype=np.float32)
            rgb = np.clip(rgb * gain + lift * (1 - rgb), 0, None) ** (1.0 / gamma)
            saturation = float(param("saturation", 1.0))
            grey = (rgb @ np.asarray(REC709, dtype=np.float32))[..., None]
            rgb = grey + (rgb - grey) * saturation
            picture[..., :3] = rgb * alpha
            return picture
        if op == "colour.invert":
            given = value(node["in"], frame)
            if given.ndim == 2:
                return 1.0 - given
            alpha = given[..., 3:4]
            out = given.copy()
            out[..., :3] = alpha - given[..., :3]  # 1 - colour, kept premultiplied
            return out
        if op == "filter.blur":
            return _blur(value(node["in"], frame), float(param("radius", 0.0)))
        raise ValidationError(f"The reference does not implement {op}")

    output = graph["output"]
    return np.stack([_picture(value(output, frame)) for frame in range(frames)]).astype(np.float32)
