"""Turn a production's composed shots into a file someone can watch.

A demo that does not build proves nothing. The reel declares four cards, four
transitions and a narration track; until something renders them, all of that is
a claim about a YAML file.

This renders the simplest honest case: composed shots -- cards drawn from data
rather than generated -- cut together on transitions the catalog declares, with
the production's audio mixed underneath. Generated and captured shots are not
handled here; they arrive as takes and are assembled by a different path.

Nothing is inferred. A transition renders the way its own manifest says it
renders on this engine, and a transition that declares no rendering for the
engine in use is refused rather than quietly replaced by a cut.

Two engines exist. The GL engine runs a GLSL transition's own shader over the
real frames (ModernGL, the `gpu` extra); the FFmpeg engine runs the stand-in
the manifest declares. `auto` uses GL when a context can be created.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .errors import CineToasterError
from .looks import load_looks
from .project import load_production
from .shader_render import ShaderTransition, gl_unavailable_reason
from .transitions import list_transitions


ENGINES = ("auto", "gl", "ffmpeg")
RENDERS_DIRECTORY = "renders"
STILLS_DIRECTORY = "stills"
WIDTH, HEIGHT, FPS = 1280, 720, 30


class BuildError(CineToasterError):
    """The production cannot be rendered as asked."""

    code = "build_failed"
    http_status = 422


class BuildCancelled(BuildError):
    """The caller asked the build to stop."""

    code = "build_cancelled"
    http_status = 409


class BuildNotPossible(BuildError):
    """Something the render needs is not installed."""

    code = "build_not_possible"
    http_status = 400


@dataclass(frozen=True, slots=True)
class BuildResult:
    output: Path
    shots: int
    transitions: int
    duration_seconds: float
    audio: bool
    stills: int = 0
    engine: str = "ffmpeg"
    shaders: int = 0

    def public_dict(self) -> dict[str, Any]:
        return {
            "output": str(self.output),
            "shots": self.shots,
            "transitions": self.transitions,
            "duration_seconds": self.duration_seconds,
            "audio": self.audio,
            "stills": self.stills,
            "engine": self.engine,
            "shaders": self.shaders,
        }


@dataclass(frozen=True, slots=True)
class Join:
    """How the render makes one transition: a shader, or an FFmpeg xfade mode."""

    transition_id: str
    seconds: float
    ffmpeg_mode: str | None = None
    shader: Path | None = None
    params: list[dict[str, Any]] = field(default_factory=list)


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise BuildNotPossible(
            "FFmpeg is needed to encode a render. "
            "Linux: sudo apt install ffmpeg | macOS: brew install ffmpeg"
        )
    return path


def _pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:
        raise BuildNotPossible(
            "Drawing a card needs the media extra. "
            "uv sync --extra media   (or: pip install -e '.[media]')"
        ) from error
    return Image, ImageDraw, ImageFont


def _run(command: list[str], what: str) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if completed.returncode != 0:
        tail = (completed.stderr or "").strip().splitlines()[-4:]
        raise BuildError(f"{what} failed: {' / '.join(tail)}")


def _hex(value: str, fallback: str) -> str:
    text = str(value or fallback)
    return text if text.startswith("#") and len(text) == 7 else fallback


def draw_card(shot: dict[str, Any], look: dict[str, Any] | None, destination: Path) -> Path:
    """One frame, drawn from what the shot and the look declare.

    A card is data, not a generated image: the same shot drawn twice is the
    same card, which is what makes a reel reproducible.
    """

    Image, ImageDraw, ImageFont = _pillow()
    palette = (look or {}).get("palette") or {}
    background = _hex(palette.get("background"), "#0b0b16")
    ink = _hex(palette.get("ink"), "#f2ead9")
    accent = _hex(palette.get("accent"), "#38b6a8")

    image = Image.new("RGB", (WIDTH, HEIGHT), background)
    draw = ImageDraw.Draw(image)

    text = shot.get("text") or {}
    if shot.get("engine") == "solid" and not text:
        image.save(destination)
        return destination

    headline = str(text.get("headline") or "").upper()
    subhead = str(text.get("subhead") or "")
    body = str(text.get("body") or "")

    def font(size: int):
        for name in (
            "DejaVuSansCondensed-Bold.ttf",
            "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf",
        ):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default(size)

    y = HEIGHT // 2 - 90
    if headline:
        draw.text((90, y), headline, font=font(88), fill=ink)
        y += 110
    if subhead:
        draw.text((92, y), subhead, font=font(30), fill=accent)
        y += 50
    if body:
        draw.text((92, y), body, font=font(26), fill=ink)

    draw.rectangle([(90, HEIGHT - 90), (90 + 160, HEIGHT - 86)], fill=accent)
    image.save(destination)
    return destination


def _renderable_shots(production: dict[str, Any]) -> list[tuple[dict, dict]]:
    pairs = []
    for scene in production["scenes"]:
        for shot in scene["shots"]:
            if shot.get("source") != "composed":
                continue
            pairs.append((scene, shot))
    return pairs


def _transition_for(
    shot: dict[str, Any],
    catalog: dict[str, dict],
    gl: bool = False,
) -> Join | None:
    reference = shot.get("transition")
    if not reference or not reference.get("id"):
        return None
    item = catalog.get(reference["id"])
    if item is None:
        raise BuildError(
            f"Shot {shot['id']} asks for transition {reference['id']!r}, which is in no catalog."
        )
    milliseconds = reference.get("duration_ms") or item.get("duration_ms") or 1000
    seconds = float(milliseconds) / 1000.0
    if gl and item["kind"] == "glsl":
        return Join(item["id"], seconds, shader=item["asset_path"], params=item.get("params") or [])
    mode = (item.get("render") or {}).get("ffmpeg")
    if not mode:
        engine_hint = (
            " Install the gpu extra so the GL engine can run its shader."
            if item["kind"] == "glsl" else ""
        )
        raise BuildError(
            f"Transition {item['id']!r} declares no FFmpeg rendering, so this engine cannot "
            f"execute it. Add [render].ffmpeg to its manifest, or render with an engine that "
            f"runs {item['kind']}.{engine_hint}"
        )
    return Join(item["id"], seconds, ffmpeg_mode=str(mode))


def _engine(requested: str) -> bool:
    """True when the GL engine will run the shaders."""

    if requested not in ENGINES:
        raise BuildError(f"Unknown engine {requested!r}; choose one of {', '.join(ENGINES)}.")
    if requested == "ffmpeg":
        return False
    reason = gl_unavailable_reason()
    if reason and requested == "gl":
        raise BuildNotPossible(f"The GL engine cannot run: {reason}.")
    return reason is None


def build(
    root: Path,
    output: Path | None = None,
    engine: str = "auto",
    *,
    work: Path | None = None,
    progress: Callable[[float, str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> BuildResult:
    """Render the production's composed shots into one file.

    ``work`` moves the scratch directory out of the project, which a job does
    so that its only write into the production is the adoption. ``progress``
    and ``should_stop`` are called between steps: a running FFmpeg step
    finishes before a stop is honoured.
    """

    def step(fraction: float, message: str) -> None:
        if should_stop and should_stop():
            raise BuildCancelled("The build was cancelled.")
        if progress:
            progress(fraction, message)

    root = Path(root).expanduser().resolve()
    ffmpeg = _ffmpeg()
    gl = _engine(engine)
    production = load_production(root)
    looks = {name: look.public_dict() for name, look in load_looks(root).items()}
    catalog = {item["id"]: item for item in list_transitions(root)}

    pairs = _renderable_shots(production)
    if not pairs:
        raise BuildError(
            "Nothing to build: this production has no composed shots. Generated and "
            "captured shots are assembled from takes, not rendered from data."
        )

    work = Path(work) if work else root / RENDERS_DIRECTORY / ".work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    segments: list[Path] = []
    stills: list[Path] = []
    transitions: list[Join | None] = []
    durations: list[float] = []

    for index, (scene, shot) in enumerate(pairs):
        step(0.8 * index / len(pairs), f"Encoding shot {shot['id']}")
        # The card is kept, not discarded with the scratch directory. Without
        # it a composed scene is text on a screen: there is no take to look at,
        # so the frame the tool drew is the only visual feedback there is.
        stills_directory = root / STILLS_DIRECTORY / scene["id"]
        stills_directory.mkdir(parents=True, exist_ok=True)
        card = draw_card(
            shot,
            looks.get(shot.get("look") or ""),
            stills_directory / f"{shot['id']}.png",
        )
        seconds = float(shot.get("duration_seconds") or 2.0)
        segment = work / f"{index:03d}.mp4"
        _run(
            [
                ffmpeg, "-y", "-loglevel", "error",
                "-loop", "1", "-framerate", str(FPS), "-t", f"{seconds}", "-i", str(card),
                "-vf", f"scale={WIDTH}:{HEIGHT},format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-r", str(FPS),
                str(segment),
            ],
            f"Encoding shot {shot['id']}",
        )
        segments.append(segment)
        stills.append(card)
        durations.append(seconds)
        transitions.append(_transition_for(shot, catalog, gl) if index else None)

    step(0.8, "Cutting the shots together")
    video = work / "video.mp4"
    shaders = sum(1 for join in transitions if join and join.shader)
    if shaders:
        _assemble(ffmpeg, segments, transitions, durations, video, work)
    else:
        _concatenate(ffmpeg, segments, transitions, durations, video)

    step(0.95, "Mixing")
    audio = _production_audio(production, root)
    destination = Path(output) if output else root / RENDERS_DIRECTORY / f"{production['id']}.mp4"
    destination.parent.mkdir(parents=True, exist_ok=True)

    if audio:
        _run(
            [
                ffmpeg, "-y", "-loglevel", "error",
                "-i", str(video), "-i", str(audio),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-shortest",
                str(destination),
            ],
            "Mixing audio",
        )
    else:
        shutil.copy(video, destination)

    shutil.rmtree(work, ignore_errors=True)
    return BuildResult(
        output=destination,
        shots=len(segments),
        transitions=sum(1 for item in transitions if item),
        duration_seconds=_probe_seconds(destination),
        audio=bool(audio),
        stills=len(stills),
        engine="gl" if gl else "ffmpeg",
        shaders=shaders,
    )


def _concatenate(
    ffmpeg: str,
    segments: list[Path],
    transitions: list[Join | None],
    durations: list[float],
    destination: Path,
) -> None:
    """Chain the segments, overlapping each pair by its transition's length."""

    if len(segments) == 1:
        shutil.copy(segments[0], destination)
        return

    inputs: list[str] = []
    for segment in segments:
        inputs.extend(["-i", str(segment)])

    steps: list[str] = []
    label = "0:v"
    offset = 0.0
    for index in range(1, len(segments)):
        join = transitions[index]
        mode, seconds = (join.ffmpeg_mode, join.seconds) if join else ("fade", 0.0)
        offset += durations[index - 1] - seconds
        output_label = f"v{index}"
        if seconds <= 0:
            steps.append(f"[{label}][{index}:v]xfade=transition=fade:duration=0.04:"
                         f"offset={max(offset - 0.04, 0):.3f}[{output_label}]")
        else:
            steps.append(f"[{label}][{index}:v]xfade=transition={mode}:duration={seconds:.3f}:"
                         f"offset={max(offset, 0):.3f}[{output_label}]")
        label = output_label

    _run(
        [
            ffmpeg, "-y", "-loglevel", "error", *inputs,
            "-filter_complex", ";".join(steps),
            "-map", f"[{label}]",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            str(destination),
        ],
        "Cutting the shots together",
    )


_ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def _assemble(
    ffmpeg: str,
    segments: list[Path],
    joins: list[Join | None],
    durations: list[float],
    destination: Path,
    work: Path,
) -> None:
    """Cut the film as pieces: each shot's body, and each join as its own clip.

    A join replaces the outgoing shot's last frames and the incoming shot's
    first ones, as an xfade overlap does, so the running time is the same on
    both engines. A join is rendered by its shader or by its FFmpeg stand-in;
    the two can meet in one film.
    """

    frames = [round(seconds * FPS) for seconds in durations]
    overlap = [0] + [round(join.seconds * FPS) if join else 0 for join in joins[1:]]
    overlap.append(0)
    pieces: list[Path] = []
    for index, segment in enumerate(segments):
        start, end = overlap[index], frames[index] - overlap[index + 1]
        if end < start:
            raise BuildError(
                f"Shot {index + 1} is {durations[index]:.2f}s, shorter than the transitions "
                f"into and out of it together."
            )
        if end > start:
            body = work / f"body-{index:03d}.mp4"
            _run(
                [ffmpeg, "-y", "-loglevel", "error", "-i", str(segment),
                 "-vf", f"trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS",
                 *_ENCODE, str(body)],
                f"Trimming shot {index + 1}",
            )
            pieces.append(body)
        join = joins[index + 1] if index + 1 < len(segments) else None
        if join and overlap[index + 1]:
            clip = work / f"join-{index + 1:03d}.mp4"
            count = overlap[index + 1]
            if join.shader:
                _shader_join(ffmpeg, segment, segments[index + 1], frames[index], count, join, clip)
            else:
                tail = frames[index] - count
                _run(
                    [ffmpeg, "-y", "-loglevel", "error", "-i", str(segment), "-i", str(segments[index + 1]),
                     "-filter_complex",
                     f"[0:v]trim=start_frame={tail}:end_frame={frames[index]},setpts=PTS-STARTPTS[a];"
                     f"[1:v]trim=end_frame={count},setpts=PTS-STARTPTS[b];"
                     f"[a][b]xfade=transition={join.ffmpeg_mode}:duration={count / FPS:.3f}:offset=0[v]",
                     "-map", "[v]", "-frames:v", str(count), *_ENCODE, str(clip)],
                    f"Rendering {join.transition_id}",
                )
            pieces.append(clip)

    listing = work / "pieces.txt"
    listing.write_text("".join(f"file '{piece.name}'\n" for piece in pieces), encoding="utf-8")
    _run(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(destination)],
        "Cutting the shots together",
    )


