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

Sound from the catalog (CT-0048) is laid under the joined cut: effects and
Foley a shot places, the scene's ambience beds and music cues, each at its
loudness, the music lowered under the speech. What was laid is recorded.

How shots are joined (SPEC-0007):

- a straight cut, unless the cut says otherwise;
- a **transition** from the catalog replaces the outgoing shot's last frames
  and the incoming one's first, as `toast build` does: its own GLSL shader
  when GL can run, else the FFmpeg stand-in its manifest declares; one that
  can do neither is a straight cut, and the version says so. The sound
  crossfades over it;
- a **J-cut** lets the incoming shot's sound lead the picture by `split`
  seconds, an **L-cut** lets the outgoing shot's sound run on: the sound
  comes from the take beyond its cut point (its handle), the other side
  fades under it. A take without enough sound there shortens the split, and
  the version says so.

Picture is normalised to the first take's size and frame rate, sound to
48 kHz stereo.

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
#: A J- or L-cut's sound across the picture cut when the cut does not say.
DEFAULT_SPLIT = 0.8
#: The leading (J) or trailing (L) sound's own edge, so it does not click in.
SPLIT_EDGE = 0.15


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
    #: Effects from the VFX catalog, applied before the title.
    effects: list[dict[str, Any]] = field(default_factory=list)
    #: The file actually cut, when it is not the take itself (a rendered card or titled piece).
    source: str = ""
    #: The join into this shot, resolved: a transition ({id, seconds, shader | mode}) and a J/L split.
    transition: dict[str, Any] | None = None
    split: float = 0.0

    @property
    def overlap(self) -> float:
        """Seconds the transition into this shot takes from the shots on both sides."""

        return float(self.transition["seconds"]) if self.transition else 0.0


@dataclass(slots=True)
class Plan:
    scene: str
    segments: list[Segment] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    gains: dict[str, float] = field(default_factory=dict)
    #: Sounds from the catalog placed on the cut's timeline, and, once rendered, what was laid.
    cues: list[dict[str, Any]] = field(default_factory=list)
    sound: list[dict[str, Any]] = field(default_factory=list)

    @property
    def takes(self) -> dict[str, str]:
        # A title card is drawn, not chosen: it has no take to remember.
        return {segment.shot: segment.take for segment in self.segments if segment.method != "title"}

    @property
    def duration(self) -> float:
        return round(sum(segment.end - segment.start - segment.overlap for segment in self.segments), 3)


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
    joins: dict[str, Any] = {}  # the transition catalog and the GL check, read once if a cut needs them
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
            segment = Segment(shot["id"], "TITLE", "", 0.0, length, cut.get("type") or "hard", "title",
                              None, shot.get("level_db"), title=title, effects=list(shot.get("effects") or []))
            if plan.segments:
                _resolve_join(root, plan, cut, segment, joins)
            plan.segments.append(segment)
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
        segment = Segment(
            shot["id"], chosen["id"], chosen["media"], start, end, join, method,
            (spoken[0][0], spoken[-1][1]) if spoken else None, shot.get("level_db"),
            revoice=bool(shot.get("voice_in_cut")), title=title, effects=list(shot.get("effects") or []),
        )
        if plan.segments:
            _resolve_join(root, plan, cut, segment, joins)
        plan.segments.append(segment)
    if not plan.segments:
        raise ValidationError(f"{scene['id']} has no shot with a take to assemble")
    if scene.get("ambience") or scene.get("music") or any(shot.get("sounds") for shot in scene["shots"]):
        from .sounds import place

        plan.cues, notes = place(scene, plan.segments)
        plan.notes.extend(notes)
    return plan


