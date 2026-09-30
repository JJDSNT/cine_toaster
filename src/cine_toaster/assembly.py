"""A scene's cut, assembled from the takes chosen for its shots.

Every assembly is a **version**: rendered to its own file, never overwritten,
and registered with the takes it was built from (`record_assembly`), so a
version can be watched, judged, compared and restored.

How a take is cut (CT-0039, from SINGULAR's practice):

- an explicit `trim` wins: `{in, out}`, `{head, tail}`, or `before`/`after`
  around speech, with `to_end` to keep the take's tail;
- a shot that **declares** speech in its take is cut around the spoken words,
  never through them: from a moment before the first word to a moment after
  the last. Words come from a sidecar beside the take. Detected words alone do
  not count: a model sometimes murmurs in a shot written as silent;
- otherwise the shot's duration is taken, after the generation's still
  opening (a generated take eases out of its first frame).

Each take's sound is set to a loudness: speech to −20 LUFS, measured on the
speech only; other sound to the shot's `level_db` (−34 by default), with only
a small boost, so a silent room's hiss is not raised.

A shot decided to be heard in the cast's own voices (`set_voice`, CT-0040)
takes its sound from the chosen take with each speaker's voice converted;
the job does the conversion and keeps it in a disposable cache.

Shots are joined with straight cuts. Transitions and split edits (J/L) are
listed as not rendered yet, not approximated. Picture is normalised to the
first take's size and frame rate, sound to 48 kHz stereo.

A production's own montage tools can register their renders as versions too;
this module is not the only way a version is made.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ValidationError

FPS = 24
#: A generated take opens on its still first frame (SINGULAR: 0.35 s).
OPENING_SECONDS = 0.35
#: Kept around declared speech, before the first word and after the last.
SPEECH_BEFORE = 1.0
SPEECH_AFTER = 0.9
SPEECH_LUFS = -20.0
AMBIENT_LUFS = -34.0


@dataclass(slots=True)
class Segment:
    shot: str
    take: str
    media: str
    start: float
    end: float
    join: str = "hard"
    method: str = "duration"
    speech: tuple[float, float] | None = None
    level: float | None = None
    #: Scene versions in a sequence were levelled when they were assembled.
    normalize: bool = True
    #: The speech is heard in the cast's own voices (CT-0040): `sound` is then
    #: the take's sound with the voices converted, on the take's own timeline.
    revoice: bool = False
    sound: str = ""
    #: A title from the catalog (CT-0031): drawn on its own card, or over the take.
    title: dict[str, Any] | None = None
    #: The file actually cut, when it is not the take itself (a rendered card or titled piece).
    source: str = ""


@dataclass(slots=True)
class Plan:
    scene: str
    segments: list[Segment] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    gains: dict[str, float] = field(default_factory=dict)

    @property
    def takes(self) -> dict[str, str]:
        # A title card is drawn, not chosen: it has no take to remember.
        return {segment.shot: segment.take for segment in self.segments if segment.method != "title"}

    @property
    def duration(self) -> float:
        return round(sum(segment.end - segment.start for segment in self.segments), 3)


def probe(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise ValidationError("ffprobe is needed to assemble a cut (it ships with FFmpeg)")
    completed = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    data = json.loads(completed.stdout or "{}")
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    rate = video.get("r_frame_rate") or f"{FPS}/1"
    numerator, _, denominator = rate.partition("/")
    return {
        "duration": float((data.get("format") or {}).get("duration") or 0.0),
        "audio": any(s.get("codec_type") == "audio" for s in streams),
        "width": int(video.get("width") or 1280),
        "height": int(video.get("height") or 720),
        "fps": round(float(numerator) / float(denominator or 1), 3) if numerator else FPS,
    }


def words_for(media: Path, pattern: str) -> list[tuple[float, float]]:
    """Word timings beside a take, as (start, end) seconds; empty when there are none."""

    sidecar = media.parent / pattern.format(stem=media.stem, name=media.name)
    if not sidecar.is_file():
        return []
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    words = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            words.append((float(item[0]), float(item[1])))
        elif isinstance(item, dict) and "start" in item and "end" in item:
            words.append((float(item["start"]), float(item["end"])))
    return sorted(words)


def _cut(trim: dict[str, Any], length: float, duration: float, words: list[tuple[float, float]],
         opening: float) -> tuple[float, float, str, str]:
    """(start, end, method, note) for one take."""

    before = float(trim.get("before", SPEECH_BEFORE))
    after = float(trim.get("after", SPEECH_AFTER))
    to_end = bool(trim.get("to_end"))
    if "in" in trim:
        start, method = float(trim["in"]), "trim"
        if "out" in trim:
            end = float(trim["out"])
        elif to_end:
            end = length
        elif words:
            end, method = words[-1][1] + after, "trim+speech"
        else:
            end = start + (duration or length)
    elif "out" in trim:
        start, end, method = opening, float(trim["out"]), "trim"
    elif "head" in trim or "tail" in trim:
        start, end, method = float(trim.get("head", opening)), length - float(trim.get("tail", 0.0)), "trim"
    elif words:
        start = max(opening, words[0][0] - before)
        end, method = (length if to_end else words[-1][1] + after), "speech"
    else:
        start, method = opening, "duration"
        end = start + duration if duration else length
    note = ""
    if end > length + 0.01:
        note = f"runs {end - length:.2f} s past the end of its take; cut at the take's end"
        end = length
    if end - start < 1 / FPS:
        raise ValidationError(f"The cut leaves nothing of the take ({start:.2f}–{end:.2f} s of {length:.2f} s)")
    return round(start, 3), round(end, 3), method, note


def _trim(raw: Any, length: float, duration: float) -> tuple[float, float, str]:
    """The cut of a take with no speech and no opening (kept for callers and tests)."""

    start, end, _, note = _cut(raw if isinstance(raw, dict) else {}, length, duration, [], 0.0)
    return start, end, note


def _speaks(shot: dict[str, Any]) -> bool:
    """Whether the shot declares someone speaking in the take itself."""

    if any(line.get("in_take", True) for line in shot.get("lines") or []):
        return True
    return bool((shot.get("script") or {}).get("dialogue"))


def plan_scene(root: Path, scene: dict[str, Any], words_sidecar: str = "{stem}.words.json") -> Plan:
    """Which take of each shot, cut where, joined how."""

    plan = Plan(scene=scene["id"])
    cuts = {cut["to"]: cut for cut in scene.get("cuts") or []}
    for shot in scene["shots"]:
        if shot.get("out_of_cut"):
            continue
        takes = [take for take in shot.get("takes") or [] if take.get("media")]
        chosen = next((take for take in takes if take.get("selected")), None)
        if chosen is None:
            chosen = next((take for take in takes if take["id"] == "CUT"), None)
        title = shot.get("title") if isinstance(shot.get("title"), dict) and not shot["title"].get("unknown") else None
        if chosen is None and title:
            # A card: the title drawn over its background, as long as the shot plays.
            length = float(shot.get("duration_seconds") or 0) or 3.0
            cut = cuts.get(shot["id"]) or {}
            plan.segments.append(Segment(shot["id"], "TITLE", "", 0.0, length, cut.get("type") or "hard", "title",
                                         None, shot.get("level_db"), title=title))
            continue
        if chosen is None:
            if shot.get("source") == "composed":
                plan.notes.append(f"{shot['id']} is composed (a card); its card is not part of a take cut yet.")
            else:
                plan.notes.append(f"{shot['id']} has no take to use; it is left out of this version.")
            continue
        path = root / chosen["media"]
        info = probe(path)
        speaks = _speaks(shot)
        words = words_for(path, words_sidecar) if speaks else []
        if speaks and not words:
            plan.notes.append(f"{shot['id']} speaks, but its take has no word timings; cut by duration.")
        opening = OPENING_SECONDS if shot.get("source") == "generated" else 0.0
        start, end, method, note = _cut(shot.get("trim") or {}, info["duration"],
                                        float(shot.get("duration_seconds") or 0), words, opening)
        spoken = [(a, b) for a, b in words if a >= start - 0.05 and b <= end + 0.05]
        if note:
            plan.notes.append(f"{shot['id']} {note}.")
        cut = cuts.get(shot["id"]) or {}
        join = cut.get("type") or "hard"
        if plan.segments and join in ("j", "l"):
            plan.notes.append(f"{shot['id']}: the {join.upper()}-cut is rendered as a straight cut in this version.")
        transition = (cut.get("transition") or {}).get("id")
        if plan.segments and transition:
            plan.notes.append(f"{shot['id']}: the transition {transition!r} is not rendered in this version.")
        plan.segments.append(Segment(
            shot["id"], chosen["id"], chosen["media"], start, end, join, method,
            (spoken[0][0], spoken[-1][1]) if spoken else None, shot.get("level_db"),
            revoice=bool(shot.get("voice_in_cut")), title=title,
        ))
    if not plan.segments:
        raise ValidationError(f"{scene['id']} has no shot with a take to assemble")
    return plan


def loudness_gain(source: Path, segment: Segment) -> float:
    """dB to bring the take to its loudness: speech measured on the speech alone."""

    ffmpeg = shutil.which("ffmpeg")
    begin, finish = segment.speech or (segment.start, segment.end)
    target = SPEECH_LUFS if segment.speech else (segment.level if segment.level is not None else AMBIENT_LUFS)
    completed = subprocess.run(
        [ffmpeg, "-hide_banner", "-ss", f"{begin:.3f}", "-t", f"{max(0.4, finish - begin):.3f}", "-i", str(source),
         "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True, timeout=120)
    measured = re.findall(r"I:\s+(-?[\d.]+) LUFS", completed.stderr)
    if not measured or float(measured[-1]) < -60:
        return 0.0
    ceiling = 12.0 if segment.speech or segment.level is not None else 3.0
    return round(max(-12.0, min(ceiling, target - float(measured[-1]))), 1)


def _draw_title(root: Path, segment: Segment, output: Path, first: dict[str, Any], fps: float, run_process) -> None:
    """Render a segment's title: a card on its own, or over the cut piece of its take, sound kept.

    The segment is then cut from that file, which starts where the cut does.
    """

    from .titles import render as render_title

    length = segment.end - segment.start
    background = None
    if segment.media:
        # A take whose voice was converted is titled over the converted sound.
        background = Path(segment.sound) if segment.sound else root / segment.media
        if segment.sound:
            muxed = output.with_suffix(".voice.mp4")
            run_process(["ffmpeg", "-y", "-loglevel", "error", "-i", str(root / segment.media), "-i", str(segment.sound),
                         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-shortest", str(muxed)],
                        message=f"{segment.shot}: the converted voice under the picture")
            background = muxed
    render_title(segment.title, length, output, width=first["width"] // 2 * 2, height=first["height"] // 2 * 2,
                 background=background, start=segment.start, root=root, fps=round(fps) or FPS,
                 run=lambda command: run_process(command, expected_seconds=length,
                                                 message=f"{segment.shot}: title {segment.title['id']}"))
    if segment.speech:
        segment.speech = (segment.speech[0] - segment.start, segment.speech[1] - segment.start)
    segment.source, segment.start, segment.end = str(output), 0.0, length


def render(root: Path, plan: Plan, output: Path, work: Path, run_process,
           span: tuple[float, float] = (0.0, 1.0)) -> None:
    """Cut each take, normalise it, and join the pieces without re-encoding twice.

    ``run_process(command, expected_seconds=..., message=..., span=...)`` is
    the job's process runner, so progress and cancellation work per piece;
    ``span`` is the part of the job's progress the render takes.
    """

    def within(a: float, b: float) -> tuple[float, float]:
        return span[0] + (span[1] - span[0]) * a, span[0] + (span[1] - span[0]) * b

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValidationError("FFmpeg is needed to assemble a cut")
    work.mkdir(parents=True, exist_ok=True)
    real = next((segment for segment in plan.segments if segment.media), None)
    first = probe(root / real.media) if real else {"width": 1280, "height": 720, "fps": FPS, "audio": False}
    size = f"{first['width'] // 2 * 2}:{first['height'] // 2 * 2}"
    fps = first["fps"] or FPS
    pieces = []
    segment_gain: dict[str, float] = {}
    plan.gains = segment_gain
    total = len(plan.segments)
    for index, segment in enumerate(plan.segments):
        if segment.title and not segment.source:
            _draw_title(root, segment, work / f"title-{index:03d}.mp4", first, fps, run_process)
        source = Path(segment.source) if segment.source else root / segment.media
        sound = Path(segment.sound) if segment.sound and not segment.source else None
        has_audio = bool(sound) or probe(source)["audio"]
        length = segment.end - segment.start
        gain = loudness_gain(sound or source, segment) if has_audio and segment.normalize else 0.0
        segment_gain[segment.shot] = gain
        piece = work / f"piece-{index:03d}.mp4"
        command = [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{segment.start:.3f}", "-t", f"{length:.3f}", "-i", str(source)]
        if sound:
            command += ["-ss", f"{segment.start:.3f}", "-t", f"{length:.3f}", "-i", str(sound)]
        elif not has_audio:
            command += ["-f", "lavfi", "-t", f"{length:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        command += [
            "-vf", f"scale={size}:force_original_aspect_ratio=decrease,pad={size}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p",
            "-map", "0:v:0", "-map", "0:a:0" if has_audio and not sound else "1:a:0",
            "-af", f"volume={gain}dB,aresample=async=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", str(piece),
        ]
        run_process(command, expected_seconds=length, message=f"Cutting {segment.shot}",
                    span=within(0.9 * index / total, 0.9 * (index + 1) / total))
        pieces.append(piece)
    listing = work / "pieces.txt"
    listing.write_text("".join(f"file '{piece.name}'\n" for piece in pieces), encoding="utf-8")
    run_process([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                 "-c", "copy", "-movflags", "+faststart", str(output)],
                message="Joining the shots", span=within(0.9, 1.0))
