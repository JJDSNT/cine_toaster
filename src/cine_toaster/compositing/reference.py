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
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np

from ..errors import ValidationError
from ..timebase import ffmpeg_rate, seek
from .schema import validate
from .semantics import blur_kernel, hue_turn, pixels, screen_channel, threshold_spread
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
    exhausted memory (CT-0071). Here the decoded frames live in a memory-mapped file -- 16-bit integers, or half
    floats for a float source, its light above white kept -- and only the frames in use are full floats.
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
        data = np.asarray(self.raw[min(index, len(self) - 1)], dtype=np.float32)
        if self.raw.dtype == np.uint16:  # an integer picture, 0 to 1; a float one is kept as it is
            data = data / 65535.0
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


def conform_box(source_width: int, source_height: int, width: int, height: int) -> tuple[int, int, int, int]:
    """Where a picture of any size lands in the frame -- one rule for every path (CT-0072, B3): scaled to fit
    within it, keeping its shape, and centred; never stretched. (width, height, x, y) of the fitted picture.
    The FFmpeg filter below and the float path of `read` both follow it."""

    scale = min(width / source_width, height / source_height)
    fitted_width = min(width, max(1, int(round(source_width * scale))))
    fitted_height = min(height, max(1, int(round(source_height * scale))))
    return fitted_width, fitted_height, (width - fitted_width) // 2, (height - fitted_height) // 2


def conform_filter(width: int, height: int, *, transparent: bool) -> str:
    """`conform_box` as an FFmpeg filter, for pictures FFmpeg scales (integer ones: its scaler clips floats).

    What is left around the picture is transparent in a composite (it can be merged over something) and black
    in a cut.
    """

    border = "black@0" if transparent else "black"
    return (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={border},setsar=1")


FLOAT_PIXELS = ("f32", "f16")  # pixel formats whose values may pass white (OpenEXR, float TIFF)


def _probe_picture(path: Path) -> tuple[int, int, str]:
    """(width, height, pixel format) of a file, or of the first frame of a sequence named by a pattern."""

    from ..color import _frames

    target = str(path)
    if "%" in target:
        found = _frames(target)
        target = str(found[0]) if found else target
    completed = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height,pix_fmt", "-of", "csv=p=0", target],
                               capture_output=True, text=True)
    width, height, pixels = (completed.stdout.strip().split(",") + ["0", "0", ""])[:3]
    return int(width or 0), int(height or 0), pixels


def _input(path: Path, fps: float, start: float, still: bool) -> list[str]:
    target = str(path)
    if "%" in target:  # a sequence of frames: read from its first number, at the rate asked
        import re

        from ..color import _frames

        found = _frames(target)
        first = int(re.findall(r"(\d+)", found[0].stem)[-1]) if found else 1
        return ["-framerate", ffmpeg_rate(fps), "-start_number", str(first), "-i", target]
    return (["-loop", "1", "-framerate", ffmpeg_rate(fps)] if still else ["-ss", seek(start)]) + ["-i", target]


def read(path: Path, frames: int, size: tuple[int, int], fps: float, *, start: float = 0.0,
         colorspace: str | None = None, alpha: str | None = None, working: str = LINEAR,
         stretch_to: float | None = None, hold: bool = True) -> Clip:
    """A clip, a still or a sequence, `frames` long, in the working space and premultiplied when used
    (SPEC-0012 §2).

    A file's colour space and alpha are, unless said, the file's convention: an integer picture is display
    encoded with straight alpha; a float one (OpenEXR) is scene-linear light with premultiplied alpha, and is
    read as float, its values above white kept (SPEC-0012's range rule, CT-0077).
    """

    import tempfile

    from . import lottie

    if lottie.is_lottie(Path(path)):
        # Motion graphics drawn by their own renderer (C6b stage D): the clip a PNG sequence would be.
        return Clip(lottie.read(Path(path), frames, size, fps, start=start, stretch_to=stretch_to, hold=hold),
                    colorspace or ENCODED, alpha or "straight", working)
    width, height = size
    still = Path(path).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".exr", ".tif", ".tiff") \
        and "%" not in str(path)
    source_width, source_height, pixels = _probe_picture(Path(path))
    floating = any(mark in pixels for mark in FLOAT_PIXELS)
    colorspace = colorspace or (LINEAR if floating else ENCODED)
    alpha = alpha or ("premultiplied" if floating else "straight")
    retime = ""
    if stretch_to and not still:
        # A clip played over another length: its whole run fitted to `stretch_to` seconds (a matte to its join).
        length = _duration(path) - start
        if length > 0:
            retime = f"setpts=(PTS-STARTPTS)*{stretch_to / length:.6f},"
    if floating:
        # Read at its own size as float (FFmpeg's scaler clips floats at white), then fitted here by the same
        # rule (`conform_box`).
        fitted_width, fitted_height, x, y = conform_box(source_width, source_height, width, height)
        command = [_ffmpeg(), "-loglevel", "error", *_input(Path(path), fps, start, still), "-frames:v", str(frames),
                   "-vf", f"{retime}fps={ffmpeg_rate(fps)},format=gbrapf32le", "-f", "rawvideo", "-pix_fmt", "gbrapf32le", "-"]
        frame_bytes, dtype = source_width * source_height * 4 * 4, "<f4"
    else:
        command = [_ffmpeg(), "-loglevel", "error", *_input(Path(path), fps, start, still), "-frames:v", str(frames),
                   "-vf", f"{retime}fps={ffmpeg_rate(fps)},format=rgba64le,{conform_filter(width, height, transparent=True)}",
                   "-f", "rawvideo", "-pix_fmt", "rgba64le", "-"]
        frame_bytes, dtype = width * height * 4 * 2, "<u2"
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    handle = tempfile.NamedTemporaryFile(prefix="clip-", suffix=".raw", delete=False)
    stored = np.lib.format.open_memmap(handle.name, mode="w+", dtype="<f2" if floating else "<u2",
                                       shape=(frames, height, width, 4))
    Path(handle.name).unlink()  # the mapping keeps it; nothing is left behind
    handle.close()
    count = 0
    while count < frames:
        chunk = process.stdout.read(frame_bytes)
        if len(chunk) < frame_bytes:
            break
        if floating:
            planes = np.frombuffer(chunk, dtype=dtype).reshape(4, source_height, source_width)
            rgba = np.stack([planes[2], planes[0], planes[1], planes[3]], axis=-1)  # g, b, r, a -> r, g, b, a
            frame = np.zeros((height, width, 4), dtype=np.float32)
            frame[y:y + fitted_height, x:x + fitted_width] = Image_resize(rgba, fitted_width, fitted_height)
            stored[count] = frame
        else:
            stored[count] = np.frombuffer(chunk, dtype=dtype).reshape(height, width, 4)
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