def _resolve_join(root: Path, plan: Plan, cut: dict[str, Any], segment: Segment, joins: dict[str, Any]) -> None:
    """The transition and split into `segment`, as this machine can render them; what it cannot, said."""

    previous = plan.segments[-1]
    reference = cut.get("transition") or {}
    if reference.get("id"):
        if "catalog" not in joins:
            from .shader_render import gl_unavailable_reason
            from .transitions import list_transitions

            joins["catalog"] = {item["id"]: item for item in list_transitions(root)}
            joins["gl"] = gl_unavailable_reason()
        item = joins["catalog"].get(reference["id"])
        seconds = float(reference.get("duration_ms") or (item or {}).get("duration_ms") or 1000) / 1000.0
        room = 0.5 * min(previous.end - previous.start, segment.end - segment.start)
        mode = ((item or {}).get("render") or {}).get("ffmpeg")
        if item is None:
            plan.notes.append(f"{segment.shot}: the transition {reference['id']!r} is in no catalog; a straight cut.")
        elif item["kind"] != "glsl" and not mode or item["kind"] == "glsl" and joins["gl"] and not mode:
            why = f"GL cannot run here ({joins['gl']})" if item["kind"] == "glsl" else "it is not a shader"
            plan.notes.append(f"{segment.shot}: the transition {item['id']!r} cannot be rendered: {why}, and it "
                              "declares no FFmpeg stand-in; a straight cut in this version.")
        else:
            if seconds > room:
                plan.notes.append(f"{segment.shot}: the transition {item['id']!r} is shortened to {room:.2f} s, half "
                                  "the shorter of the shots it joins.")
                seconds = room
            if item["kind"] == "glsl" and not joins["gl"]:
                segment.transition = {"id": item["id"], "seconds": round(seconds, 3),
                                      "shader": str(item["asset_path"]), "params": item.get("params") or []}
            else:
                segment.transition = {"id": item["id"], "seconds": round(seconds, 3), "mode": str(mode)}
    if segment.join in ("j", "l"):
        if segment.transition:
            plan.notes.append(f"{segment.shot}: a {segment.join.upper()}-cut with a transition: the sound "
                              "crossfades over the transition instead.")
        else:
            segment.split = float(cut.get("split") or DEFAULT_SPLIT)


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
    """Render a segment's effects and title: a card on its own, or over the cut piece of its take, sound kept.

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
    from .vfx import render as render_effects

    size = {"width": first["width"] // 2 * 2, "height": first["height"] // 2 * 2, "fps": round(fps) or FPS}

    def run(what: str):
        return lambda command: run_process(command, expected_seconds=length, message=f"{segment.shot}: {what}")

    start = segment.start
    if segment.effects and background is not None:  # a take: its effects, then the title over them
        treated = output.with_suffix(".fx.mp4")
        render_effects(segment.effects, length, treated, background=background, start=start,
                       run=run("effects " + ", ".join(e["id"] for e in segment.effects)), **size)
        background, start = treated, 0.0
    if segment.title:
        render_title(segment.title, length, output, background=background, start=start, root=root,
                     run=run(f"title {segment.title['id']}"), **size)
    else:
        shutil.copyfile(background, output)
    if segment.effects and not segment.media:  # a card: the effects over the drawn card, text included
        treated = output.with_suffix(".fx.mp4")
        render_effects(segment.effects, length, treated, background=output, run=run("effects"), **size)
        treated.replace(output)
    if segment.speech:
        segment.speech = (segment.speech[0] - segment.start, segment.speech[1] - segment.start)
    segment.source, segment.start, segment.end = str(output), 0.0, length


def render(root: Path, plan: Plan, output: Path, work: Path, run_process,
           span: tuple[float, float] = (0.0, 1.0)) -> None:
    """Cut each take, normalise it, join the pictures and lay the sound.

    Picture and sound are made apart: the picture as normalised pieces,
    joined by straight cuts and transitions; the sound as one levelled clip
    per shot, with the handles a J- or L-cut needs, placed on the timeline
    and faded where the joins say; then the catalog's sound over both.

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
    width, height = first["width"] // 2 * 2, first["height"] // 2 * 2
    size = f"{width}:{height}"
    fps = first["fps"] or FPS
    segment_gain: dict[str, float] = {}
    plan.gains = segment_gain
    total = len(plan.segments)
    count = [0] * total  # frames of each piece
    overlap = [0] * (total + 1)  # frames each transition takes, into segment i
    pictures, sounds = [], []
    for index, segment in enumerate(plan.segments):
        if (segment.title or segment.effects) and not segment.source:
            _draw_title(root, segment, work / f"title-{index:03d}.mp4", first, fps, run_process)
        source = Path(segment.source) if segment.source else root / segment.media
        length = segment.end - segment.start
        picture = work / f"picture-{index:03d}.mp4"
        run_process([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{segment.start:.3f}", "-t", f"{length:.3f}",
                     "-i", str(source), "-map", "0:v:0",
                     "-vf", f"scale={size}:force_original_aspect_ratio=decrease,pad={size}:(ow-iw)/2:(oh-ih)/2,"
                            f"setsar=1,fps={fps},format=yuv420p",
                     "-frames:v", str(max(1, round(length * fps))), "-an", "-c:v", "libx264", "-preset", "veryfast",
                     "-crf", "18", str(picture)],
                    expected_seconds=length, message=f"Cutting {segment.shot}",
                    span=within(0.6 * index / total, 0.6 * (index + 1) / total))
        pictures.append(picture)
        # What the take really gave: a take that ends mid-frame gives one frame less than its length says.
        count[index] = _frames_in(picture) or max(1, round(length * fps))
    for index, segment in enumerate(plan.segments[1:], 1):
        wanted = round(segment.overlap * fps)
        overlap[index] = min(wanted, count[index - 1] // 2, count[index] // 2)
    # The splits each take can give: sound from beyond its cut point.
    lead = [0.0] * total  # sound before the picture, for a J-cut into the shot
    trail = [0.0] * total  # sound after the picture, for an L-cut out of the shot
    for index, segment in enumerate(plan.segments[1:], 1):
        if not segment.split:
            continue
        previous = plan.segments[index - 1]
        if segment.join == "j":
            room = segment.start if not segment.source else 0.0
        else:
            sound = Path(previous.sound) if previous.sound and not previous.source else (
                Path(previous.source) if previous.source else root / previous.media)
            room = max(0.0, probe(sound)["duration"] - previous.end) if previous.media else 0.0
        room = min(room, 0.9 * (previous.end - previous.start), 0.9 * (segment.end - segment.start))
        split = round(min(segment.split, room), 3)
        if split < segment.split:
            whose = "its take" if segment.join == "j" else f"{previous.shot}'s take"
            plan.notes.append(f"{segment.shot}: the {segment.join.upper()}-cut's sound runs {split:.2f} s across the "
                              f"cut, not {segment.split:.2f}: {whose} has no more sound beyond its cut point."
                              if split > 0 else
                              f"{segment.shot}: the {segment.join.upper()}-cut is a straight cut: {whose} has no "
                              "sound beyond its cut point.")
        segment.split = split
        if segment.join == "j":
            lead[index] = split
        else:
            trail[index - 1] = split
    starts, clock = [], 0.0
    for index in range(total):
        clock -= overlap[index] / fps
        starts.append(clock)
        clock += count[index] / fps
    duration = clock
    plan_duration_frames = round(duration * fps)
    for index, segment in enumerate(plan.segments):
        source = Path(segment.source) if segment.source else root / segment.media
        sound = Path(segment.sound) if segment.sound and not segment.source else None
        has_audio = bool(sound) or probe(source)["audio"]
        length = count[index] / fps
        gain = loudness_gain(sound or source, segment) if has_audio and segment.normalize else 0.0
        segment_gain[segment.shot] = gain
        # The sound: the shot's span, plus what a J/L-cut takes from beyond it, faded as the joins say.
        before, after = lead[index], trail[index]
        span_seconds = before + length + after
        fade_in = (overlap[index] / fps if overlap[index] else
                   segment.split if segment.join == "l" and segment.split else
                   min(SPLIT_EDGE, before) if before else 0.0)
        following = plan.segments[index + 1] if index + 1 < total else None
        fade_out = (overlap[index + 1] / fps if overlap[index + 1] else
                    following.split if following and following.join == "j" and following.split else
                    min(SPLIT_EDGE, after) if after else 0.0)
        # A trailing L sound fades at its own end; otherwise the fade ends with the picture.
        fade_end = span_seconds if after else before + length
        fades = ([f"afade=t=in:d={fade_in:.3f}"] if fade_in else []) + (
            [f"afade=t=out:st={fade_end - fade_out:.3f}:d={fade_out:.3f}"] if fade_out else [])
        clip = work / f"sound-{index:03d}.wav"
        if has_audio:
            command = [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{segment.start - before:.3f}",
                       "-t", f"{span_seconds:.3f}", "-i", str(sound or source), "-map", "0:a:0"]
        else:
            command = [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-t", f"{span_seconds:.3f}",
                       "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        run_process(command + ["-af", ",".join([f"volume={gain}dB", "aresample=48000",
                                                 "aformat=sample_fmts=fltp:channel_layouts=stereo",
                                                 f"apad=whole_dur={span_seconds:.3f}", f"atrim=0:{span_seconds:.3f}",
                                                 *fades]),
                               "-ar", "48000", "-ac", "2", str(clip)],
                    expected_seconds=span_seconds, message=f"{segment.shot}: its sound",
                    span=within(0.6 + 0.25 * index / total, 0.6 + 0.25 * (index + 1) / total))
        sounds.append((clip, max(0.0, starts[index] - before)))
    picture = _join_pictures(ffmpeg, plan, pictures, count, overlap, work, fps, width, height, run_process,
                             within(0.85, 0.9))
    mixed = work / "sound.wav"
    inputs = [part for clip, _ in sounds for part in ("-i", str(clip))]
    delays = ";".join(f"[{index}:a]adelay={int(round(at * 1000))}:all=1[s{index}]"
                      for index, (_, at) in enumerate(sounds))
    labels = "".join(f"[s{index}]" for index in range(len(sounds)))
    run_process([ffmpeg, "-y", "-loglevel", "error", *inputs, "-filter_complex",
                 f"{delays};{labels}amix=inputs={len(sounds)}:normalize=0:duration=longest,"
                 f"apad=whole_dur={duration:.3f},atrim=0:{duration:.3f}[a]",
                 "-map", "[a]", "-ar", "48000", "-ac", "2", str(mixed)],
                message="Laying the takes' sound", span=within(0.9, 0.92))
    joined = work / "joined.mp4" if plan.cues else output
    run_process([ffmpeg, "-y", "-loglevel", "error", "-i", str(picture), "-i", str(mixed), "-map", "0:v:0",
                 "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                 "-frames:v", str(plan_duration_frames), "-shortest", "-movflags", "+faststart", str(joined)],
                message="Joining the shots", span=within(0.92, 0.93 if plan.cues else 1.0))
    if plan.cues:
        from .sounds import list_sounds, mix

        speech = [(starts[index] + max(0.0, segment.speech[0] - segment.start),
                   starts[index] + min(segment.end, segment.speech[1]) - segment.start)
                  for index, segment in enumerate(plan.segments) if segment.speech]
        catalog = {item["id"]: item for item in list_sounds(root)}

        def run_sound(command, expected_seconds=None, message=""):
            run_process(command, expected_seconds=expected_seconds, message=message, span=within(0.93, 1.0))

        plan.sound = mix(joined, plan.cues, catalog, speech, output, work / "sound", run_sound)


def _frames_in(path: Path) -> int:
    """The frames a video file holds, counted from its packets."""

    ffprobe = shutil.which("ffprobe")
    completed = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                                "stream=nb_read_packets", "-of", "csv=p=0", str(path)],
                               capture_output=True, text=True, timeout=120)
    try:
        return int(completed.stdout.strip().split(",")[0])
    except ValueError:
        return 0