def _frames(ffmpeg: str, source: Path, start: int, end: int) -> list[bytes]:
    """Frames [start, end) of a clip as packed RGB, bottom row first for GL."""

    completed = subprocess.run(
        [ffmpeg, "-loglevel", "error", "-i", str(source),
         "-vf", f"trim=start_frame={start}:end_frame={end},scale={WIDTH}:{HEIGHT},vflip",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, timeout=900,
    )
    if completed.returncode != 0:
        raise BuildError(f"Reading frames from {source.name} failed: {completed.stderr.decode()[-300:]}")
    size = WIDTH * HEIGHT * 3
    data = completed.stdout
    return [data[offset:offset + size] for offset in range(0, len(data) - size + 1, size)]


def _shader_join(
    ffmpeg: str, outgoing: Path, incoming: Path, outgoing_frames: int, count: int, join: Join, clip: Path
) -> None:
    tail = _frames(ffmpeg, outgoing, outgoing_frames - count, outgoing_frames)
    head = _frames(ffmpeg, incoming, 0, count)
    if not tail or not head:
        raise BuildError(f"No frames to run {join.transition_id} over.")
    renderer = ShaderTransition(join.shader, join.params, WIDTH, HEIGHT)
    encoder = subprocess.Popen(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-", "-vf", "vflip", *_ENCODE, str(clip)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        for frame in range(count):
            # Never exactly 0 or 1: every frame of the join is part of the change.
            progress = (frame + 1) / (count + 1)
            a = tail[min(frame, len(tail) - 1)]
            b = head[min(frame, len(head) - 1)]
            encoder.stdin.write(renderer.render(a, b, progress))
        encoder.stdin.close()
        if encoder.wait(timeout=900) != 0:
            raise BuildError(f"Encoding {join.transition_id} failed: {encoder.stderr.read().decode()[-300:]}")
    finally:
        renderer.release()
        if encoder.poll() is None:
            encoder.kill()
            encoder.wait()
        encoder.stderr.close()


def _production_audio(production: dict[str, Any], root: Path) -> Path | None:
    """The first spoken line that actually exists on disk.

    Deliberately simple: a real mix is a later tier, and pretending to have one
    would hide that.
    """

    for scene in production["scenes"]:
        for shot in scene["shots"]:
            for line in shot.get("lines") or []:
                target = (line.get("mix") or {}).get("file")
                if not target:
                    continue
                path = root / target
                if path.is_file():
                    return path
    return None


def _probe_seconds(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    completed = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    try:
        return round(float(completed.stdout.strip()), 3)
    except ValueError:
        return 0.0
