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
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np

from ..errors import ValidationError
from .schema import validate
from .semantics import blur_kernel, pixels, screen_channel, threshold_spread
from .semantics import default as semantic_default

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


def conform_filter(width: int, height: int, *, transparent: bool) -> str:
    """How a picture of any size is fitted to the frame -- one rule for every path (CT-0072, B3).

    Scaled to fit within the frame, keeping its shape, and centred; what is left is transparent in a
    composite (it can be merged over something) and black in a cut. Never stretched.
    """

    border = "black@0" if transparent else "black"
    return (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={border},setsar=1")


def read(path: Path, frames: int, size: tuple[int, int], fps: float, *, start: float = 0.0,
         colorspace: str = ENCODED, alpha: str = "straight", working: str = LINEAR,
         stretch_to: float | None = None, hold: bool = True) -> Clip:
    """A clip or a still, `frames` long, in the working space and premultiplied when used (SPEC-0012 §2)."""

    import tempfile

    width, height = size
    still = Path(path).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".exr", ".tif", ".tiff")
    source = ["-loop", "1", "-framerate", f"{fps:g}"] if still else ["-ss", f"{start:.4f}"]
    retime = ""
    if stretch_to and not still:
        # A clip played over another length: its whole run fitted to `stretch_to` seconds (a matte to its join).
        length = _duration(path) - start
        if length > 0:
            retime = f"setpts=(PTS-STARTPTS)*{stretch_to / length:.6f},"
    process = subprocess.Popen(
        [_ffmpeg(), "-loglevel", "error", *source, "-i", str(path), "-frames:v", str(frames),
         "-vf", f"{retime}fps={fps:g},format=rgba64le,{conform_filter(width, height, transparent=True)}",
         "-f", "rawvideo", "-pix_fmt", "rgba64le", "-"],
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
    for index in range(count, frames):  # a clip shorter than the extent holds its last frame, or ends
        stored[index] = stored[count - 1] if hold else 0
    return Clip(stored, colorspace, alpha, working)


def _duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    completed = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(path)], capture_output=True, text=True, timeout=60)
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return 0.0


def shown(picture: Any, working: str = LINEAR, display: str = ENCODED) -> np.ndarray:
    """A frame as it is shown: its colour in the display encoding, 0 to 1, over black. One rule for a film
    written and for a still drawn from it (CT-0072)."""

    rgb = convert(np.clip(np.asarray(picture, dtype=np.float32)[..., :3], 0.0, None), working, display)
    return np.clip(rgb, 0.0, 1.0)


def write_still(picture: Any, destination: Path, *, working: str = LINEAR, display: str = ENCODED) -> Path:
    """One frame to a PNG, shown as `write` shows it."""

    from PIL import Image

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((shown(picture, working, display) * 255.0 + 0.5).astype(np.uint8), "RGB").save(destination)
    return destination


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
            process.stdin.write((shown(picture, working, display) * 65535.0 + 0.5).astype("<u2").tobytes())
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


def cubic_bezier(x1: float, y1: float, x2: float, y2: float) -> Callable[[float], float]:
    """An ease as CSS and every animation tool write it: a cubic Bézier from (0, 0) to (1, 1) with two handles.

    The time axis is solved for the curve's parameter by bisection (it is monotonic for handles within
    0..1 on x), then the value read on the other axis.
    """

    if not (0 <= x1 <= 1 and 0 <= x2 <= 1):
        raise ValidationError(f"A Bézier ease keeps its handles' times within 0 and 1, not {x1} and {x2}")

    def axis(a: float, b: float, s: float) -> float:
        return 3 * a * (1 - s) ** 2 * s + 3 * b * (1 - s) * s ** 2 + s ** 3

    def ease(x: float) -> float:
        x = min(max(x, 0.0), 1.0)
        low, high = 0.0, 1.0
        for _ in range(40):
            middle = (low + high) / 2
            if axis(x1, x2, middle) < x:
                low = middle
            else:
                high = middle
        return axis(y1, y2, (low + high) / 2)

    return ease