def _join_pictures(ffmpeg: str, plan: Plan, pictures: list[Path], count: list[int], overlap: list[int], work: Path,
                   fps: float, width: int, height: int, run_process, span: tuple[float, float]) -> Path:
    """The pieces joined: straight cuts, and each transition as its own clip between the bodies (as `toast build`)."""

    destination = work / "picture.mp4"
    encode = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", f"{fps:g}"]
    pieces: list[Path] = []
    total = len(pictures)
    for index, picture in enumerate(pictures):
        start, end = overlap[index], count[index] - overlap[index + 1]
        if start == 0 and end == count[index]:
            pieces.append(picture)
        elif end > start:
            body = work / f"body-{index:03d}.mp4"
            run_process([ffmpeg, "-y", "-loglevel", "error", "-i", str(picture), "-vf",
                         f"trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS", *encode, str(body)],
                        message=f"Trimming {plan.segments[index].shot}", span=span)
            pieces.append(body)
        if index + 1 < total and overlap[index + 1]:
            following = plan.segments[index + 1]
            transition, frames = following.transition, overlap[index + 1]
            clip = work / f"join-{index + 1:03d}.mp4"
            if transition.get("shader"):
                from .build import Join, _shader_join

                join = Join(transition["id"], frames / fps, shader=Path(transition["shader"]),
                            params=transition.get("params") or [])
                _shader_join(ffmpeg, picture, pictures[index + 1], count[index], frames, join, clip, width, height, fps)
            else:
                tail = count[index] - frames
                run_process([ffmpeg, "-y", "-loglevel", "error", "-i", str(picture), "-i", str(pictures[index + 1]),
                             "-filter_complex",
                             f"[0:v]trim=start_frame={tail}:end_frame={count[index]},setpts=PTS-STARTPTS[a];"
                             f"[1:v]trim=end_frame={frames},setpts=PTS-STARTPTS[b];"
                             f"[a][b]xfade=transition={transition['mode']}:duration={frames / fps:.3f}:offset=0[v]",
                             "-map", "[v]", "-frames:v", str(frames), *encode, str(clip)],
                            message=f"{following.shot}: {transition['id']}", span=span)
            pieces.append(clip)
    listing = work / "pictures.txt"
    listing.write_text("".join(f"file '{piece.name}'\n" for piece in pieces), encoding="utf-8")
    # Pieces straight from the takes join as they are; with transition clips among them, encoded once more.
    codec = ["-c", "copy"] if not any(overlap) else encode
    run_process([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                 *codec, str(destination)], message="Joining the pictures", span=span)
    return destination