#: How a drawing is written: kept for further work (4:4:4, near lossless), or as a piece of the cut, in the
#: format the cut joins its pieces in -- the shot's one encode before the film's.
MASTER = ("yuv444p", "12")
PIECE = ("yuv420p", "18")


def write(pictures: Any, destination: Path, fps: float, *, working: str = LINEAR,
          display: str = ENCODED, quality: tuple[str, str] = MASTER) -> Path:
    """Frames (an array or any sequence of (H, W, 4)), linear premultiplied, to H.264 in the display encoding.

    Written as they come, so a long composite never has to be in memory at once.
    """

    frames = iter(pictures)
    first = next(frames)
    height, width = first.shape[:2]
    process = subprocess.Popen(
        [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb48le", "-s", f"{width}x{height}",
         "-r", ffmpeg_rate(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", quality[1], "-pix_fmt", quality[0],
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
            points.append((float(key["t"]), np.asarray(key["value"], dtype=np.float64), ease_of(key.get("ease", "linear"))))
        else:
            points.append((float(key[0]), np.asarray(key[1], dtype=np.float64), _EASES["linear"]))
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


def lut_colours(node: dict[str, Any], rgb: np.ndarray, working: str, root: Path | None = None) -> np.ndarray:
    """colour.lut on straight linear colours: an OCIO look, a display view seen and brought back to linear, or a
    .cube file (made for encoded pictures, so applied in the display encoding). One drawing of a look: GL bakes
    its lattice from this function (CT-0077)."""

    import PyOpenColorIO as ocio

    from ..color import DISPLAY, _processor, config

    flat = np.ascontiguousarray(rgb.reshape(-1, 3), dtype=np.float32)
    if node.get("look"):
        transform = ocio.LookTransform(src=working, dst=working, looks=node["look"])
        config().getProcessor(transform).getDefaultCPUProcessor().applyRGB(flat)
        return flat.reshape(rgb.shape)
    if node.get("view"):
        # Seen through a display view (a film response such as ACES 2.0's), then decoded back to light.
        _processor(working, display=str(node.get("display") or DISPLAY), view=str(node["view"])).applyRGB(flat)
        return convert(np.clip(flat.reshape(rgb.shape), 0.0, 1.0), ENCODED, working)
    path = Path(node["file"])
    path = (root / path) if root and not path.is_absolute() else path
    encoded = np.ascontiguousarray(convert(rgb, working, ENCODED).reshape(-1, 3), dtype=np.float32)
    config().getProcessor(ocio.FileTransform(src=str(path))).getDefaultCPUProcessor().applyRGB(encoded)
    return convert(encoded.reshape(rgb.shape), ENCODED, working)


def gradient_stops(colours: Any, at: Any = None) -> tuple[np.ndarray, np.ndarray]:
    """A gradient's stops (up to eight, as GL takes them) and where each sits from 0 to 1: given by `at`, or
    evenly spaced. Two stops close together make a sharp edge -- a chrome's horizon (CT-0078)."""

    stops = np.asarray(colours, dtype=np.float32).reshape(-1, 4)[:8]
    if at is not None and len(np.asarray(at).reshape(-1)) >= len(stops):
        places = np.maximum.accumulate(np.clip(np.asarray(at, dtype=np.float32).reshape(-1)[:len(stops)], 0, 1))
    else:
        places = np.linspace(0.0, 1.0, len(stops), dtype=np.float32)
    return stops, places


def gradient_colours(colours: np.ndarray, x: np.ndarray, at: Any = None) -> np.ndarray:
    """Colours along a gradient: mixed linearly between its stops (`gradient_stops`)."""

    stops, places = gradient_stops(colours, at)
    if len(stops) == 1:
        return np.broadcast_to(stops[0], x.shape + (4,)).astype(np.float32).copy()
    upper = np.clip(np.searchsorted(places, x, side="right"), 1, len(stops) - 1)
    lower = upper - 1
    span = np.maximum(places[upper] - places[lower], 1e-6)
    weight = np.clip((x - places[lower]) / span, 0, 1)[..., None]
    return (stops[lower] * (1 - weight) + stops[upper] * weight).astype(np.float32)


def bevel_lit(picture: np.ndarray, relief: np.ndarray, radius_px: float, param: Callable[..., Any]) -> np.ndarray:
    """A picture lit as if raised: its blurred alpha (`relief`) is a height, its slope (central differences, in
    the radius's units) tilts the surface, light from `semantics.light_direction` brightens the faces turned to it
    (by `highlight`, as white light) and darkens the others (by `shadow`). Alpha is left as it was."""

    from .semantics import light_direction

    lx, ly, lz = light_direction(param("angle", 135.0), param("elevation", 35.0))
    padded = np.pad(relief, 1, mode="edge")
    slope_x = (padded[1:-1, 2:] - padded[1:-1, :-2]) * 0.5 * max(radius_px, 1.0) * float(param("depth", 1.0))
    slope_y = (padded[2:, 1:-1] - padded[:-2, 1:-1]) * 0.5 * max(radius_px, 1.0) * float(param("depth", 1.0))
    length = np.sqrt(slope_x ** 2 + slope_y ** 2 + 1.0)
    shade = ((-slope_x * lx - slope_y * ly + lz) / length) / max(lz, 1e-6)
    lit, dark = np.clip(shade - 1.0, 0, None), np.clip(1.0 - shade, 0, None)
    alpha = picture[..., 3:4]
    rgb = picture[..., :3] * (1.0 - float(param("shadow", 0.6)) * dark[..., None]) \
        + float(param("highlight", 0.6)) * lit[..., None] * alpha
    return np.concatenate([np.clip(rgb, 0, None), alpha], axis=-1).astype(np.float32)


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
    "filter.bevel",
    "time.remap", "time.offset", "time.blend", "time.echo",
    "track.read", "track.measure",
    "curve.progress", "curve.keys", "curve.map", "curve.combine", "curve.noise", "curve.beats", "curve.from_track",
}
#: In SPEC-0012 but outside the reference, by definition (opaque) or until a renderer gives them (models, 3D).
NOT_IN_REFERENCE = {"signal.estimate": "a model's result is recorded, not computed by the reference",
                    "generate.render": "a renderer's own scene; its result is recorded"}


@lru_cache(maxsize=64)
def _text_coverage(text: str, shown: str, font_path: str, size_px: int, position: tuple[float, float],
                   width: int, height: int, align: str = "centre", spacing_px: int = 0, outline_px: int = 0,
                   hollow: bool = False) -> np.ndarray:
    """How much of each pixel the text covers, drawn four times over and averaged. Kept: a still text (a
    card, a title not revealing) is the same drawing on every frame.

    The text is placed by its whole extent -- centred on `position`, or starting or ending there by `align` --
    so revealed letters do not shift; lines are `spacing_px` apart beyond the font's own; an `outline` draws a
    stroke round the letters, and `hollow` keeps only the stroke (a neon tube)."""

    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(font_path, size_px)
    anchor = {"centre": "center", "left": "left", "right": "right"}[align]

    def drawn(value: str, stroke: int) -> Image.Image:
        canvas = Image.new("L", (width * 4, height * 4), 0)
        draw = ImageDraw.Draw(canvas)
        box = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing_px, stroke_width=stroke)
        across = box[2] - box[0]
        x = position[0] * width * 4 - {"center": across / 2, "left": 0.0, "right": across}[anchor] - box[0]
        y = position[1] * height * 4 - (box[3] - box[1]) / 2 - box[1]
        draw.multiline_text((x, y), value, font=font, fill=255, spacing=spacing_px, align=anchor,
                            stroke_width=stroke, stroke_fill=255)
        return canvas

    canvas = drawn(shown, outline_px)
    if hollow and outline_px:
        inside = np.asarray(drawn(shown, 0), dtype=np.int16)
        canvas = Image.fromarray(np.clip(np.asarray(canvas, dtype=np.int16) - inside, 0, 255).astype(np.uint8), "L")
    coverage = np.asarray(canvas.resize((width, height), Image.BOX), dtype=np.float32) / 255.0
    coverage.setflags(write=False)
    return coverage


#: The tables an OpenType font draws its glyphs' own colours from that FreeType draws: layered (COLR) and bitmap
#: (CBDT, Apple's sbix). SVG glyphs need a renderer FreeType is not given: such a font draws as a plain one (a
#: limitation recorded in the roadmap).
COLOUR_TABLES = (b"COLR", b"CBDT", b"sbix")


@lru_cache(maxsize=32)
def colour_glyphs(font_path: str) -> bool:
    """Whether the font carries its glyphs' own colours (C6b stage C, CT-0078): read from the font's table
    directory, the first face of a collection."""

    try:
        with open(font_path, "rb") as handle:
            head = handle.read(12)
            start = 0
            if head[:4] == b"ttcf":
                handle.seek(12)
                start = int.from_bytes(handle.read(4), "big")
                handle.seek(start)
                head = handle.read(12)
            count = int.from_bytes(head[4:6], "big")
            directory = handle.read(16 * count)
    except OSError:
        return False
    return any(directory[16 * index: 16 * index + 4] in COLOUR_TABLES for index in range(count))


def _colour_font(font_path: str, size_px: int) -> tuple[Any, float]:
    """The font at `size_px`, and the scale its drawing needs: a bitmap colour font (CBDT, sbix) has only the
    sizes it was drawn at, so it is read at one of them and its drawing scaled."""

    from PIL import ImageFont

    try:
        return ImageFont.truetype(font_path, size_px), 1.0
    except OSError:
        for strike in (109, 136, 128, 160, 96, 72, 64, 48, 32, 20):
            try:
                return ImageFont.truetype(font_path, strike), size_px / strike
            except OSError:
                continue
        raise


@lru_cache(maxsize=64)
def _colour_text(shown: str, text: str, font_path: str, size_px: int, position: tuple[float, float], width: int,
                 height: int, align: str = "centre", spacing_px: int = 0) -> np.ndarray:
    """The text in its font's own colours, premultiplied, placed as `_text_coverage` places it -- by the whole
    text's extent -- and drawn four times over, then averaged."""

    from PIL import Image, ImageDraw

    font, scale = _colour_font(font_path, size_px)
    anchor = {"centre": "center", "left": "left", "right": "right"}[align]
    spacing = int(round(spacing_px / scale))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = probe.multiline_textbbox((0, 0), text, font=font, spacing=spacing)
    tile = Image.new("RGBA", (max(1, box[2] - box[0]), max(1, box[3] - box[1])), (0, 0, 0, 0))
    if shown:
        ImageDraw.Draw(tile).multiline_text((-box[0], -box[1]), shown, font=font, spacing=spacing, align=anchor,
                                            embedded_color=True)
    if scale != 1.0:
        tile = tile.resize((max(1, round(tile.width * scale)), max(1, round(tile.height * scale))), Image.LANCZOS)
    data = np.asarray(tile, dtype=np.float32) / 255.0
    # The font's colours are display colours: into linear light, then premultiplied.
    data = np.concatenate([decode_srgb(data[..., :3]) * data[..., 3:], data[..., 3:]], axis=-1)
    drawn = np.zeros((height * 4, width * 4, 4), np.float32)
    x = int(round(position[0] * width * 4 - {"center": tile.width / 2, "left": 0.0, "right": float(tile.width)}[anchor]))
    y = int(round(position[1] * height * 4 - tile.height / 2))
    ys, xs = slice(max(0, y), min(height * 4, y + tile.height)), slice(max(0, x), min(width * 4, x + tile.width))
    if ys.start < ys.stop and xs.start < xs.stop:
        drawn[ys, xs] = data[ys.start - y:ys.stop - y, xs.start - x:xs.stop - x]
    picture = drawn.reshape(height, 4, width, 4, 4).mean(axis=(1, 3)).astype(np.float32)
    picture.setflags(write=False)
    return picture


LETTER_PROPERTIES = {"offset": [0.0, 0.0], "rotate": 0.0, "scale": 1.0, "opacity": 1.0}


def letter_state(spec: dict[str, Any], local: float, index: int, seconds: float) -> dict[str, Any]:
    """One letter's offset (pixels at 720 lines), turn (degrees), scale and opacity at its own time `local` --
    the animator's keys, eased -- plus a wave running along the line (C6b, CT-0078)."""

    state = {key: np.asarray(value, dtype=np.float64) for key, value in LETTER_PROPERTIES.items()}
    keys = sorted(spec.get("keys") or [], key=lambda key: float(key.get("t", 0.0)))
    for key in LETTER_PROPERTIES:
        points = [(float(k.get("t", 0.0)), np.asarray(k[key], dtype=np.float64), k.get("ease", "linear"))
                  for k in keys if key in k]
        if not points:
            continue
        if local <= points[0][0]:
            state[key] = points[0][1]
        elif local >= points[-1][0]:
            state[key] = points[-1][1]
        else:
            for (t0, v0, ease), (t1, v1, _) in zip(points, points[1:]):
                if local < t1:
                    state[key] = v0 + (v1 - v0) * ease_of(ease)((local - t0) / (t1 - t0))
                    break
    wave = spec.get("wave")
    if wave:
        lift = float(wave.get("amplitude", 10.0)) * math.sin(
            2 * math.pi * (float(wave.get("frequency", 1.0)) * seconds + index * float(wave.get("phase", 0.15))))
        state["offset"] = state["offset"] + np.array([0.0, -lift])
    return state


def letter_ranks(text: str, order: str, seed: int = 0) -> list[int]:
    """Each character's place in the animator's order: forward, backward, from the centre out, or shuffled.
    Spaces take no place, so a word's letters follow each other without a pause between words."""

    visible = [index for index, char in enumerate(text) if not char.isspace()]
    count = len(visible)
    if order == "backward":
        places = list(range(count - 1, -1, -1))
    elif order == "centre":
        places = [int(round(abs(position - (count - 1) / 2))) for position in range(count)]
    elif order == "random":
        places = list(np.random.default_rng(seed).permutation(count))
    else:
        places = list(range(count))
    ranks = [0] * len(text)
    for position, index in enumerate(visible):
        ranks[index] = int(places[position])
    return ranks


def _letters_coverage(text: str, font_path: str, size_px: int, position: tuple[float, float], width: int,
                      height: int, align: str, spacing_px: int, outline_px: int, hollow: bool, spec: dict[str, Any],
                      seconds: float, scale_px: float) -> np.ndarray:
    """The text drawn letter by letter, each where the whole block would put it, then moved, turned, scaled
    and faded by the animator at its own time (C6b, CT-0078)."""

    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(font_path, size_px)
    big = (width * 4, height * 4)
    canvas = np.zeros((big[1], big[0]), dtype=np.float32)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    box = probe.multiline_textbbox((0, 0), text, font=font, spacing=spacing_px, stroke_width=outline_px)
    across = box[2] - box[0]
    x0 = position[0] * big[0] - {"centre": across / 2, "left": 0.0, "right": across}[align] - box[0]
    y0 = position[1] * big[1] - (box[3] - box[1]) / 2 - box[1]
    line_height = probe.textbbox((0, 0), "A", font=font, stroke_width=outline_px)[3] + outline_px + spacing_px
    lines = text.split("\n")
    widest = max(probe.textlength(line, font=font) for line in lines) if lines else 0.0
    ranks = letter_ranks(text.replace("\n", " "), str(spec.get("order") or "forward"), int(spec.get("seed", 0)))
    stagger, start = float(spec.get("stagger", 0.05)), float(spec.get("start", 0.0))
    flat_index = 0
    for row, line in enumerate(lines):
        width_here = probe.textlength(line, font=font)
        shift = {"centre": (widest - width_here) / 2, "left": 0.0, "right": widest - width_here}[align]
        for column, char in enumerate(line):
            index, flat_index = flat_index, flat_index + 1
            if char.isspace():
                continue
            state = letter_state(spec, seconds - start - ranks[index] * stagger, ranks[index], seconds)
            opacity = float(np.clip(state["opacity"], 0.0, 1.0))
            if opacity <= 0.0:
                continue
            left = x0 + shift + probe.textlength(line[:column], font=font)
            top = y0 + row * line_height
            glyph_box = probe.textbbox((0, 0), char, font=font, stroke_width=outline_px)
            pad = int(size_px * 0.6) + outline_px
            tile_size = (int(glyph_box[2] - glyph_box[0]) + 2 * pad, int(glyph_box[3] - glyph_box[1]) + 2 * pad)
            tile = Image.new("L", tile_size, 0)
            draw = ImageDraw.Draw(tile)
            origin = (pad - glyph_box[0], pad - glyph_box[1])
            draw.text(origin, char, font=font, fill=255, stroke_width=outline_px, stroke_fill=255)
            if hollow and outline_px:
                inner = Image.new("L", tile_size, 0)
                ImageDraw.Draw(inner).text(origin, char, font=font, fill=255)
                tile = Image.fromarray(np.clip(np.asarray(tile, np.int16) - np.asarray(inner, np.int16), 0, 255)
                                       .astype(np.uint8), "L")
            scale = float(np.asarray(state["scale"]).reshape(-1)[0])
            if abs(scale - 1.0) > 1e-3 and scale > 0:
                tile = tile.resize((max(1, int(round(tile.width * scale))), max(1, int(round(tile.height * scale)))),
                                   Image.BILINEAR)
            angle = float(np.asarray(state["rotate"]).reshape(-1)[0])
            if abs(angle) > 1e-3:
                tile = tile.rotate(-angle, resample=Image.BILINEAR, expand=True)
            offset = np.broadcast_to(np.asarray(state["offset"], dtype=np.float64), (2,)) * scale_px * 4
            # The glyph's centre, where the block put it, moved by the offset.
            centre_x = left + glyph_box[0] + (glyph_box[2] - glyph_box[0]) / 2 + offset[0]
            centre_y = top + glyph_box[1] + (glyph_box[3] - glyph_box[1]) / 2 + offset[1]
            x, y = int(round(centre_x - tile.width / 2)), int(round(centre_y - tile.height / 2))
            data = np.asarray(tile, dtype=np.float32) / 255.0 * opacity
            ys = slice(max(0, y), min(big[1], y + tile.height))
            xs = slice(max(0, x), min(big[0], x + tile.width))
            if ys.start < ys.stop and xs.start < xs.stop:
                part = data[ys.start - y:ys.stop - y, xs.start - x:xs.stop - x]
                canvas[ys, xs] = np.maximum(canvas[ys, xs], part)
    reduced = canvas.reshape(height, 4, width, 4).mean(axis=(1, 3))
    return reduced.astype(np.float32)


def text_picture(node: dict[str, Any], param: Callable[..., Any], width: int, height: int,
                 root: Path | None, seconds: float = 0.0) -> np.ndarray:
    """generate.text's picture for one frame: one drawing of a text for every renderer (GL uploads it)."""

    from ..titles import font_file

    text = str(param("text", "")).replace("\\n", "\n")
    reveal = param("reveal", 1.0)
    if reveal is None:
        shown = text
    elif param("reveal_by", "letter") == "word":
        words = text.split(" ")
        shown = " ".join(words[: int(round(len(words) * float(np.clip(reveal, 0, 1))))])
    else:
        shown = text[: int(round(len(text) * float(np.clip(reveal, 0, 1))))]
    size_px = max(4, int(pixels(param("size", 40), height) * 4))
    position = np.broadcast_to(np.asarray(param("position", [0.5, 0.5]), dtype=np.float32), (2,))
    font_path = font_file({"font": node.get("font") or ""}, root)
    align = str(param("align", "centre"))
    spacing_px = int(round(pixels(param("line_spacing", 0.0), height) * 4))
    outline_px = int(round(pixels(param("outline", 0.0), height) * 4))
    colour = np.asarray(param("colour", [1, 1, 1, 1]), dtype=np.float32).reshape(-1)
    tint = np.concatenate([colour[:3], colour[3:4] if colour.size > 3 else [1.0]]).astype(np.float32)
    if colour_glyphs(font_path) and node.get("glyph_colours", True) and not node.get("letters"):
        # A colour font draws in its own colours (C6b stage C): of `colour` it takes the opacity, as a browser
        # does (`glyph_colours: false` draws it in `colour`, a plain font). Its outline is the drawing grown
        # round, in `colour`, beneath it (`hollow`: the outline alone). Its alpha is the text as a matte (a
        # style's fill, rings, glow and shadow), as a plain font's is.
        glyphs = _colour_text(shown, text, font_path, size_px, (float(position[0]), float(position[1])), width,
                              height, align, spacing_px)
        if not outline_px:
            return (glyphs * tint[3]).astype(np.float32)
        grown = _grown(glyphs[..., 3], outline_px / 4)
        ring = np.clip(grown - glyphs[..., 3], 0, 1) if param("hollow", False) else grown
        under = np.concatenate([tint[:3] * ring[..., None], ring[..., None]], axis=-1) * tint[3]
        if param("hollow", False):
            return under.astype(np.float32)
        faded = glyphs * tint[3]
        return (faded + under * (1.0 - faded[..., 3:])).astype(np.float32)
    try:
        if node.get("letters"):
            # Letter by letter, each with its own time (C6b): the animator is the node's, not a curve. A colour
            # font's letters are drawn in `colour` here (a limitation recorded in the roadmap).
            coverage = _letters_coverage(text, font_path, size_px, (float(position[0]), float(position[1])), width,
                                         height, align, spacing_px, outline_px, bool(param("hollow", False)),
                                         node["letters"], seconds, pixels(1.0, height))
        else:
            coverage = _text_coverage(text, shown, font_path, size_px, (float(position[0]), float(position[1])),
                                      width, height, align, spacing_px, outline_px, bool(param("hollow", False)))
    except OSError as error:  # a bitmap font has only the sizes it was drawn at
        raise ValidationError(f"The font {Path(font_path).name} cannot draw this text ({error}); a bitmap colour "
                              "font draws only in its own colours, letter by letter not yet") from error
    alpha = coverage * tint[3]
    return np.concatenate([tint[:3] * alpha[..., None], alpha[..., None]], axis=-1).astype(np.float32)


def _grown(alpha: np.ndarray, radius: float) -> np.ndarray:
    """A matte grown round by `radius` pixels -- a round stroke, as a font's outline is drawn."""

    reach = int(math.ceil(radius))
    if reach <= 0:
        return alpha
    padded = np.pad(alpha, reach)
    height, width = alpha.shape
    out = alpha.copy()
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            weight = float(np.clip(radius + 0.5 - math.hypot(dx, dy), 0.0, 1.0))
            if weight > 0:
                out = np.maximum(out, padded[reach + dy:reach + dy + height, reach + dx:reach + dx + width] * weight)
    return out


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


def source_extents(graph: dict[str, Any], frames: int, fps: float,
                   beats: list[float] | None = None) -> dict[str, tuple[int, int]]:
    """For each source of the graph, the first and last of its local frames the output reads (C7, CT-0080):
    past the shot's end when a remap runs faster, before its start (negative: a pre-roll) when one runs back
    past it -- composed over every path, nested remaps and offsets included (`clock.extents`)."""

    from . import clock

    nodes = graph.get("nodes") or {}
    curve = curve_factory(nodes, {}, fps=fps, length=frames / fps if fps else 0.0, beats=beats,
                          tracks=lambda reference: {"kind": "point", "frames": [{"points": [[0.5, 0.5]]}]},
                          track_entry=lambda reference, seconds: {"points": [[0.5, 0.5]]})
    try:
        return clock.extents(graph, frames, fps, curve)
    except (ValidationError, KeyError, TypeError, ValueError):  # a map that cannot be read ahead: the shot's own
        return {source: (0, frames - 1) for source in clock.sources(graph)}


def reach(graph: dict[str, Any], frames: int, fps: float, beats: list[float] | None = None) -> int:
    """How many frames of its sources, from their local zero, a graph reads to make `frames` frames."""

    return max([frames] + [high + 1 for _, high in source_extents(graph, frames, fps, beats).values()])


def preroll(graph: dict[str, Any], frames: int, fps: float, beats: list[float] | None = None) -> int:
    """How many frames before their local zero a graph reads of its sources (a remap running back past it)."""

    return max([0] + [-low for low, _ in source_extents(graph, frames, fps, beats).values()])


def retimed(graph: dict[str, Any], frames: int, fps: float, beats: list[float] | None = None) -> bool:
    """Whether the graph shows any source at another time than its own: a remap or an offset that moves it by
    half a frame or more at some frame. Its sound is then not the take's at speed 1 (muted, CT-0080)."""

    from . import clock

    nodes = graph.get("nodes") or {}
    if not any(node.get("op") in ("time.remap", "time.offset") for node in nodes.values()):
        return False
    curve = curve_factory(nodes, {}, fps=fps, length=frames / fps if fps else 0.0, beats=beats,
                          tracks=lambda reference: {"kind": "point", "frames": [{"points": [[0.5, 0.5]]}]},
                          track_entry=lambda reference, seconds: {"points": [[0.5, 0.5]]})
    output = str(graph["output"]).split(".")[0]
    half = 0.5 / fps
    for source in clock.sources(graph):
        for frame in range(frames):
            here = clock.centre(frame, fps)
            if any(abs(float(at) - float(here)) >= half - 1e-9
                   for at in clock.instants(nodes, curve, fps, output, source, here)):
                return True
    return False


def shown_instants(graph: dict[str, Any], frames: int, fps: float, source: str, origin: Any,
                   beats: list[float] | None = None) -> tuple[list[list[Any]], Callable[[Any], Any]]:
    """The media instants the graph's output shows of `source` at each output frame's centre (one per path), and
    the map at any output instant (refusing disagreement) -- the shot's sound follows this (CT-0080, step 3)."""

    from . import clock

    nodes = graph.get("nodes") or {}
    curve = curve_factory(nodes, {}, fps=fps, length=frames / fps if fps else 0.0, beats=beats,
                          tracks=lambda reference: {"kind": "point", "frames": [{"points": [[0.5, 0.5]]}]},
                          track_entry=lambda reference, seconds: {"points": [[0.5, 0.5]]})
    output = str(graph["output"]).split(".")[0]
    per_frame = [[clock.media(at, origin) for at in clock.instants(nodes, curve, fps, output, source,
                                                                    clock.centre(frame, fps))]
                 for frame in range(frames)]

    def at(seconds: Any) -> Any:
        local = clock.instant(nodes, curve, fps, output, source, seconds)
        if local is None:
            raise ValidationError(f"{source} is not shown at {float(seconds):.3f} s")
        return clock.media(local, origin)

    return per_frame, at


class Shifted:
    """A source read from before its local zero: local frame `i` is the read clip's frame `i + preroll`, so
    negative local frames -- a pre-roll -- are frames of the media before the cut point (CT-0080)."""

    def __init__(self, clip: Any, preroll: int) -> None:
        self.clip, self.preroll = clip, int(preroll)
        self.shape = (len(clip) - self.preroll,) + tuple(clip.shape[1:])

    def __len__(self) -> int:
        return len(self.clip) - self.preroll

    def __getitem__(self, frame: Any) -> Any:
        return self.clip[max(0, int(frame) + self.preroll)]

    def release_before(self, frame: int) -> None:
        if hasattr(self.clip, "release_before"):
            self.clip.release_before(frame + self.preroll)


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
                  beats: list[float] | None, tracks: Callable[[str], dict[str, Any]],
                  track_entry: Callable[[str, float], dict[str, Any]] | None = None) -> Callable[[str], Callable]:
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
                # Where the track is read: by its clock at the source's instant when the evaluator says (C7,
                # CT-0080); else by the reader's own frame.
                frame = (track_entry(node["track"], seconds) if track_entry is not None else
                         track["frames"][min(int(seconds * fps), len(track["frames"]) - 1)])
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


