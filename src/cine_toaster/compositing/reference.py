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


class Clip:
    """A clip read once into a file on disk, each frame converted to the working space when it is asked for.

    At 1080 lines a second of float RGBA is a gigabyte; held whole, a few clips and every node's frame
    exhausted memory (CT-0071). Here the decoded 16-bit frames live in a memory-mapped file, and only the
    frames in use are ever floats.
    """

    def __init__(self, raw: np.ndarray, colorspace: str, alpha: str, working: str) -> None:
        self.raw, self.colorspace, self.alpha, self.working = raw, colorspace, alpha, working
        self.shape = (raw.shape[0],) + raw.shape[1:3] + (4,)

    def __len__(self) -> int:
        return self.shape[0]

    def release_before(self, frame: int) -> None:
        """Let the kernel drop the pages of frames no longer needed; they are read again from disk if asked."""

        _drop_pages(self.raw, frame)

    def frame(self, index: int) -> np.ndarray:
        data = np.asarray(self.raw[min(index, len(self) - 1)], dtype=np.float32) / 65535.0
        rgb = convert(data[..., :3], self.colorspace, self.working)
        if self.alpha == "straight":
            rgb = rgb * data[..., 3:4]
        return np.concatenate([rgb, data[..., 3:4]], axis=-1).astype(np.float32)

    def __getitem__(self, key: Any) -> np.ndarray:
        if isinstance(key, tuple):
            return self.frame(int(key[0]))[key[1:]]
        return self.frame(int(key))


def _drop_pages(array: np.ndarray, frame: int) -> None:
    """Advise the kernel that a memory-mapped array's frames before ``frame`` are not needed for now."""

    import mmap

    handle = getattr(array, "_mmap", None)
    if handle is None or frame <= 0 or not hasattr(handle, "madvise"):
        return
    per_frame = int(np.prod(array.shape[1:])) * array.dtype.itemsize
    header = getattr(array, "offset", 0)
    end = (header + frame * per_frame) // mmap.PAGESIZE * mmap.PAGESIZE
    if end > 0:
        try:
            handle.madvise(mmap.MADV_DONTNEED, 0, end)
        except (OSError, ValueError):  # advice only: if refused, the pages stay and nothing is lost
            pass