def ease_of(ease: Any) -> Callable[[float], float]:
    """A named ease, or a Bézier given as its four handle numbers; an ease nobody knows is refused, not guessed
    (what an ease may be is decided in `semantics`, which the validator reads too)."""

    from .semantics import ease_problem

    problem = ease_problem(ease)
    if problem:
        raise ValidationError(problem[0].upper() + problem[1:])
    if isinstance(ease, (list, tuple)):
        return cubic_bezier(*map(float, ease))
    return _EASES[str(ease)]


def keys_curve(keys: list[Any]) -> Callable[[float], Any]:
    """`[t, value]` or `{t, value, ease}`: between keys the left key's ease; outside them, held (SPEC-0012 §6)."""

    points = []
    for key in keys:
        if isinstance(key, dict):
            points.append((float(key["t"]), np.asarray(key["value"], dtype=np.float32), ease_of(key.get("ease", "linear"))))
        else:
            points.append((float(key[0]), np.asarray(key[1], dtype=np.float32), _EASES["linear"]))
    points.sort(key=lambda point: point[0])

    def at(seconds: float) -> Any:
        if seconds <= points[0][0]:
            return points[0][1]
        for (t0, v0, ease), (t1, v1, _) in zip(points, points[1:]):
            if seconds < t1:
                x = ease((seconds - t0) / (t1 - t0))
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


def noise_field(kind: str, scale: float, seed: int, frame: int, width: int, height: int) -> np.ndarray:
    """generate.noise's values, 0 to 1: one drawing of them for every renderer (GL uploads it; CT-0077)."""

    if kind == "grain":
        grey = np.random.default_rng([seed, frame]).normal(0.5, 0.15, (height, width)).astype(np.float32)
    else:
        cells = max(1.0, float(scale))
        from PIL import Image

        coarse = np.random.default_rng(seed).uniform(0, 1, (int(cells * height / width) + 2, int(cells) + 2))
        grey = np.asarray(Image.fromarray(coarse.astype(np.float32), "F").resize((width, height), Image.BICUBIC))
    return np.clip(grey, 0, 1).astype(np.float32)


def grain_field(seed: int, frame: int, size: float, width: int, height: int) -> np.ndarray:
    """filter.noise's grain for a frame (mean 0), its size in pixels at 720 lines: shared by every renderer."""

    grain = np.random.default_rng([seed, frame]).normal(0, 1, (height, width)).astype(np.float32)
    return _blur(grain, max(pixels(size, height) - 1.0, 0.0))


def _excess(rgb: np.ndarray, screen: np.ndarray) -> np.ndarray:
    """How much a colour's screen channel (the one the key colour is made of) exceeds the larger of the other two."""

    index = screen_channel(screen)
    others = [channel for channel in range(3) if channel != index]
    return rgb[..., index] - np.maximum(rgb[..., others[0]], rgb[..., others[1]])


def _blur(image: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0:
        return image
    sigma, half = blur_kernel(radius)
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
    "warp.transform", "warp.corner_pin", "warp.displace", "warp.procedural", "warp.surface",
    "colour.grade", "colour.invert", "colour.despill", "colour.curve", "colour.lut", "colour.posterise", "colour.solarise",
    "colour.cycle",
    "filter.blur", "filter.sharpen", "filter.glow", "filter.edges", "filter.morphology", "filter.noise",
    "time.remap", "time.offset", "time.blend", "time.echo",
    "track.read", "track.measure",
    "curve.progress", "curve.keys", "curve.map", "curve.combine", "curve.noise", "curve.beats", "curve.from_track",
}
#: In SPEC-0012 but outside the reference, by definition (opaque) or until a renderer gives them (models, 3D).
NOT_IN_REFERENCE = {"signal.estimate": "a model's result is recorded, not computed by the reference",
                    "generate.render": "a renderer's own scene; its result is recorded"}


