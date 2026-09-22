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
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import CineToasterError
from .looks import load_looks
from .project import load_production
from .transitions import list_transitions


RENDERS_DIRECTORY = "renders"
STILLS_DIRECTORY = "stills"
WIDTH, HEIGHT, FPS = 1280, 720, 30


class BuildError(CineToasterError):
    """The production cannot be rendered as asked."""

    code = "build_failed"
    http_status = 422


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

    def public_dict(self) -> dict[str, Any]:
        return {
            "output": str(self.output),
            "shots": self.shots,
            "transitions": self.transitions,
            "duration_seconds": self.duration_seconds,
            "audio": self.audio,
            "stills": self.stills,
        }


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
) -> tuple[str, float] | None:
    reference = shot.get("transition")
    if not reference or not reference.get("id"):
        return None
    item = catalog.get(reference["id"])
    if item is None:
        raise BuildError(
            f"Shot {shot['id']} asks for transition {reference['id']!r}, which is in no catalog."
        )
    mode = (item.get("render") or {}).get("ffmpeg")
    if not mode:
        raise BuildError(
            f"Transition {item['id']!r} declares no FFmpeg rendering, so this engine cannot "
            f"execute it. Add [render].ffmpeg to its manifest, or render with an engine that "
            f"runs {item['kind']}."
        )
    milliseconds = reference.get("duration_ms") or item.get("duration_ms") or 1000
    return str(mode), float(milliseconds) / 1000.0


def build(root: Path, output: Path | None = None) -> BuildResult:
    """Render the production's composed shots into one file."""

    root = Path(root).expanduser().resolve()
    ffmpeg = _ffmpeg()
    production = load_production(root)
    looks = {name: look.public_dict() for name, look in load_looks(root).items()}
    catalog = {item["id"]: item for item in list_transitions(root)}

    pairs = _renderable_shots(production)
    if not pairs:
        raise BuildError(
            "Nothing to build: this production has no composed shots. Generated and "
            "captured shots are assembled from takes, not rendered from data."
        )

    work = root / RENDERS_DIRECTORY / ".work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    segments: list[Path] = []
    stills: list[Path] = []
    transitions: list[tuple[str, float] | None] = []
    durations: list[float] = []

    for index, (scene, shot) in enumerate(pairs):
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
        transitions.append(_transition_for(shot, catalog) if index else None)

    video = work / "video.mp4"
    _concatenate(ffmpeg, segments, transitions, durations, video)

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
    )


def _concatenate(
    ffmpeg: str,
    segments: list[Path],
    transitions: list[tuple[str, float] | None],
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
        transition = transitions[index]
        mode, seconds = transition if transition else ("fade", 0.0)
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