def read(path: Path, frames: int, size: tuple[int, int], fps: float, *, start: float = 0.0,
         colorspace: str = ENCODED, alpha: str = "straight", working: str = LINEAR) -> Clip:
    """A clip or a still, `frames` long, in the working space and premultiplied when used (SPEC-0012 §2)."""

    import tempfile

    width, height = size
    still = Path(path).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".exr", ".tif", ".tiff")
    source = ["-loop", "1", "-framerate", f"{fps:g}"] if still else ["-ss", f"{start:.4f}"]
    process = subprocess.Popen(
        [_ffmpeg(), "-loglevel", "error", *source, "-i", str(path), "-frames:v", str(frames),
         "-vf", f"fps={fps:g},scale={width}:{height}:flags=bicubic", "-f", "rawvideo", "-pix_fmt", "rgba64le", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    handle = tempfile.NamedTemporaryFile(prefix="clip-", suffix=".raw", delete=False)
    stored = np.lib.format.open_memmap(handle.name, mode="w+", dtype="<u2", shape=(frames, height, width, 4))
    Path(handle.name).unlink()  # the mapping keeps it; nothing is left behind
    handle.close()
    size_bytes, count = width * height * 4 * 2, 0
    while count < frames:
        chunk = process.stdout.read(size_bytes)
        if len(chunk) < size_bytes:
            break
        stored[count] = np.frombuffer(chunk, dtype="<u2").reshape(height, width, 4)
        count += 1
        if count % 16 == 0:  # written frames are flushed to the file and their pages let go
            stored.flush()
            _drop_pages(stored, count)
    process.stdout.close()
    error = process.stderr.read().decode()
    process.wait(timeout=60)
    if count == 0:
        raise ValidationError(f"Reading {Path(path).name} gave no frames: {error[-300:]}")
    for index in range(count, frames):  # a clip shorter than the extent holds its last frame
        stored[index] = stored[count - 1]
    return Clip(stored, colorspace, alpha, working)


def write(pictures: Any, destination: Path, fps: float, *, working: str = LINEAR,
          display: str = ENCODED) -> Path:
    """Frames (an array or any sequence of (H, W, 4)), linear premultiplied, to H.264 in the display encoding.

    Written as they come, so a long composite never has to be in memory at once.
    """

    frames = iter(pictures)
    first = next(frames)
    height, width = first.shape[:2]
    process = subprocess.Popen(
        [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb48le", "-s", f"{width}x{height}",
         "-r", f"{fps:g}", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv444p",
         str(destination)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for picture in _chain(first, frames):
            rgb = convert(np.clip(np.asarray(picture, dtype=np.float32)[..., :3], 0.0, None), working, display)
            process.stdin.write((np.clip(rgb, 0.0, 1.0) * 65535.0 + 0.5).astype("<u2").tobytes())
        process.stdin.close()
        if process.wait(timeout=900) != 0:
            raise ValidationError(f"Writing {destination.name} failed: {process.stderr.read().decode()[-300:]}")
    finally:
        if process.poll() is None:
            process.kill()
        process.stderr.close()
    return destination


def _chain(first: Any, rest: Any):
    yield first
    yield from rest


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
    #: Frames of node values kept behind the one being made, from what the graph's time operations reach
    #: back (`temporal_window`); older ones are computed again when asked for. Memory is bounded by the
    #: graph and this window, never by the length.
    window: int = 0
    #: A ceiling on the bytes of node values held in memory; past it the oldest frames go first, never the
    #: frame being made. None: only the window bounds it.
    budget: int | None = None


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


IMPLEMENTED = {
    "generate.source", "generate.solid", "generate.gradient", "generate.noise", "generate.text",
    "signal.luminance", "signal.luma", "signal.channel", "signal.read", "signal.align_depth",
    "matte.from_signal", "matte.threshold", "matte.combine", "matte.shape", "matte.key", "matte.label",
    "merge.over", "merge.mix", "merge.blend", "merge.porter_duff", "merge.channels", "merge.depth",
    "warp.transform", "warp.corner_pin", "warp.displace", "warp.procedural",
    "colour.grade", "colour.invert", "colour.curve", "colour.lut", "colour.posterise", "colour.solarise",
    "colour.cycle",
    "filter.blur", "filter.sharpen", "filter.glow", "filter.edges", "filter.morphology", "filter.noise",
    "time.remap", "time.offset", "time.blend", "time.echo",
    "track.read", "track.measure",
    "curve.progress", "curve.keys", "curve.map", "curve.combine", "curve.noise", "curve.beats", "curve.from_track",
}
#: In SPEC-0012 but outside the reference, by definition (opaque) or until a renderer gives them (models, 3D).
NOT_IN_REFERENCE = {"signal.estimate": "a model's result is recorded, not computed by the reference",
                    "generate.render": "a renderer's own scene; its result is recorded"}


def Image_resize(data: np.ndarray, width: int, height: int) -> np.ndarray:
    """A float array resized to the frame, channel by channel (signals are not pictures to encode)."""

    from PIL import Image

    planes = data if data.ndim == 3 else data[..., None]
    out = np.stack([np.asarray(Image.fromarray(planes[..., index].astype(np.float32), "F").resize(
        (width, height), Image.BILINEAR)) for index in range(planes.shape[-1])], axis=-1)
    return out if data.ndim == 3 else out[..., 0]


def node_windows(graph: dict[str, Any]) -> dict[str, int]:
    """For each node a time operation reads, how many frames back it is read; every other node needs only
    the frame being made. Kept per node, so a long echo holds its input's past, not the whole graph's."""

    reach: dict[str, int] = {}
    for node in (graph.get("nodes") or {}).values():
        op, source = node.get("op"), str(node.get("in") or "").split(".")[0]
        back = 0
        if op == "time.offset" and isinstance(node.get("frames"), int):
            back = abs(node["frames"])
        elif op == "time.echo":
            back = int(node.get("count", 4)) * int(node.get("spacing", 1))
        elif op == "time.blend":
            back = int(node.get("frames", 2))
        if back and source:
            reach[source] = max(reach.get(source, 0), back)
    return reach


def temporal_window(graph: dict[str, Any]) -> int:
    """How many frames back the graph's time operations read, so their inputs stay in memory that long.

    Each node's value is kept for the frame being made (two nodes reading one result share it); a node
    behind an offset, an echo or a blend is kept as far back as those reach. A remap may reach anywhere:
    what it asks for beyond the window is computed again rather than kept.
    """

    reach = 0
    for node in (graph.get("nodes") or {}).values():
        op = node.get("op")
        if op == "time.offset" and isinstance(node.get("frames"), int):
            reach = max(reach, abs(node["frames"]))
        elif op == "time.echo":
            reach = max(reach, int(node.get("count", 4)) * int(node.get("spacing", 1)))
        elif op == "time.blend":
            reach = max(reach, int(node.get("frames", 2)))
    return reach


class _Held:
    """One picture standing for every frame, without copying it once per frame."""

    def __init__(self, picture: np.ndarray, frames: int) -> None:
        self.picture, self.shape = picture, (frames,) + picture.shape

    def __getitem__(self, key: Any) -> np.ndarray:
        return self.picture[key[1:]] if isinstance(key, tuple) else self.picture


def evaluate(graph: dict[str, Any], inputs: dict[str, Any], *, frames: int, size: tuple[int, int], fps: float,
             working: str = LINEAR, root: Path | None = None, beats: list[float] | None = None,
             stream: bool = False, stats: dict[str, int] | None = None, budget: int | None = None) -> Any:
    """The graph's output picture for every frame of its extent: (frames, H, W, 4), linear, premultiplied.

    With ``stream``, a generator of frames instead, made one at a time: memory stays bounded by the
    graph and a few frames, not by the length.

    Four things are kept apart (SPEC-0012 §5): a node's **identity** says whether a result can be reused;
    the **persistent cache** (`render`) keeps results between runs, on disk; the **resident** values here
    hold what the frame being made and the time operations' window need, within an optional ``budget`` in
    bytes; and a value's **lifetime** ends when nothing still to be made needs it, whether or not the
    persistent cache has it. ``stats`` receives what was kept at most (entries, bytes), hits, misses and
    recomputations.

    ``beats`` are the scene music's beats in seconds from the extent's start (CT-0067), for `curve.beats`.
    An input that is a recorded result of `signal.estimate` or `generate.render` is given like any other.
    """

    problems = validate(graph)
    if problems:
        raise ValidationError("The graph is not valid: " + "; ".join(message for _, message in problems))
    nodes = graph["nodes"]
    missing = sorted({node["op"] for node in nodes.values() if node["op"] not in IMPLEMENTED})
    if missing:
        why = "; ".join(f"{op}: {NOT_IN_REFERENCE[op]}" for op in missing if op in NOT_IN_REFERENCE)
        raise ValidationError(f"The reference does not implement {', '.join(missing)}" + (f" ({why})" if why else " yet"))
    aspect = size[0] / size[1]
    context = Context(size, fps, frames, working, root, window=temporal_window(graph), budget=budget)
    counts = {"hits": 0, "misses": 0, "recomputed": 0}
    windows = node_windows(graph)
    made_once: set[tuple[str, int]] = set()
    width, height = size
    length = frames / fps
    port_types = graph.get("ports") or {}

    def port_kind(name: str) -> str:
        return str(port_types.get(name, ""))
    curves: dict[str, Callable[[float], Any]] = {}
    clips: dict[str, np.ndarray] = {}
    for name, value in inputs.items():
        if isinstance(value, dict):  # a track, as data
            continue
        if callable(value):
            curves[name] = value
        elif isinstance(value, Clip):
            clips[name] = value
        elif isinstance(value, np.ndarray):
            per_frame = value.ndim == 4 or (port_kind(name) == "signal" and value.ndim == 3 and value.shape[0] == frames)
            clips[name] = value if per_frame else _Held(value, frames)
        else:
            clips[name] = read(Path(value), frames, size, fps, working=working)
    for name, kind in port_types.items():
        if kind == "curve" and name not in curves:
            curves[name] = lambda seconds: seconds / length if length else 0.0  # a join's progress, by default
        elif kind in ("picture", "matte", "signal") and name not in clips:
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
        elif op == "curve.beats":
            times = list(beats or [])[:: max(int(node.get("every", 1) or 1), 1)]
            attack, decay = float(node.get("attack", 0.02)), float(node.get("decay", 0.2))
            low, high = float(node.get("low", 0.0)), float(node.get("high", 1.0))

            def made(seconds: float) -> float:
                level = 0.0
                for beat in times:
                    d = seconds - beat
                    if -attack < d < 0:
                        level = max(level, 1 + d / attack)
                    elif 0 <= d < decay:
                        level = max(level, 1 - d / decay)
                return low + (high - low) * level
        elif op == "curve.from_track":
            track, field = tracks(node["track"]), node["field"]

            def made(seconds: float) -> Any:
                frame = track["frames"][min(int(seconds * fps), len(track["frames"]) - 1)]
                points = np.asarray(frame.get("points") or frame.get("corners"), dtype=np.float32)
                if field in ("x", "y"):
                    return float(points.mean(axis=0)[0 if field == "x" else 1])
                first = np.asarray(track["frames"][0].get("points") or track["frames"][0].get("corners"))
                if len(points) < 2:
                    return 0.0 if field == "rotation" else 1.0
                now, then = points[1] - points[0], first[1] - first[0]
                if field == "rotation":
                    return math.degrees(math.atan2(now[1], now[0]) - math.atan2(then[1], then[0]))
                return float(np.hypot(*now) / max(np.hypot(*then), 1e-9))
        elif op == "curve.combine":
            a, b = curve(node["a"]), curve(node["b"])
            how = {"add": np.add, "subtract": np.subtract, "multiply": np.multiply, "min": np.minimum,
                   "max": np.maximum}[node["how"]]
            made = lambda seconds: how(a(seconds), b(seconds))  # noqa: E731
        else:
            raise ValidationError(f"{reference} is not a curve")
        curves[reference] = made
        return made

    track_cache: dict[str, dict[str, Any]] = {}

    def tracks(reference: str) -> dict[str, Any]:
        """A track as data (SPEC-0012 §1): {kind, frames: [{points} or {corners}]}."""

        if reference in track_cache:
            return track_cache[reference]
        if reference in inputs and isinstance(inputs[reference], dict):
            track_cache[reference] = inputs[reference]
            return track_cache[reference]
        node = nodes[reference]
        if node["op"] == "track.read":
            import json

            path = Path(node["file"])
            path = (root / path) if root and not path.is_absolute() else path
            track_cache[reference] = json.loads(path.read_text(encoding="utf-8"))
        else:  # track.measure
            from .tracking import measure

            # Frame by frame: tracking holds two frames, not the clip (CT-0071).
            track_cache[reference] = measure(lambda index: _picture(value(node["in"], index)), node["kind"],
                                             node.get("region"), working, frames=frames)
        return track_cache[reference]

    def value(reference: str, frame: int) -> Any:
        if reference in clips:
            return clips[reference][frame]
        if reference in curves or nodes.get(reference, {}).get("op", "").startswith("curve."):
            return curve(reference)((frame + 0.5) / fps)
        key = (reference, frame)
        if key in context.cache:
            counts["hits"] += 1
            return context.cache[key]
        counts["misses"] += 1
        if key in made_once:
            counts["recomputed"] += 1  # dropped by the window or the budget, and asked for again
        made_once.add(key)
        result = compute(reference, frame)
        context.cache[key] = result
        if context.budget is not None:
            while resident() > context.budget:
                older = [held for held in context.cache if held[1] < frame]
                if not older:
                    break
                del context.cache[min(older, key=lambda held: held[1])]
        return result

    def resident() -> int:
        return sum(getattr(held, "nbytes", 0) for held in context.cache.values())

    def forget_before(frame: int) -> None:
        # A value is dropped once no frame still to be made reaches back to it: per node, not graph-wide.
        for key in [key for key in context.cache if key[1] <= frame - 1 - windows.get(key[0], 0)]:
            del context.cache[key]

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
            from .warp import transform

            angles = param("rotate", 0.0)
            return transform(value(node["in"], frame), translate=param("translate", [0.0, 0.0]),
                             scale=param("scale", [1.0, 1.0]), rotate=angles if angles is not None else 0.0,
                             pivot=param("pivot", [0.5, 0.5]), perspective=float(param("perspective", 0.0) or 0.0),
                             aspect=aspect)
        if op == "warp.corner_pin":
            from .warp import corner_pin

            if node.get("track"):
                track = tracks(node["track"])
                entry = track["frames"][min(frame, len(track["frames"]) - 1)]
                first = track["frames"][0]
                if "corners" in entry:
                    corners = entry["corners"]
                else:  # a point track moves the picture with it
                    shift = np.mean(entry["points"], axis=0) - np.mean(first["points"], axis=0)
                    corners = (np.asarray(node.get("corners") or [[0, 0], [1, 0], [1, 1], [0, 1]]) + shift).tolist()
            else:
                corners = param("corners")
            return corner_pin(value(node["in"], frame), [list(map(float, corner)) for corner in corners], aspect)
        if op == "warp.displace":
            from .warp import displace

            return displace(value(node["in"], frame), value(node["map"], frame), float(param("strength", 0.1)),
                            param("direction"), str(node.get("edge", "transparent")))
        if op == "warp.procedural":
            from .warp import procedural

            return procedural(value(node["in"], frame), node["kind"], float(param("amount", 1.0)),
                              float(param("frequency", 4.0)), param("centre"), aspect,
                              str(node.get("edge", "transparent")))
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
        return more(name, node, op, frame, seconds, param, value)

    def more(name: str, node: dict[str, Any], op: str, frame: int, seconds: float, param, value) -> Any:
        """The ops of the second slice (CT-0071): generators, signals from files, depth, colour, filters, time."""

        def straight(picture: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            alpha = picture[..., 3:4]
            return np.divide(picture[..., :3], alpha, out=np.zeros_like(picture[..., :3]), where=alpha > 1e-6), alpha

        def rebuilt(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
            return np.concatenate([rgb * alpha, alpha], axis=-1).astype(np.float32)

        if op == "generate.noise":
            seed = int(param("seed", 0) or 0)
            kind = param("kind", "value")
            if kind == "grain":
                grey = np.random.default_rng([seed, frame]).normal(0.5, 0.15, (height, width)).astype(np.float32)
            else:
                cells = max(1.0, float(param("scale", 8.0)))
                from PIL import Image

                coarse = np.random.default_rng(seed).uniform(0, 1, (int(cells * height / width) + 2, int(cells) + 2))
                grey = np.asarray(Image.fromarray(coarse.astype(np.float32), "F").resize((width, height),
                                                                                         Image.BICUBIC))
            grey = np.clip(grey, 0, 1).astype(np.float32)
            return np.stack([grey, grey, grey, np.ones_like(grey)], axis=-1)
        if op == "generate.text":
            from PIL import Image, ImageDraw, ImageFont

            from ..titles import font_file

            text = str(param("text", ""))
            reveal = param("reveal", 1.0)
            shown = text[: int(round(len(text) * float(np.clip(reveal, 0, 1))))] if reveal is not None else text
            size_px = max(4, int(float(param("size", 40)) * height / 720 * 4))
            font = ImageFont.truetype(font_file({"font": node.get("font") or ""}, root), size_px)
            canvas = Image.new("L", (width * 4, height * 4), 0)
            draw = ImageDraw.Draw(canvas)
            position = np.broadcast_to(np.asarray(param("position", [0.5, 0.5]), dtype=np.float32), (2,))
            box = draw.textbbox((0, 0), text, font=font)  # placed by the whole text, so letters do not shift
            x = position[0] * width * 4 - (box[2] - box[0]) / 2 - box[0]
            y = position[1] * height * 4 - (box[3] - box[1]) / 2 - box[1]
            draw.text((x, y), shown, font=font, fill=255)
            coverage = np.asarray(canvas.resize((width, height), Image.BOX), dtype=np.float32) / 255.0
            colour = np.asarray(param("colour", [1, 1, 1, 1]), dtype=np.float32)
            alpha = coverage * (colour[3] if colour.size > 3 else 1.0)
            return np.concatenate([colour[:3] * alpha[..., None], alpha[..., None]], axis=-1).astype(np.float32)
        if op == "signal.read":
            path = Path(node["file"])
            path = (root / path) if root and not path.is_absolute() else path
            key = f"read:{name}"
            if key not in clips:
                if path.suffix.lower() == ".exr":
                    from ..color import read_exr

                    data = read_exr(path)
                    data = np.asarray(Image_resize(data, width, height))
                elif path.suffix.lower() == ".npy":
                    data = np.load(path).astype(np.float32)
                else:
                    data = read(path, 1, size, fps, colorspace=LINEAR, alpha="premultiplied", working=LINEAR)[0]
                kind = node["kind"]
                channels = {"vectors": 2, "normals": 3}.get(kind, 1)
                if data.ndim == 3:
                    data = data[..., :channels] if channels > 1 else data[..., 0]
                clips[key] = data.astype(np.float32 if kind != "segmentation" else np.int64)
            return clips[key]
        if op == "signal.align_depth":
            relative = value(node["signal"], frame).astype(np.float64)
            if node.get("inverse"):
                relative = 1.0 / np.maximum(relative, 1e-6)
            if (node.get("method") or "scale_shift") == "manual":
                return (relative * float(node["scale"]) + float(node["shift"])).astype(np.float32)
            reference = value(node["reference"], frame).astype(np.float64)
            region = _matte(value(node["region"], frame)) > 0.5 if node.get("region") else np.isfinite(reference)
            a = np.stack([relative[region], np.ones(int(region.sum()))], axis=1)
            scale, shift = np.linalg.lstsq(a, reference[region], rcond=None)[0]
            return (relative * scale + shift).astype(np.float32)
        if op == "matte.label":
            labels = value(node["signal"], frame)
            return np.isin(np.rint(labels).astype(np.int64), np.asarray(node["labels"], dtype=np.int64)).astype(
                np.float32)
        if op == "merge.depth":
            pictures = np.stack([_picture(value(item, frame)) for item in node["pictures"]])
            depths = np.stack([value(item, frame) for item in node["depths"]])
            if not node.get("near_is_small", True):
                depths = -depths
            order = np.argsort(depths, axis=0)  # nearest first, per pixel
            out = np.zeros(pictures.shape[1:], dtype=np.float32)
            for rank in range(pictures.shape[0] - 1, -1, -1):  # far to near, each over what is behind it
                layer = np.take_along_axis(pictures, order[rank][None, ..., None].repeat(4, axis=-1), axis=0)[0]
                out = layer + out * (1 - layer[..., 3:4])
            return out
        if op == "colour.curve":
            given = value(node["in"], frame)
            points = np.asarray(node.get("points") or [[0, 0], [1, 1]], dtype=np.float32)
            curve_of = lambda x: np.interp(x, points[:, 0], points[:, 1]).astype(np.float32)  # noqa: E731
            if given.ndim == 2:
                return curve_of(given)
            rgb, alpha = straight(given)
            return rebuilt(curve_of(rgb), alpha)
        if op == "colour.lut":
            rgb, alpha = straight(_picture(value(node["in"], frame)))
            from ..color import config

            import PyOpenColorIO as ocio

            if node.get("look"):
                transform = ocio.LookTransform(src=working, dst=working, looks=node["look"])
                processor = config().getProcessor(transform).getDefaultCPUProcessor()
                flat = np.ascontiguousarray(rgb.reshape(-1, 3), dtype=np.float32)
                processor.applyRGB(flat)
                return rebuilt(flat.reshape(rgb.shape), alpha)
            path = Path(node["file"])
            path = (root / path) if root and not path.is_absolute() else path
            # A .cube is made for encoded pictures: applied in the display encoding, then back to linear.
            processor = config().getProcessor(ocio.FileTransform(src=str(path))).getDefaultCPUProcessor()
            flat = np.ascontiguousarray(convert(rgb, working, ENCODED).reshape(-1, 3), dtype=np.float32)
            processor.applyRGB(flat)
            return rebuilt(convert(flat.reshape(rgb.shape), ENCODED, working), alpha)
        if op in ("colour.posterise", "colour.solarise"):
            rgb, alpha = straight(_picture(value(node["in"], frame)))
            encoded = convert(rgb, working, ENCODED)
            if op == "colour.posterise":
                levels = max(2, int(param("levels", 4)))
                encoded = np.round(np.clip(encoded, 0, 1) * (levels - 1)) / (levels - 1)
            else:
                threshold = float(param("threshold", 0.5))
                encoded = np.where(encoded > threshold, 1 - encoded, encoded)
            return rebuilt(convert(encoded.astype(np.float32), ENCODED, working), alpha)
        if op == "colour.cycle":
            rgb, alpha = straight(_picture(value(node["in"], frame)))
            angle = math.radians(float(param("speed", 90.0)) * seconds)  # hue turned, degrees per second
            cos, sin = math.cos(angle), math.sin(angle)
            k = np.ones(3, dtype=np.float32) / math.sqrt(3)
            matrix = (cos * np.eye(3) + sin * np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
                      + (1 - cos) * np.outer(k, k))
            return rebuilt(np.clip(rgb @ matrix.T.astype(np.float32), 0, None), alpha)
        if op == "filter.sharpen":
            picture = _picture(value(node["in"], frame))
            return np.clip(picture + float(param("amount", 0.5)) * (picture - _blur(picture, 2.0)), 0, None)
        if op == "filter.glow":
            picture = _picture(value(node["in"], frame))
            rgb, alpha = straight(picture)
            bright = np.clip(rgb @ np.asarray(REC709, dtype=np.float32) - float(param("threshold", 0.8)), 0, None)
            halo = _blur(picture[..., :3] * (bright > 0)[..., None], float(param("radius", 8.0)))
            out = picture.copy()
            out[..., :3] += halo * float(param("intensity", 1.0))
            return out
        if op == "filter.edges":
            rgb, _ = straight(_picture(value(node["in"], frame)))
            grey = rgb @ np.asarray(REC709, dtype=np.float32)
            gy, gx = np.gradient(grey)
            return np.clip(np.hypot(gx, gy) * 4, 0, 1).astype(np.float32)
        if op == "filter.morphology":
            matte = _matte(value(node["in"], frame))
            radius = max(0, int(round(float(param("radius", 1.0)))))
            padded = np.pad(matte, radius, mode="edge")
            stack = [padded[dy:dy + height, dx:dx + width] for dy in range(2 * radius + 1)
                     for dx in range(2 * radius + 1)]
            return (np.min(stack, axis=0) if node["operation"] == "erode" else np.max(stack, axis=0)).astype(
                np.float32)
        if op == "filter.noise":
            picture = _picture(value(node["in"], frame))
            grain = np.random.default_rng([int(param("seed", 0) or 0), frame]).normal(0, 1, (height, width))
            grain = _blur(grain.astype(np.float32), max(float(param("size", 1.0)) - 1.0, 0.0))
            out = picture.copy()
            out[..., :3] = np.clip(picture[..., :3] + grain[..., None] * float(param("amount", 0.1)) * 0.1
                                   * picture[..., 3:4], 0, None)
            return out
        if op in ("time.remap", "time.offset"):
            if op == "time.offset":
                source_frame = frame - int(param("frames", 0))
            else:
                source_frame = int(round(float(param("map", seconds)) * fps - 0.5))
            return value(node["in"], int(np.clip(source_frame, 0, frames - 1)))
        if op == "time.blend":
            span = max(1, int(param("frames", 2)))
            around = [int(np.clip(frame + offset, 0, frames - 1)) for offset in range(-(span // 2), span - span // 2)]
            return np.mean([_picture(value(node["in"], item)) for item in around], axis=0).astype(np.float32)
        if op == "time.echo":
            count, spacing = int(param("count", 4)), max(1, int(param("spacing", 1)))
            decay = float(param("decay", 0.5))
            out = np.zeros((height, width, 4), dtype=np.float32)
            for index in range(count, -1, -1):  # the oldest echo first, the present last, on top
                earlier = frame - index * spacing
                if earlier < 0:
                    continue
                out = (_picture(value(node["in"], earlier)) * decay ** index) + out * (
                    1 - _picture(value(node["in"], earlier))[..., 3:4] * decay ** index)
            return out
        raise ValidationError(f"The reference does not implement {op}")

    output = graph["output"]

    def each() -> Any:
        for frame in range(frames):
            yield np.asarray(_picture(value(output, frame)), dtype=np.float32)
            if stats is not None:
                stats["most_kept"] = max(stats.get("most_kept", 0), len(context.cache))
                stats["most_kept_bytes"] = max(stats.get("most_kept_bytes", 0), resident())
            forget_before(frame + 1)
            for clip in clips.values():
                if isinstance(clip, Clip):
                    clip.release_before(frame + 1 - context.window)
        if stats is not None:
            stats.update(counts)

    if stream:
        return each()
    return np.stack(list(each())).astype(np.float32)


def cache_directory() -> Path:
    import os

    configured = os.environ.get("XDG_CACHE_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".cache"
    return base / "cine-toaster" / "composite"


def _input_identity(value: Any) -> str | None:
    """An input's identity: a file by content, an array by its bytes; a curve given as code has none."""

    import hashlib

    from .identity import file_hash

    if isinstance(value, np.ndarray):
        return "array:" + hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()
    if isinstance(value, (str, Path)) and Path(value).is_file():
        return "file:" + file_hash(Path(value))
    if isinstance(value, dict):  # a track as data
        import json

        return "track:" + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    return None


def render(graph: dict[str, Any], inputs: dict[str, Any], *, frames: int, size: tuple[int, int], fps: float,
           working: str = LINEAR, root: Path | None = None, beats: list[float] | None = None,
           cache: Path | None | bool = True) -> tuple[np.ndarray, str, bool]:
    """`evaluate`, kept by the output's identity (SPEC-0012 §5): (pictures, identity, whether it was cached).

    The cache is disposable: deleting it costs time only. An input with no identity (a curve given as
    code) makes the result uncacheable, and it is computed every time.
    """

    from .identity import REFERENCE_VERSION, identities

    known = {name: _input_identity(value) for name, value in inputs.items()}
    context = {"renderer": REFERENCE_VERSION, "numpy": np.__version__, "working": working, "fps": fps,
               "frames": frames, "size": list(size), "beats": list(beats or [])}
    if cache is False or any(identity is None for identity in known.values()):
        return evaluate(graph, inputs, frames=frames, size=size, fps=fps, working=working, root=root,
                        beats=beats, stream=True), "", False
    output = identities(graph, known, context=context, root=root)[graph["output"].split(".")[0]]
    folder = Path(cache) if isinstance(cache, (str, Path)) else cache_directory()
    stored = folder / f"{output}.npy"
    if stored.is_file():
        return np.load(stored, mmap_mode="r"), output, True
    folder.mkdir(parents=True, exist_ok=True)
    partial = stored.with_suffix(".part.npy")
    # Half floats, the precision SPEC-0012 hands pictures over in, written frame by frame to disk.
    kept = np.lib.format.open_memmap(partial, mode="w+", dtype=np.float16, shape=(frames, size[1], size[0], 4))
    for index, picture in enumerate(evaluate(graph, inputs, frames=frames, size=size, fps=fps, working=working,
                                             root=root, beats=beats, stream=True)):
        kept[index] = picture
        if index % 16 == 15:
            kept.flush()
            _drop_pages(kept, index + 1)
    kept.flush()
    del kept
    partial.replace(stored)
    return np.load(stored, mmap_mode="r"), output, False