@lru_cache(maxsize=64)
def _text_coverage(text: str, shown: str, font_path: str, size_px: int, position: tuple[float, float],
                   width: int, height: int) -> np.ndarray:
    """How much of each pixel the text covers, drawn four times over and averaged. Kept: a still text (a
    card, a title not revealing) is the same drawing on every frame."""

    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(font_path, size_px)
    canvas = Image.new("L", (width * 4, height * 4), 0)
    draw = ImageDraw.Draw(canvas)
    box = draw.textbbox((0, 0), text, font=font)  # placed by the whole text, so letters do not shift
    x = position[0] * width * 4 - (box[2] - box[0]) / 2 - box[0]
    y = position[1] * height * 4 - (box[3] - box[1]) / 2 - box[1]
    draw.text((x, y), shown, font=font, fill=255)
    coverage = np.asarray(canvas.resize((width, height), Image.BOX), dtype=np.float32) / 255.0
    coverage.setflags(write=False)
    return coverage


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


def curve_factory(nodes: dict[str, Any], curves: dict[str, Callable[[float], Any]], *, fps: float, length: float,
                  beats: list[float] | None, tracks: Callable[[str], dict[str, Any]]) -> Callable[[str], Callable]:
    """The curves of a graph (SPEC-0012 §6), evaluated the same way by every renderer: they are numbers per
    frame, computed on the CPU and handed to whatever draws the pictures. ``curves`` holds those given as
    inputs and is filled as curves are made."""

    def curve(reference: str) -> Callable[[float], Any]:
        if reference in curves:
            return curves[reference]
        node = nodes[reference]
        op = node["op"]
        if op == "curve.progress":
            made = lambda seconds: seconds / length if length else 0.0  # noqa: E731
        elif op == "curve.keys":
            keyed = keys_curve(node["keys"])
            if node.get("in"):  # keys placed along another curve: a recipe's keys follow its join's progress
                along = curve(node["in"])
                made = lambda seconds: keyed(float(along(seconds)))  # noqa: E731
            else:
                made = keyed
        elif op == "curve.noise":
            made = noise_curve(int(node.get("seed", 0)), float(node.get("frequency", 1.0)),
                               float(node.get("amplitude", 1.0)), float(node.get("offset", 0.0)))
        elif op == "curve.map":
            source, how = curve(node["in"]), node["how"]
            low, high = float(node.get("low", 0.0)), float(node.get("high", 1.0))
            out_low, out_high = float(node.get("out_low", 0.0)), float(node.get("out_high", 1.0))
            factor = float(node.get("factor", 1.0))
            ease = ease_of(node.get("ease", "in-out"))
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
            # When a pulse happens is the beat's; how the value reacts is the envelope's. An ease maps 0 to 0
            # and 1 to 1, so changing it reshapes the pulse and never moves its peak off the beat (CT-0074).
            beat = lambda key: semantic_default("curve.beats", key) if node.get(key) is None else node[key]  # noqa: E731
            # A frame reads its curves at its centre, so a beat's peak is placed at the centre of the frame
            # it falls in: that frame shows the full pulse, whatever the eases -- a sharp envelope never lets
            # the frame before it come out higher and move the hit off its frame.
            times = [(math.floor(at * fps + 1e-9) + 0.5) / fps
                     for at in list(beats or [])[:: max(int(beat("every") or 1), 1)]]
            attack, decay = max(float(beat("attack")), 0.0), max(float(beat("decay")), 0.0)
            low, high = float(beat("low")), float(beat("high"))
            rise, fall = ease_of(beat("attack_ease")), ease_of(beat("decay_ease"))
            adding = beat("overlap") == "add"

            def made(seconds: float, times=times, attack=attack, decay=decay, low=low, high=high, rise=rise,
                     fall=fall, adding=adding) -> float:
                level = 0.0
                for at in times:
                    d = seconds - at
                    if d == 0 or (-attack < d < 0):
                        pulse = 1.0 if d == 0 else rise(1 + d / attack)
                    elif 0 < d < decay:
                        pulse = 1.0 - fall(d / decay)
                    else:
                        continue
                    level = level + pulse if adding else max(level, pulse)
                return low + (high - low) * min(level, 1.0)
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

    return curve


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

    curve = curve_factory(nodes, curves, fps=fps, length=length, beats=beats,
                          tracks=lambda reference: tracks(reference))

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
        base, _, output = reference.partition(".")
        if output and base in nodes:  # a second output: made with its node's first
            value(base, frame)
            if key in context.cache:
                return context.cache[key]
            raise ValidationError(f"{base} gives no {output!r} the reference can make")
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
            # An author's value, else the op's default as decided once in `semantics` (CT-0072).
            given = node.get(key)
            if given is None:
                given = semantic_default(op, key, default)
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
            u, v = (xs + 0.5) / width - 0.5, (ys + 0.5) / height - 0.5  # from the centre, in frame fractions
            kind = param("kind", "linear")
            if kind == "radial":  # the frame's own shape, its corners at 1
                x = np.hypot(u, v) / math.hypot(0.5, 0.5)
            elif kind == "circle":  # round whatever the frame, its corners at 1 (CT-0076)
                x = np.hypot(u * aspect, v) / math.hypot(0.5 * aspect, 0.5)
            elif kind == "diamond":  # by |x| + |y| in frame fractions, its corners at 1
                x = np.abs(u) + np.abs(v)
            elif kind == "conic":  # the angle, clockwise from twelve o'clock, round whatever the frame
                x = np.mod(np.arctan2(u * aspect, -v) / (2 * math.pi) - float(param("angle", 0.0)) / 360.0, 1.0)
            else:
                angle = math.radians(float(param("angle", 0.0)))
                x = ((xs + 0.5) / width - 0.5) * math.cos(angle) + ((ys + 0.5) / height - 0.5) * math.sin(angle) + 0.5
            repeats = float(param("repeat", 1.0) or 1.0)
            if repeats > 1.0:  # the ramp repeated: stripes, rings, bands (CT-0077)
                x = np.mod(np.clip(x, 0, 1) * repeats, 1.0)
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
            spread = threshold_spread(param("softness"))
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
                # A colour key by colour difference (CT-0075), in linear light where an edge is the subject and
                # the screen mixed: how much the screen's channel exceeds the others, against the screen's own
                # excess. 0 on the screen, 1 where there is no excess, and between, the subject's share of an
                # edge pixel -- what `colour.despill` needs to take the screen out. A difference key by the
                # largest channel against a clean plate, in the display encoding. 0 at `tolerance`, 1 past it
                # by the softness's spread.
                shown_here = convert(straight, working, ENCODED)
                if by == "colour":
                    target = np.asarray(param("colour"), dtype=np.float32)[:3]
                    distance = 1.0 - _excess(straight, target) / max(float(_excess(target, target)), 1e-6)
                else:
                    plate = _picture(value(node["reference"], frame))
                    plate_alpha = plate[..., 3:4]
                    plate = np.divide(plate[..., :3], plate_alpha, out=np.zeros_like(plate[..., :3]),
                                      where=plate_alpha > 1e-6)
                    distance = np.abs(shown_here - convert(plate, working, ENCODED)).max(axis=-1)
                spread = threshold_spread(param("softness", 0.0))
                key = np.clip((distance - float(param("tolerance"))) / spread, 0, 1)
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
            # `b` blended onto `a` as W3C Compositing defines it for premultiplied pictures (CT-0075): the blend
            # of their straight colours where both are, each alone where only it is, so a transparent part of
            # `b` leaves `a` as it was whatever the mode; the alpha is the union of both.
            a, b = _picture(value(node["a"], frame)), _picture(value(node["b"], frame))
            alpha_a, alpha_b = a[..., 3:4], b[..., 3:4]
            cb = np.divide(a[..., :3], alpha_a, out=np.zeros_like(a[..., :3]), where=alpha_a > 1e-6)
            cs = np.divide(b[..., :3], alpha_b, out=np.zeros_like(b[..., :3]), where=alpha_b > 1e-6)
            mode = node["mode"]
            blended = {"screen": cb + cs - cb * cs, "add": cb + cs, "multiply": cb * cs, "lighten": np.maximum(cb, cs),
                       "darken": np.minimum(cb, cs), "difference": np.abs(cb - cs),
                       "overlay": np.where(cb < 0.5, 2 * cb * cs, 1 - 2 * (1 - cb) * (1 - cs))}[mode]
            composed = np.concatenate([b[..., :3] * (1 - alpha_a) + a[..., :3] * (1 - alpha_b)
                                       + alpha_a * alpha_b * blended, alpha_a + alpha_b - alpha_a * alpha_b], axis=-1)
            mix = float(param("mix", 1.0))
            return (a * (1 - mix) + composed * mix).astype(np.float32)
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

            angles = param("rotate")
            return transform(value(node["in"], frame), translate=param("translate"),
                             scale=param("scale"), rotate=angles if angles is not None else 0.0,
                             pivot=param("pivot"), perspective=float(param("perspective") or 0.0),
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
        if op == "warp.surface":
            from .warp import surface

            picture, depth = surface(_picture(value(node["in"], frame)), shape=node["shape"],
                                     morph=float(param("morph")), rotate=param("rotate"),
                                     translate=param("translate"), scale=float(param("scale")),
                                     perspective=float(param("perspective") or 0.0),
                                     light=float(param("light")), detail=int(param("detail")),
                                     supersample=int(param("supersample")), aspect=aspect)
            context.cache[(f"{name}.depth", frame)] = depth
            return picture
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
        if op == "colour.despill":
            # The screen's channel held to the largest (or the mean) of the other two, on the straight colour:
            # a grey or a skin keeps its colour, a green cast on hair goes. The same in any encoding, since it
            # compares channels of one pixel through the same curve.
            picture = _picture(value(node["in"], frame))
            screen_rgb = np.asarray(param("colour"), dtype=np.float32)[:3]
            if node.get("matte"):
                # An edge pixel is the subject and the screen mixed in light, C = m F + (1 - m) S: what is left
                # of the subject is C - (1 - m) S, seen as much as the matte says.
                matte = _matte(value(node["matte"], frame))[..., None]
                picture = np.concatenate([np.clip(picture[..., :3] - (1 - matte) * screen_rgb * picture[..., 3:4],
                                                  0, None), picture[..., 3:4] * matte], axis=-1)
            alpha = picture[..., 3:4]
            rgb = np.divide(picture[..., :3], alpha, out=np.zeros_like(picture[..., :3]), where=alpha > 1e-6)
            screen = screen_channel(screen_rgb)
            others = rgb[..., [index for index in range(3) if index != screen]]
            cap = others.max(axis=-1) if param("limit", "max") == "max" else others.mean(axis=-1)
            held = rgb.copy()
            held[..., screen] = np.minimum(rgb[..., screen], cap)
            rgb = rgb + (held - rgb) * float(param("amount", 1.0))
            return np.concatenate([rgb * alpha, alpha], axis=-1).astype(np.float32)
        if op == "colour.invert":
            given = value(node["in"], frame)
            if given.ndim == 2:
                return 1.0 - given
            alpha = given[..., 3:4]
            out = given.copy()
            out[..., :3] = alpha - given[..., :3]  # 1 - colour, kept premultiplied
            return out
        if op == "filter.blur":
            return _blur(value(node["in"], frame), pixels(param("radius", 0.0), height))
        return more(name, node, op, frame, seconds, param, value)

    def more(name: str, node: dict[str, Any], op: str, frame: int, seconds: float, param, value) -> Any:
        """The ops of the second slice (CT-0071): generators, signals from files, depth, colour, filters, time."""

        def straight(picture: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            alpha = picture[..., 3:4]
            return np.divide(picture[..., :3], alpha, out=np.zeros_like(picture[..., :3]), where=alpha > 1e-6), alpha

        def rebuilt(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
            return np.concatenate([rgb * alpha, alpha], axis=-1).astype(np.float32)

        if op == "generate.noise":
            grey = noise_field(str(param("kind", "value")), float(param("scale", 8.0)), int(param("seed", 0) or 0),
                               frame, width, height)
            return np.stack([grey, grey, grey, np.ones_like(grey)], axis=-1)
        if op == "generate.text":
            from ..titles import font_file

            text = str(param("text", ""))
            reveal = param("reveal", 1.0)
            shown = text[: int(round(len(text) * float(np.clip(reveal, 0, 1))))] if reveal is not None else text
            size_px = max(4, int(pixels(param("size", 40), height) * 4))
            position = np.broadcast_to(np.asarray(param("position", [0.5, 0.5]), dtype=np.float32), (2,))
            coverage = _text_coverage(text, shown, font_file({"font": node.get("font") or ""}, root), size_px,
                                      (float(position[0]), float(position[1])), width, height)
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
            return np.clip(picture + float(param("amount", 0.5)) * (picture - _blur(picture, pixels(2.0, height))), 0, None)
        if op == "filter.glow":
            picture = _picture(value(node["in"], frame))
            rgb, alpha = straight(picture)
            bright = np.clip(rgb @ np.asarray(REC709, dtype=np.float32) - float(param("threshold", 0.8)), 0, None)
            halo = _blur(picture[..., :3] * (bright > 0)[..., None], pixels(param("radius", 8.0), height))
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
            radius = max(0, int(round(pixels(param("radius", 1.0), height))))
            padded = np.pad(matte, radius, mode="edge")
            stack = [padded[dy:dy + height, dx:dx + width] for dy in range(2 * radius + 1)
                     for dx in range(2 * radius + 1)]
            return (np.min(stack, axis=0) if node["operation"] == "erode" else np.max(stack, axis=0)).astype(
                np.float32)
        if op == "filter.noise":
            picture = _picture(value(node["in"], frame))
            grain = grain_field(int(param("seed", 0) or 0), frame, float(param("size", 1.0)), width, height)
            amount = grain[..., None] * float(param("amount", 0.1)) * 0.1
            out = picture.copy()
            if param("space", "linear") == "display":
                # Grain as video shows it (CT-0077): added to the encoded picture, the same in the shadows as in
                # the highlights; in linear light a little grain swamps the dark parts once encoded.
                rgb, alpha = straight(picture)
                out[..., :3] = decode_srgb(np.clip(encode_srgb(rgb) + amount, 0, None)) * alpha
            else:
                out[..., :3] = np.clip(picture[..., :3] + amount * picture[..., 3:4], 0, None)
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
           cache: Path | None | bool = True, renderer: Any = None) -> tuple[np.ndarray, str, bool]:
    """`evaluate`, kept by the output's identity (SPEC-0012 §5): (pictures, identity, whether it was cached).

    The cache is disposable: deleting it costs time only. An input with no identity (a curve given as
    code) makes the result uncacheable, and it is computed every time.
    """

    from .identity import REFERENCE_VERSION, identities

    known = {name: _input_identity(value) for name, value in inputs.items()}
    # Another renderer (GL) draws the same graph; its results are kept apart from the reference's.
    draw = renderer.evaluate if renderer is not None else evaluate
    context = {"renderer": f"gl/{renderer.name}" if renderer is not None else REFERENCE_VERSION, "numpy": np.__version__, "working": working, "fps": fps,
               "frames": frames, "size": list(size), "beats": list(beats or [])}
    if cache is False or any(identity is None for identity in known.values()):
        return draw(graph, inputs, frames=frames, size=size, fps=fps, working=working, root=root,
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
    for index, picture in enumerate(draw(graph, inputs, frames=frames, size=size, fps=fps, working=working,
                                         root=root, beats=beats, stream=True)):
        kept[index] = picture
        if index % 16 == 15:
            kept.flush()
            _drop_pages(kept, index + 1)
    kept.flush()
    del kept
    partial.replace(stored)
    return np.load(stored, mmap_mode="r"), output, False