def read_signal(name: str, node: dict[str, Any], book: "TrackBook", frame: int, fps: float, width: int,
                height: int, root: Path | None, held: dict[str, Any]) -> np.ndarray:
    """A production signal at this frame -- one reading for every renderer: its record checked against what the
    node says (kind, camera), the frame at the media instant its source (`of`) shows, else the graph's own frame;
    resized to the picture -- smoothly for values, to the nearest for labels (CT-0081)."""

    from ..signals import SignalReader

    key = f"signal:{name}"
    if key not in held:
        if root is None:
            raise ValidationError(f"{name} reads the production's signal {node['signal']!r}: give the graph its "
                                  "production")
        reader = SignalReader(root, str(node["signal"]))
        record = reader.record
        if node.get("kind") and node["kind"] != record["kind"]:
            raise ValidationError(f"{name} reads {node['signal']} as {node['kind']}, but it is a {record['kind']}")
        if node.get("camera") and node["camera"] != record.get("camera"):
            raise ValidationError(f"{name} reads {node['signal']} as from the camera {node['camera']!r}, but it is "
                                  f"from {record.get('camera')!r}")
        held[key] = reader
    reader = held[key]
    seconds = (frame + 0.5) / fps
    if node.get("of"):
        data = reader.at(book.media_instant(str(node["of"]).split(".")[0], name, seconds, f"the signal {node['signal']}"))
    else:
        data = reader.frame(frame)
    if data.shape[:2] != (height, width):
        if reader.record["kind"] == "segmentation":
            rows = (np.arange(height) * data.shape[0] // height)[:, None]
            cols = (np.arange(width) * data.shape[1] // width)[None, :]
            data = data[rows, cols]
        else:
            data = Image_resize(data.astype(np.float32), width, height)
    return data.astype(np.int64 if reader.record["kind"] == "segmentation" else np.float32)


class TrackBook:
    """The tracks of a graph, read the one way every renderer reads them (C7, CT-0080): a track's data -- given,
    read from a file, a production's record (validated and corrected by `tracks.load_track`), or measured on
    its input -- and the entry for the instant its source shows when a node is evaluated, by the track's own
    clock (`clock`). Renderers give it how to get a picture of a node at a frame; nothing else differs."""

    def __init__(self, graph: dict[str, Any], inputs: dict[str, Any], *, fps: float, frames: int,
                 root: Path | None, origins: dict[str, Any], working: str,
                 picture_at: Callable[[str, int], np.ndarray]) -> None:
        self.graph, self.nodes = graph, graph.get("nodes") or {}
        self.ports = graph.get("ports") or {}
        self.inputs, self.fps, self.frames, self.root = inputs, fps, frames, root
        self.origins, self.working, self.picture_at = origins, working, picture_at
        self.cache: dict[str, dict[str, Any]] = {}
        self.curve: Callable[[str], Callable] | None = None
        self.reader: list[str | None] = [None]  # the node whose parameters are being read

    def origin_of(self, name: str) -> Fraction:
        """A source's media instant at its local zero: a port's given origin, a `generate.source`'s start."""

        if name in self.origins:
            given = self.origins[name]
            return given if isinstance(given, Fraction) else Fraction(str(given))
        node = self.nodes.get(name, {})
        if node.get("op") == "generate.source":
            return Fraction(str(node.get("start", 0.0)))
        return Fraction(0)

    def described(self, reference: str) -> str | None:
        """What picture a track describes: a read track's `of`, a measured one's input."""

        node = self.nodes.get(reference, {})
        of = node.get("of") if node.get("op") == "track.read" else node.get("in") if node.get("op") == "track.measure" else None
        return str(of).split(".")[0] if of else None

    def entry(self, reference: str, consumer: str | None, seconds: float) -> dict[str, Any]:
        """The track's entry for the instant its source shows when `consumer` is evaluated at `seconds`: by the
        track's own clock, at the source's media instant -- right whether the track was made on the cut, on the
        whole take or elsewhere, whatever remaps stand between. A track with no clock, or not said to describe
        a source, is read by the consumer's frame, as before."""

        from . import clock
        from ..timebase import from_record, rate as exact_rate
        from .semantics import remap_samples

        track = self.track(reference)
        entries = track["frames"]
        of, spec = self.described(reference), track.get("clock")
        frame = int(round(seconds * self.fps - 0.5))
        if not spec or not of or consumer is None:
            return entries[min(max(0, frame), len(entries) - 1)]
        media = self.media_instant(of, consumer, seconds, f"the track {reference}")
        position = media - from_record(spec["origin"])
        index = remap_samples(position, exact_rate(spec["rate"]), "nearest")[0][0]
        return entries[min(index, len(entries) - 1)]

    def media_instant(self, of: str, consumer: str, seconds: float, what: str) -> Any:
        """The instant of `of`'s media shown when `consumer` is evaluated at `seconds`: the walk through every
        time operation between them (`clock`), plus `of`'s origin -- where a track or a signal of that source
        is read (C7, C8)."""

        from . import clock

        nodes, curve, fps = self.nodes, self.curve, self.fps
        if of not in nodes and of not in self.ports:
            raise ValidationError(f"{what} describes {of!r}, which is no node or port")
        here = clock.centre(int(round(seconds * fps - 0.5)), fps)
        local = clock.instant(nodes, curve, fps, consumer, of, here)
        if local is None:
            # Not upstream of its reader (a window pinned on a plate it is laid over): the instant the output
            # shows the source at -- when the reader itself is on the output's time.
            output = str(self.graph["output"]).split(".")[0]
            if output != consumer and clock.instants(nodes, curve, fps, output, consumer, here) not in ([], [here]):
                raise ValidationError(f"{consumer} reads {what} under a time operation that does not reach {of}: "
                                      f"which instant of {of} it describes is ambiguous")
            local = clock.instant(nodes, curve, fps, output, of, here)
            if local is None:
                raise ValidationError(f"{what} describes {of}, which the graph never shows")
        return clock.media(local, self.origin_of(of))

    def track(self, reference: str) -> dict[str, Any]:
        """A track as data (SPEC-0012 §1): {kind, frames: [{points} or {corners}], clock}."""

        if reference in self.cache:
            return self.cache[reference]
        if reference in self.inputs and isinstance(self.inputs[reference], dict):
            self.cache[reference] = self.inputs[reference]
            return self.cache[reference]
        node, root = self.nodes[reference], self.root
        if node["op"] == "track.read" and node.get("track"):
            # A production's track (C7 step 5): measured on its media, corrected by a person, refused when stale.
            from ..tracks import load_track

            if root is None:
                raise ValidationError(f"{reference} reads the production's track {node['track']!r}: give the graph "
                                      "its production")
            self.cache[reference] = load_track(root, str(node["track"]))
        elif node["op"] == "track.read":
            import json

            path = Path(node["file"])
            path = (root / path) if root and not path.is_absolute() else path
            self.cache[reference] = json.loads(path.read_text(encoding="utf-8"))
        else:  # track.measure: OpenCV's, on pictures of its input -- the CPU's, whoever draws
            from ..timebase import ffmpeg_rate, to_record
            from .tracking import measure

            measured = measure(lambda index: self.picture_at(node["in"], index), node["kind"], node.get("region"),
                               self.working, frames=self.frames)
            # Its clock: the input's frames, from the input's media origin (C7, CT-0080).
            source = str(node["in"]).split(".")[0]
            measured["clock"] = {"rate": ffmpeg_rate(self.fps),
                                 "origin": to_record(self.origin_of(source), rounding="half_even")}
            self.cache[reference] = measured
        return self.cache[reference]


def pinned_corners(book: TrackBook, node: dict[str, Any], name: str, seconds: float, fps: float) -> list[list[float]]:
    """A corner pin's corners from its track at `seconds` -- one rule for every renderer:
    - a plane track with no corners given: the picture fills the tracked plane (a screen replaced);
    - a plane track with corners given: those corners carried as the plane has moved since the shot's first frame
      -- the homography from its first corners to its current ones (a window kept on a moving wall, C7);
    - a point track: the given corners moved as the point has moved since the shot's first frame."""

    entry = book.entry(node["track"], name, seconds)
    first = book.entry(node["track"], name, 0.5 / fps)
    if "corners" in entry:
        if not node.get("corners"):
            return [list(map(float, corner)) for corner in entry["corners"]]
        from .warp import homography

        moved = homography(first["corners"], entry["corners"])
        given = np.asarray(node["corners"], np.float64)
        points = np.c_[given, np.ones(len(given))] @ np.asarray(moved, np.float64).T
        return (points[:, :2] / points[:, 2:3]).tolist()
    shift = np.mean(entry["points"], axis=0) - np.mean(first["points"], axis=0)
    return (np.asarray(node.get("corners") or [[0, 0], [1, 0], [1, 1], [0, 1]]) + shift).tolist()


def open_source(path: Path, node: dict[str, Any], name: str, spans: dict[str, tuple[int, int]], extent: int,
                size: tuple[int, int], fps: float, working: str) -> Any:
    """A `generate.source`'s clip, read as far as the graph reaches and, before its start, as far back as a remap
    asks and the file has frames (a pre-roll): one reading for every renderer (C7, CT-0080)."""

    start = float(node.get("start", 0.0))
    wanted = max(0, -spans.get(name, (0, 0))[0])
    early = min(wanted, int(round(start * fps)))
    clip = read(path, extent + early, size, fps, start=start - early / fps, colorspace=node.get("colorspace"),
                alpha=node.get("alpha"), working=working)
    return Shifted(clip, early) if early else clip


def _from_held(held: Any, frame: int) -> Any:
    """A held source's frame: before what it holds, its first (a pre-roll's first when it has one); past its
    end, its last -- for an array, a clip and a shifted clip alike."""

    lowest = -getattr(held, "preroll", 0)
    if frame < lowest:
        frame = lowest
    if isinstance(held, np.ndarray) and frame >= len(held):
        frame = len(held) - 1
    if isinstance(held, np.ndarray) and frame < 0:
        frame = 0
    return held[frame]


def evaluate(graph: dict[str, Any], inputs: dict[str, Any], *, frames: int, size: tuple[int, int], fps: float,
             working: str = LINEAR, root: Path | None = None, beats: list[float] | None = None,
             stream: bool = False, stats: dict[str, int] | None = None, budget: int | None = None,
             origins: dict[str, Any] | None = None) -> Any:
    """The graph's output picture for every frame of its extent: (frames, H, W, 4), linear, premultiplied.

    ``origins`` gives, for a source port, the instant of its media at its local zero (a take's cut point): a
    track with a clock is read at the media instant its source shows (C7, CT-0080).

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
    # How far the sources are read: past the output when a remap or an offset reads ahead (CT-0080).
    extent = reach(graph, frames, fps, beats)
    spans = source_extents(graph, frames, fps, beats)
    origins = dict(origins or {})

    def port_kind(name: str) -> str:
        return str(port_types.get(name, ""))
    curves: dict[str, Callable[[float], Any]] = {}
    clips: dict[str, np.ndarray] = {}
    for name, value in inputs.items():
        if isinstance(value, dict):  # a track, as data
            continue
        if callable(value):
            curves[name] = value
        elif isinstance(value, (Clip, Shifted)):
            clips[name] = value
        elif isinstance(value, np.ndarray):
            per_frame = value.ndim == 4 or (port_kind(name) == "signal" and value.ndim == 3 and value.shape[0] == frames)
            clips[name] = value if per_frame else _Held(value, extent)
        else:
            clips[name] = read(Path(value), extent, size, fps, working=working)
    for name, kind in port_types.items():
        if kind == "curve" and name not in curves:
            curves[name] = lambda seconds: seconds / length if length else 0.0  # a join's progress, by default
        elif kind in ("picture", "matte", "signal") and name not in clips:
            raise ValidationError(f"The graph's port {name!r} was given no {kind}")

    # Tracks, one way for every renderer (C7, CT-0080): read by their clock where their source is shown.
    book = TrackBook(graph, inputs, fps=fps, frames=frames, root=root, origins=origins, working=working,
                     picture_at=lambda name, index: _picture(value(name, index)))
    curve = curve_factory(nodes, curves, fps=fps, length=length, beats=beats, tracks=book.track,
                          track_entry=lambda reference, seconds: book.entry(reference, book.reader[0], seconds))
    book.curve = curve
    tracks = book.track

    def value(reference: str, frame: int) -> Any:
        if reference in clips:
            return _from_held(clips[reference], frame)
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
                book.reader[0] = name
                return curve(given["curve"])(seconds)
            return given

        if op == "generate.source":
            if name not in clips:
                path = Path(node.get("file") or node.get("take"))
                path = (root / path) if root and not path.is_absolute() else path
                clips[name] = open_source(path, node, name, spans, extent, size, fps, working)
            return _from_held(clips[name], frame)
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
            x = np.clip(x, 0, 1)
            out = gradient_colours(colours, x, param("at", None))
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
                             aspect=aspect, skew=float(param("skew", 0.0) or 0.0))
        if op == "warp.corner_pin":
            from .warp import corner_pin

            if node.get("track"):
                corners = pinned_corners(book, node, name, seconds, fps)
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
            return text_picture(node, param, width, height, root, seconds)
        if op == "signal.read" and node.get("signal"):
            # A production's signal (C8 step 1): checked once, read at the instant its source shows.
            return read_signal(name, node, book, frame, fps, width, height, root, clips)
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
            return rebuilt(lut_colours(node, rgb, working, root), alpha)
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
            # The hue turned, degrees per second (`semantics.hue_turn`: one matrix for both renderers).
            matrix = np.asarray(hue_turn(float(param("speed", 90.0)) * seconds), dtype=np.float32)
            return rebuilt(np.clip(rgb @ matrix.T, 0, None), alpha)
        if op == "filter.bevel":
            picture = _picture(value(node["in"], frame))
            height_px = pixels(param("radius", 6.0), height)
            relief = _blur(picture[..., 3], height_px)
            return bevel_lit(picture, relief, height_px, param)
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
        if op == "time.offset":
            return value(node["in"], frame - int(param("frames", 0)))
        if op == "time.remap":
            # Which source instant (the map), then how it is pictured (the interpolation): two decisions.
            from . import clock
            from .semantics import remap_samples

            samples = remap_samples(clock.remap_at(node, nodes, curve, clock.centre(frame, fps)), fps,
                                    str(node.get("interpolation") or "nearest"), clamp=False)
            # Before what the source holds: its first frame; past its end (a blend's second frame on the last):
            # its last -- whoever holds it (`_from_held`).
            parts = [(value(node["in"], index), weight) for index, weight in samples]
            if len(parts) == 1:
                return parts[0][0]
            return sum(np.asarray(part, dtype=np.float32) * weight for part, weight in parts)
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
                if isinstance(clip, (Clip, Shifted)):
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
           cache: Path | None | bool = True, renderer: Any = None,
           origins: dict[str, Any] | None = None) -> tuple[np.ndarray, str, bool]:
    """`evaluate`, kept by the output's identity (SPEC-0012 §5): (pictures, identity, whether it was cached).

    The cache is disposable: deleting it costs time only. An input with no identity (a curve given as
    code) makes the result uncacheable, and it is computed every time.
    """

    from .identity import REFERENCE_VERSION, identities
    from .natron import has_plugins, stage

    if has_plugins(graph):
        # OpenFX plugins run by Natron first, over what feeds them; the rest is drawn as any graph is.
        graph, inputs = stage(graph, inputs, frames=frames, size=size, fps=fps, root=root, beats=beats)
    known = {name: _input_identity(value) for name, value in inputs.items()}
    # Another renderer (GL) draws the same graph; its results are kept apart from the reference's.
    # Sources' media origins: where tracks are read (C7, CT-0080) -- by every renderer.
    draw = (lambda *args, **kwargs: (renderer.evaluate if renderer is not None else evaluate)(
        *args, origins=origins, **kwargs))
    context = {"renderer": f"gl/{renderer.name}" if renderer is not None else REFERENCE_VERSION, "numpy": np.__version__, "working": working, "fps": fps,
               "frames": frames, "size": list(size), "beats": list(beats or []),
               "origins": {name: str(value) for name, value in sorted((origins or {}).items())}}
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
