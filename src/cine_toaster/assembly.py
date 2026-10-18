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
  and the incoming one's first, drawn as a graph: its own GLSL shader
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

from . import timebase
from .cards import is_card, recipe as card_recipe
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


#: Takes that are one picture, not a clip; and how long one is held when the shot does not say.
STILL_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
STILL_SECONDS = 3.0


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
    #: The shot drawn by its graph, already a piece of the cut (its frame, rate and format): joined as it is,
    #: not encoded again.
    piece: str = ""
    #: The media instants its graph shows of its take, frame by frame (C7, CT-0080): what its sound follows when
    #: the picture is retimed; None when the take is not shown, "ambiguous" when it is shown at several times.
    timemap: Any = None
    #: What its take's sound does under a retime (`mute` by default, `preserve`, `stretch`), and with what.
    retime_sound: str = ""
    stretch_with: str = ""
    #: Its picture retimed as the shot says (speed, reverse, freeze; keys on beats), compiled when drawn.
    retime: dict[str, Any] | None = None
    #: Speech heard within a scene version, in its own seconds (a sequence's segments): music ducks under it.
    speech_spans: list[tuple[float, float]] = field(default_factory=list)
    #: A format's frame in the take ({x, y}, CT-0049), and the captions spoken in it, in the take's seconds.
    reframe: dict[str, Any] | None = None
    captions: list[tuple[float, float, str]] = field(default_factory=list)
    #: The take's sound silenced in stretches (take seconds), and faded out from a point of the shot as cut.
    mute: list[list[float]] = field(default_factory=list)
    sound_fades_at: float | None = None
    #: Subtitles of the lines said in the take, in the take's seconds (CT-0054).
    subtitles: list[tuple[float, float, str]] = field(default_factory=list)
    #: Voices laid in the montage from their own files (a narration): (seconds into the shot's take, file).
    voice_over: list[tuple[float, str]] = field(default_factory=list)
    #: A scene version's renditions, by format (a sequence's segments): the sequence's renditions use them.
    renditions: dict[str, str] = field(default_factory=dict)
    #: The take is a still picture (a grabbed frame, a photograph): held for as long as the shot plays (CT-0065).
    still: bool = False
    #: The shot's picture is a composite (SPEC-0012): its graph, and the media of each take it may name.
    composite: dict[str, Any] | None = None
    composite_takes: dict[str, str] = field(default_factory=dict)
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
    #: Once rendered, where speech is heard on the cut's timeline: kept beside the version for the sequence.
    speech: list[tuple[float, float]] = field(default_factory=list)
    #: The format's rules the render applies (CT-0049): {aspect, captions}.
    format: dict[str, Any] = field(default_factory=dict)
    #: The production's frame (CT-0068): {width, height, fps}; empty, the first moving take's.
    frame: dict[str, Any] = field(default_factory=dict)
    #: The scene music's beats in seconds of the cut (CT-0067), for composites that move with them.
    beats: list[float] = field(default_factory=list)
    #: Another layout mixed beside the stereo, as a second track ("5.1", CT-0052); and, once rendered,
    #: the loudness of each track.
    surround: str = ""
    loudness: dict[str, float] = field(default_factory=dict)
    #: Write the sound's parts beside the version, for a final mix in a DAW (CT-0063); once rendered, where.
    stems: bool = False
    stems_folder: str = ""
    #: The cut as OpenTimelineIO beside the version (CT-0096): asked for, then the cut as it was made -- each
    #: shot's picture, where it starts in it, its frames on the timeline, the transition into it.
    otio: bool = False
    timeline: list[dict[str, Any]] = field(default_factory=list)
    rate: Any = None
    size: tuple[int, int] = (0, 0)
    #: Subtitles in the film's language (CT-0054): {burn: bool}; once rendered, the .srt written beside.
    subtitles: dict[str, Any] = field(default_factory=dict)
    subtitle_file: str = ""
    #: Once rendered, a still of each shot drawn by a graph (a card, a composite), by shot: what the frame at
    #: its middle is in the cut (CT-0072). Written in the render's work folder; the job adopts them.
    stills: dict[str, str] = field(default_factory=dict)
    #: A reveal over the whole scene (Demo 01): {kind: iris, from, to, until} -- a circle growing without a stop
    #: from `from` to `to` (fractions of the half-diagonal) by `until` (a fraction of the scene's length).
    reveal: dict[str, Any] = field(default_factory=dict)

    @property
    def takes(self) -> dict[str, str]:
        # A title card is drawn, not chosen: it has no take to remember.
        return {segment.shot: segment.take for segment in self.segments
                if segment.method not in ("title", "composite") and not segment.method.startswith("solid:")}

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
    return {
        "duration": float((data.get("format") or {}).get("duration") or 0.0),
        "audio": any(s.get("codec_type") == "audio" for s in streams),
        "width": int(video.get("width") or 1280),
        "height": int(video.get("height") or 720),
        # The rate as the file says it, a fraction: 30000/1001 stays NTSC (CT-0079), never 29.97 rounded.
        "fps": float(timebase.rate(rate)) if not rate.startswith("0") else FPS,
    }


def sidecar_for(media: Path, pattern: str) -> Path | None:
    """A take's word timings: its own, else -- for a take made from another, `c02-pov` from `c02` -- the
    original's, whose timeline it keeps (SINGULAR's POV montage, CT-0054)."""

    sidecar = media.parent / pattern.format(stem=media.stem, name=media.name)
    if sidecar.is_file():
        return sidecar
    stem = media.stem
    while "-" in stem:
        stem = stem.rsplit("-", 1)[0]
        original = media.parent / pattern.format(stem=stem, name=f"{stem}{media.suffix}")
        if original.is_file():
            return original
    return None


def words_for(media: Path, pattern: str) -> list[tuple[float, float]]:
    """Word timings beside a take, as (start, end) seconds; empty when there are none."""

    sidecar = sidecar_for(media, pattern)
    if sidecar is None:
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

    plan = Plan(scene=scene["id"], reveal=dict(scene.get("reveal") or {}))
    cuts = {cut["to"]: cut for cut in scene.get("cuts") or []}
    joins: dict[str, Any] = {}  # the transition catalog and the GL check, read once if a cut needs them
    framed: list[str] = []  # reframed on whom, from the plan: one note for the scene
    for shot in scene["shots"]:
        if shot.get("out_of_cut"):
            continue
        takes = [take for take in shot.get("takes") or [] if take.get("media")]
        chosen = next((take for take in takes if take.get("selected")), None)
        if chosen is None:
            chosen = next((take for take in takes if take["id"] == "CUT"), None)
        if chosen is None:
            chosen = _reused(root, scene, shot, plan)
        title = shot.get("title") if isinstance(shot.get("title"), dict) and not shot["title"].get("unknown") else None
        if chosen is None and title and not shot.get("composite"):
            # A card: the title drawn over its background, as long as the shot plays (a composite with a title is
            # drawn below, the title over it).
            length = float(shot.get("duration_seconds") or 0) or 3.0
            cut = cuts.get(shot["id"]) or {}
            segment = Segment(shot["id"], "TITLE", "", 0.0, length, cut.get("type") or "hard", "title",
                              None, shot.get("level_db"), title=title, effects=list(shot.get("effects") or []))
            segment.voice_over = _voices_of(root, scene, shot)
            segment.subtitles = _card_subtitles(root, scene, shot, length)
            if plan.segments:
                _resolve_join(root, plan, cut, segment, joins)
            plan.segments.append(segment)
            continue
        if chosen is None and shot.get("source") == "composed" and shot.get("engine") == "solid":
            # A plain black (or white) shot: the screen held for its duration, its sounds laid over it (CT-0054).
            length = float(shot.get("duration_seconds") or 0) or 2.0
            cut = cuts.get(shot["id"]) or {}
            colour = "white" if str(shot.get("kind") or "").lower() in ("white", "branco") else "black"
            segment = Segment(shot["id"], "SOLID", "", 0.0, length, cut.get("type") or "hard", f"solid:{colour}",
                              None, shot.get("level_db"))
            segment.voice_over = _voices_of(root, scene, shot)
            segment.subtitles = _card_subtitles(root, scene, shot, length)
            if plan.segments:
                _resolve_join(root, plan, cut, segment, joins)
            plan.segments.append(segment)
            continue
        if chosen is None and is_card(shot):
            # A card: its words on the look's background, drawn as a graph like every composite (CT-0072).
            length = float(shot.get("duration_seconds") or 0) or 3.0
            cut = cuts.get(shot["id"]) or {}
            if "looks" not in joins:
                from .looks import load_looks

                joins["looks"] = {name: look.public_dict() for name, look in load_looks(root).items()}
            segment = Segment(shot["id"], "CARD", "", 0.0, length, cut.get("type") or "hard", "composite",
                              None, shot.get("level_db"), effects=list(shot.get("effects") or []))
            segment.composite = card_recipe(shot, joins["looks"].get(shot.get("look") or ""))
            segment.composite_takes = {}
            segment.voice_over = _voices_of(root, scene, shot)
            segment.subtitles = _card_subtitles(root, scene, shot, length)
            if plan.segments:
                _resolve_join(root, plan, cut, segment, joins)
            plan.segments.append(segment)
            continue
        if chosen is None and shot.get("composite"):
            # A picture made only by its composite (files, generators): no take to cut from (SPEC-0012 §4).
            length = float(shot.get("duration_seconds") or 0) or 3.0
            cut = cuts.get(shot["id"]) or {}
            segment = Segment(shot["id"], "COMPOSITE", "", 0.0, length, cut.get("type") or "hard", "composite",
                              None, shot.get("level_db"), title=title, effects=list(shot.get("effects") or []))
            segment.composite = shot["composite"]
            segment.composite_takes = {take["id"]: take["media"] for take in shot.get("takes") or []}
            segment.voice_over = _voices_of(root, scene, shot)
            # Its picture retimed too (C7, CT-0080): a composite of files is retimed as a take is.
            segment.retime = shot.get("retime") if isinstance(shot.get("retime"), dict) else None
            if plan.segments:
                _resolve_join(root, plan, cut, segment, joins)
            plan.segments.append(segment)
            continue
        if chosen is None:
            plan.notes.append(f"{shot['id']} has no take to use; it is left out of this version.")
            continue
        path = root / chosen["media"]
        still = path.suffix.lower() in STILL_SUFFIXES
        if still:
            # A picture has no length of its own: the shot says how long it is held.
            held = float(shot.get("duration_seconds") or 0)
            if not held:
                held = STILL_SECONDS
                plan.notes.append(f"{shot['id']} is a still with no duration; held {STILL_SECONDS:g} s.")
            info = {**probe(path), "duration": held}
        else:
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
            still=still,
        )
        if plan.segments:
            _resolve_join(root, plan, cut, segment, joins)
        segment.reframe = shot.get("reframe")
        if shot.get("composite"):
            segment.composite = shot["composite"]
            segment.composite_takes = {take["id"]: take["media"] for take in shot.get("takes") or []}
            segment.composite_takes.setdefault("CUT", chosen["media"])
            segment.composite_takes[chosen["id"]] = chosen["media"]
        segment.mute = list(shot.get("mute") or [])
        scene_dir = root / Path(scene["file"]).parent
        segment.voice_over = [(float(line["mix"].get("at", line["mix"].get("em")) or 0.0),
                               str(scene_dir / (line["mix"].get("file") or line["mix"].get("arquivo"))))
                              for line in shot.get("lines") or []
                              if isinstance(line.get("mix"), dict) and (line["mix"].get("file") or line["mix"].get("arquivo"))]
        if scene.get("subtitles"):
            from .formats import spoken_words, subtitle_blocks

            # Every line has its subtitle: those said in the take by their words, a narration at its time.
            said = [line for line in shot.get("lines") or [] if line.get("in_take", True) or line.get("mix")]
            segment.subtitles = subtitle_blocks(said, spoken_words(path, words_sidecar), start, end,
                                                lambda name: probe(root / Path(scene["file"]).parent / name)["duration"]
                                                if name and (root / Path(scene["file"]).parent / name).is_file() else 1.4)
        segment.sound_fades_at = shot.get("sound_fades_at")
        segment.retime_sound = str(shot.get("retime_sound") or "")
        segment.retime = shot.get("retime") if isinstance(shot.get("retime"), dict) else None
        segment.stretch_with = str(shot.get("stretch_with") or "")
        wants_frame = ((scene.get("style") or {}).get("format") or {}).get("aspect") or scene.get("deliver")
        if not segment.reframe and wants_frame:
            from .formats import subject_window

            segment.reframe, note = subject_window(scene, shot)
            if note:
                framed.append(note)
        # Timed whenever a version wants them: the scene's format, or a format it is delivered in.
        if (((scene.get("style") or {}).get("format") or {}).get("captions")
                or any(item.get("captions") for item in scene.get("deliver") or [])):
            from .formats import groups, spoken_words, spread

            words = [word for word in spoken_words(path, words_sidecar) if start - 0.05 <= word[0] and word[1] <= end + 0.05]
            if words:
                segment.captions = groups(words)
            else:
                text = " ".join(str(line.get("en") or line.get("text") or "") for line in shot.get("lines") or []
                                if line.get("in_take", True)).strip()
                begin, finish = segment.speech or (start, end)
                segment.captions = spread(text, begin, finish)
        plan.segments.append(segment)
    if not plan.segments:
        raise ValidationError(f"{scene['id']} has no shot with a take to assemble")
    for segment in plan.segments:
        if segment.media and not segment.still:
            # A cut point is a frame boundary of the take (CT-0079): the picture starts on a whole frame, so the
            # sound must start at that frame too, not at the second the shot names.
            grid = probe(root / segment.media)["fps"]
            start, end = timebase.snap(segment.start, grid), timebase.snap(segment.end, grid)
            if end > start:
                segment.start, segment.end = start, end
    if framed:
        plain = [note.replace(" is reframed on ", ": ").replace(", from the plan", "") for note in framed if ";" not in note]
        plan.notes.append("Reframed on each shot's subject, from the plan -- " + ", ".join(plain) + ".")
        plan.notes += [note + "." for note in framed if ";" in note]
    form = (scene.get("style") or {}).get("format") or {}
    plan.format = {key: form[key] for key in ("aspect", "captions") if form.get(key)}
    plan.frame = dict(scene.get("frame") or {})
    plan.beats = _scene_beats(root, scene)
    plan.surround = str(scene.get("surround") or "")
    plan.subtitles = dict(scene.get("subtitles") or {})
    if scene.get("ambience") or scene.get("music") or any(shot.get("sounds") for shot in scene["shots"]):
        from .sounds import place

        plan.cues, notes = place(scene, plan.segments)
        plan.notes.extend(notes)
    return plan


def _card_subtitles(root: Path, scene: dict[str, Any], shot: dict[str, Any], length: float) -> list[tuple[float, float, str]]:
    """A card or a black shot has no take: only a narration laid over it is subtitled, at its time."""

    if not scene.get("subtitles"):
        return []
    from .formats import subtitle_blocks

    folder = root / Path(scene["file"]).parent
    narration = [line for line in shot.get("lines") or [] if isinstance(line.get("mix"), dict)]
    return subtitle_blocks(narration, [], 0.0, length,
                           lambda name: probe(folder / name)["duration"] if name and (folder / name).is_file() else 1.4)


def _voices_of(root: Path, scene: dict[str, Any], shot: dict[str, Any]) -> list[tuple[float, str]]:
    scene_dir = root / Path(scene["file"]).parent
    return [(float(line["mix"].get("at", line["mix"].get("em")) or 0.0),
             str(scene_dir / (line["mix"].get("file") or line["mix"].get("arquivo"))))
            for line in shot.get("lines") or []
            if isinstance(line.get("mix"), dict) and (line["mix"].get("file") or line["mix"].get("arquivo"))]


def _reused(root: Path, scene: dict[str, Any], shot: dict[str, Any], plan: Plan) -> dict[str, Any] | None:
    """A shot that reuses another scene's clip (`from: {ref: "1-02 c03", relation: reuses}`) takes that clip."""

    for item in shot.get("from") or []:
        if str(item.get("relation") or "") not in ("reuses", "reusa"):
            continue
        parts = str(item.get("ref") or "").split()
        if len(parts) != 2:
            continue
        other_id, clip = parts[0].split("/")[0], parts[1]
        from .project import load_production, scene_files
        from .takes import work_directory_for

        for path in scene_files(root):
            text = path.read_text(encoding="utf-8")
            if re.search(rf"^(scene|cena):\s*['\"]?{re.escape(other_id)}['\"]?\s*$", text, re.M):
                media = work_directory_for(path) / f"{clip}.mp4"
                if media.is_file():
                    plan.notes.append(f"{shot['id']} reuses {other_id}'s clip {clip}.")
                    return {"id": f"REUSE-{other_id}-{clip}".upper(), "media": media.relative_to(root).as_posix()}
        plan.notes.append(f"{shot['id']} reuses {item.get('ref')}, which is not there.")
    return None


def _resolve_join(root: Path, plan: Plan, cut: dict[str, Any], segment: Segment, joins: dict[str, Any]) -> None:
    """The transition and split into `segment`, as this machine can render them; what it cannot, said."""

    previous = plan.segments[-1]
    reference = cut.get("transition") or {}
    if reference.get("id"):
        if "catalog" not in joins:
            from .compositing.gl import gl_unavailable_reason
            from .transitions import list_transitions

            joins["catalog"] = {item["id"]: item for item in list_transitions(root)}
            joins["gl"] = gl_unavailable_reason()
        item = joins["catalog"].get(reference["id"])
        seconds = float(reference.get("duration_ms") or (item or {}).get("duration_ms") or 1000) / 1000.0
        room = 0.5 * min(previous.end - previous.start, segment.end - segment.start)
        mode = ((item or {}).get("render") or {}).get("ffmpeg")
        # Pictures the join gives the transition, over the item's own (SPEC-0011).
        inputs = dict((item or {}).get("inputs") or {})
        generated = reference.get("matte") if isinstance(reference.get("matte"), dict) else None
        for key in ("matte", "overlay"):
            if reference.get(key) and not (key == "matte" and generated):
                inputs[key] = (root / reference[key]).resolve()
        missing = [key for key, path in inputs.items() if not Path(path).is_file()]
        # A matte item, or a shader whose FFmpeg stand-in is the matte renderer when GL cannot run it.
        by_matte = bool(item) and (item["kind"] == "matte" or (mode == "matte" and joins["gl"]))
        matte = (generated or inputs.get("matte") or inputs.get("luma")) if by_matte else None
        if item is None:
            plan.notes.append(f"{segment.shot}: the transition {reference['id']!r} is in no catalog; a straight cut.")
        elif missing:
            plan.notes.append(f"{segment.shot}: the transition {item['id']!r} has no {', '.join(missing)} to read; "
                              "a straight cut in this version.")
        elif by_matte and matte is None:
            plan.notes.append(f"{segment.shot}: the transition {item['id']!r} is shaped by a matte and the join gives "
                              "none (matte: on the join); a straight cut in this version.")
        elif item["kind"] == "graph":
            # A recipe of SPEC-0012 primitives, drawn by the compositing reference (ADR 0022).
            if seconds > room:
                plan.notes.append(f"{segment.shot}: the transition {item['id']!r} is shortened to {room:.2f} s, half "
                                  "the shorter of the shots it joins.")
                seconds = room
            segment.transition = {"id": item["id"], "seconds": round(seconds, 3), "graph": item["graph"],
                                  "inputs": {name: str(path) for name, path in inputs.items()
                                             if name not in ("matte", "overlay")}}
        elif by_matte:
            if seconds > room:
                plan.notes.append(f"{segment.shot}: the transition {item['id']!r} is shortened to {room:.2f} s, half "
                                  "the shorter of the shots it joins.")
                seconds = room
            segment.transition = {"id": item["id"], "seconds": round(seconds, 3),
                                  "matte": matte if isinstance(matte, dict) else str(matte),
                                  "softness": float(reference.get("softness", item.get("softness") or 0.0) or 0.0)}
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
                                      "shader": str(item["asset_path"]), "params": item.get("params") or [],
                                      "textures": {name: str(path) for name, path in inputs.items()
                                                   if name not in ("matte", "overlay")}}
            else:
                segment.transition = {"id": item["id"], "seconds": round(seconds, 3), "mode": str(mode)}
        if segment.transition and inputs.get("overlay"):
            segment.transition["overlay"] = str(inputs["overlay"])
            segment.transition["blend"] = str(reference.get("blend") or "normal")
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


def _scene_beats(root: Path, scene: dict[str, Any]) -> list[float]:
    """The beats of the scene's music, in seconds of the cut, when the music starts with the scene."""

    music = scene.get("music") or []
    if not music or music[0].get("from") or float(music[0].get("at") or 0):
        return []
    from .beats import read
    from .sounds import list_sounds

    item = next((sound for sound in list_sounds(root) if sound["id"] == music[0]["id"]), None)
    heard, _ = read(item) if item else (None, "")
    return list((heard or {}).get("beats") or [])


def _drawn(segment: Segment) -> bool:
    """Whether the shot is drawn by its graph: a composite, a still picture, or a take with effects or a title
    (OpenFX plugins included: Natron runs as a node of it). A take with nothing over it is cut as it is."""

    return bool(segment.composite or segment.title or segment.effects or segment.still or segment.retime)


def _shot_drawing(root: Path, segment: Segment, size: tuple[int, int], fps: float, beats: list[float] | None = None,
                  at: float = 0.0, run_process=None) -> tuple[Any, Any, bool]:
    """The shot as one graph, drawn (CT-0078): its picture -- a composite, a take, a still, or a title's card
    -- then its effects and its title chained after it, so nothing is written between them. A take is
    treated by its effects, then titled; a card is titled, then treated, text included.
    (pictures, the GL renderer or None, cached)."""

    from .compositing import reference
    from .compositing.gl import renderer_for
    from .compositing.shot import shot_graph
    from .titles import card_picture, title_graph
    from .vfx import effects_graph

    length = segment.end - segment.start
    frames = max(1, round(length * fps))
    width, height = size
    run = (lambda command: run_process(command, expected_seconds=length, message=f"{segment.shot}: its elements")) \
        if run_process else None
    whole = dict(width=width, height=height, fps=fps, run=run)
    effects = [("fx-", effects_graph(segment.effects, length, **whole))] if segment.effects else []
    title = [("title-", title_graph(segment.title, length, root=root, **whole))] if segment.title else []
    fragments = title + effects if not (segment.media or segment.composite) else effects + title
    # The music's beats in the shot's own seconds: a shot pulses with the cut, not with its take.
    local = [beat - at for beat in beats or [] if -1.0 <= beat - at <= length + 1.0]
    if segment.retime and (segment.media or segment.composite):
        # The shot's picture retimed first, so its effects and title run at the cut's speed (C7, CT-0080).
        from .compositing.retime import compile_retime

        retimed, problems = compile_retime(segment.retime, length=length,
                                           beats=[beat for beat in local if 0 <= beat < length],
                                           where=f"{segment.shot}'s retime")
        if problems:
            raise ValidationError("; ".join(problems))
        fragments = [("retime-", retimed)] + fragments
    base = segment.composite or None
    graph = shot_graph(base, fragments) if base is not None or fragments else None
    # The takes read as far as the graph reaches: past the shot's end when it is retimed faster, and before its
    # cut point (a pre-roll) when a remap runs back past it, as far as the take has frames (CT-0080).
    extent = reference.reach(graph, frames, fps, local) if graph is not None else frames
    early = reference.preroll(graph, frames, fps, local) if graph is not None else 0
    inputs: dict[str, Any] = {}
    origins: dict[str, Any] = {}

    def take(media: str, start: float, name: str, **more: Any) -> Any:
        grid = probe(root / media)["fps"]
        # The take's media instant at the shot's local zero, exactly: its cut point on the take's grid.
        origins[name] = timebase.seconds_of(timebase.frame_at(start, grid), grid)
        back = min(early, int(round(start * fps)))
        clip = reference.read(root / media, extent + back, size, fps, start=start - back / fps, **more)
        return reference.Shifted(clip, back) if back else clip

    if segment.composite:
        for name, node in base["nodes"].items():
            if node.get("op") != "generate.source" or not node.get("take"):
                continue
            media = segment.composite_takes.get(str(node["take"]))
            if media is None:
                raise ValidationError(f"{segment.shot}: its composite names the take {node['take']!r}, which the "
                                      f"shot does not have ({', '.join(segment.composite_takes) or 'none'})")
            # The cut's stretch of the take, unless the node asks for another start.
            start = float(node["start"]) if node.get("start") is not None else segment.start
            inputs[name] = take(media, start, name, colorspace=node.get("colorspace"), alpha=node.get("alpha"))
    elif segment.media:
        inputs["picture"] = take(segment.media, segment.start, "picture")
    else:
        inputs["picture"] = card_picture(segment.title or {"params": {}}, width, height)
    if graph is None:  # a take as it is: its own frames
        clip = inputs["picture"]
        return (clip[index] for index in range(frames)), None, False
    # What its take's sound follows: the instants the picture shows of the take (CT-0080).
    segment.timemap = _sound_map(graph, segment, frames, fps, local, origins) if segment.media else None
    fast = renderer_for(graph)
    pictures, _identity, cached = reference.render(graph, inputs, frames=frames, size=size, fps=fps, root=root,
                                                   beats=local, renderer=fast, origins=origins)
    return pictures, fast, cached


def _sound_map(graph: dict[str, Any], segment: Segment, frames: int, fps: float, beats: list[float],
               origins: dict[str, Any]) -> Any:
    """The shot's sound map: the take's media instant at each output frame, from the source that is the take."""

    from .compositing import reference
    from .retime_sound import TimeMap

    names = [name for name in origins
             if name == "picture" or (graph["nodes"].get(name, {}).get("take")
                                      and segment.composite_takes.get(str(graph["nodes"][name]["take"])) == segment.media)]
    if not names:
        return None
    source = names[0]
    per_frame, at = reference.shown_instants(graph, frames, fps, source, origins[source], beats)
    if any(len(found) > 1 for found in per_frame):
        return "ambiguous"
    if any(not found for found in per_frame):
        return None
    return TimeMap(timebase.rate(fps), origins[source], tuple(found[0] for found in per_frame), at=at)


def _draw_shot(root: Path, segment: Segment, destination: Path, first: dict[str, Any], fps: float, run_process,
               notes: list[str], beats: list[float] | None = None, at: float = 0.0,
               still: Path | None = None) -> None:
    """The shot drawn once by its graph and written once, as a piece of the cut; its take's sound laid under
    it by copy, not by encoding the picture again. With ``still``, the middle frame the cut shows."""

    from .compositing import reference

    length = segment.end - segment.start
    size = (first["width"] // 2 * 2, first["height"] // 2 * 2)
    pictures, fast, cached = _shot_drawing(root, segment, size, fps, beats, at, run_process)
    notes.append(f"{segment.shot}: drawn in one graph by "
                 + (f"GL ({fast.name.split(' (')[0]})." if fast else "the NumPy reference (exact, slow)."))
    if cached:
        notes.append(f"{segment.shot}: its drawing was found in the cache.")
    kept: list[Any] = []
    piece = destination.with_suffix(".piece.mp4")
    reference.write(_frames_keeping(pictures, max(1, round(length * fps)) // 2, kept), piece, fps,
                    quality=reference.PIECE)
    if still is not None and kept:
        reference.write_still(kept[0], still)
    # A take whose voice was converted is heard converted.
    heard = Path(segment.sound) if segment.sound else (root / segment.media if segment.media else None)
    timemap = segment.timemap
    retimed = timemap == "ambiguous" or (timemap is not None and timemap.kind != "unchanged")
    silence = ["-f", "lavfi", "-t", f"{length:.6f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    if heard is None or not probe(heard).get("audio"):
        sound = silence
    elif not retimed:
        sound = ["-ss", timebase.seek(segment.start), "-t", f"{length:.6f}", "-i", str(heard)]
    else:
        # A retimed picture: its take's sound by the shot's policy (C7, CT-0080) -- mute unless it says otherwise.
        from . import retime_sound

        policy = segment.retime_sound or "mute"
        made = destination.with_suffix(".sound.wav")
        try:
            if timemap == "ambiguous":
                raise ValidationError("its take is shown at several times at once: which sound to follow is ambiguous")
            said = retime_sound.build(policy, timemap, heard, made, stretch_with=segment.stretch_with or None)
            sound = ["-i", str(made)]
            notes.append(f"{segment.shot}: retimed -- " + (
                "its take's sound is muted (retime_sound: mute, the default); nothing out of sync is heard."
                if policy == "mute" else "; ".join(said) + "."))
        except ValidationError as error:
            notes.append(f"{segment.shot}: retimed -- {error}; its take's sound is muted.")
            policy, sound = "mute", silence
        if policy == "mute":
            segment.speech, segment.speech_spans = None, []
    run_process(["ffmpeg", "-y", "-loglevel", "error", "-i", str(piece), *sound, "-map", "0:v:0", "-map", "1:a:0",
                 "-c:v", "copy", "-c:a", "aac", "-shortest", str(destination)],
                expected_seconds=length, message=f"{segment.shot}: its sound under its drawing")
    if segment.speech:
        segment.speech = (segment.speech[0] - segment.start, segment.speech[1] - segment.start)
    segment.source, segment.piece, segment.start, segment.end = str(destination), str(piece), 0.0, length


def _frames_keeping(pictures: Any, index: int, kept: list[Any]):
    """The frames as they come, with frame ``index`` kept aside (a still taken from the cut being drawn)."""

    for number, picture in enumerate(pictures):
        if number == index:
            kept.append(picture)
        yield picture


def _source_frame(root: Path, plan: Plan) -> tuple[dict[str, Any], float]:
    """The cut's frame and rate before a format reframes it: decided once, for the render and a still."""

    # A moving take decides the frame and the rate; a still only when there is nothing else.
    real = (next((segment for segment in plan.segments if segment.media and not segment.still), None)
            or next((segment for segment in plan.segments if segment.media), None))
    first = probe(root / real.media) if real else {"width": 1280, "height": 720, "fps": FPS, "audio": False}
    if real and real.still:
        first["fps"] = FPS  # a picture has no rate; what ffprobe reports for one is a default
    if plan.frame:
        # The production's frame, whatever its first take is (CT-0068); its rate, when it gives one.
        first = {**first, "width": plan.frame["width"], "height": plan.frame["height"],
                 "fps": plan.frame.get("fps") or first["fps"]}
    return first, first["fps"] or FPS


def _starts(plan: Plan) -> list[float]:
    """Where each shot starts in the cut: a transition takes its length from both shots it joins."""

    starts, clock = [], 0.0
    for segment in plan.segments:
        clock -= segment.overlap
        starts.append(max(clock, 0.0))
        clock += segment.end - segment.start
    return starts


def still(root: Path, plan: Plan, shot: str, destination: Path, at: float | None = None) -> Path:
    """A shot's frame at ``at`` seconds into it (its middle when not given), as the cut draws it: the shot's
    one graph -- its picture, effects and title (CT-0078) -- run at that instant, at the cut's frame and rate,
    with the cut's beats (CT-0072). A shot cut from a take with nothing over it is the take's frame, read
    through the same conform. An instant inside a join belongs to the sequence, not to one shot (recorded in
    the compositing roadmap).
    """

    from .compositing import reference

    index = next((number for number, segment in enumerate(plan.segments) if segment.shot == shot), None)
    if index is None:
        raise ValidationError(f"{shot} is not in this cut")
    segment = plan.segments[index]
    if segment.method.startswith("solid:") or not (segment.media or segment.composite or segment.title):
        raise ValidationError(f"{shot} has no picture to draw a still from")
    first, fps = _source_frame(root, plan)
    if plan.format.get("aspect"):
        from .formats import target_size

        first = {**first, **dict(zip(("width", "height"), target_size(first["width"], first["height"],
                                                                      plan.format["aspect"])))}
    length = segment.end - segment.start
    frames = max(1, round(length * fps))
    wanted = frames // 2 if at is None else min(frames - 1, max(0, round(float(at) * fps)))
    size = (first["width"] // 2 * 2, first["height"] // 2 * 2)
    pictures, _fast, _cached = _shot_drawing(root, segment, size, fps, plan.beats, _starts(plan)[index])
    for number, picture in enumerate(pictures):
        if number == wanted:
            return reference.write_still(picture, destination)
    raise ValidationError(f"{shot}: its graph gave no frame {wanted}")


from .compositing.reference import conform_filter  # one rule for fitting a picture to the frame (CT-0072)


def iris_expression(start: float, end: float, until: float, duration: float) -> str:
    """Whether a pixel is inside the iris at time T: a circle from the centre, growing evenly, never stopping."""

    grow = f"({start}+({end}-{start})*min(T/{max(until * duration, 0.04):.3f},1))"
    return f"lte(hypot(X-W/2,Y-H/2),{grow}*hypot(W/2,H/2))"


def _iris(ffmpeg: str, picture: Path, plan: Plan, work: Path, run_process, span) -> Path:
    """The scene seen through an iris that opens across its whole length (one continuous move, not per shot)."""

    reveal = plan.reveal
    inside = iris_expression(float(reveal.get("from", 0.1)), float(reveal.get("to", 1.0)),
                             float(reveal.get("until", 1.0)), plan.duration)
    output = work / "picture-iris.mp4"
    run_process([ffmpeg, "-y", "-loglevel", "error", "-i", str(picture), "-vf",
                 f"format=yuv444p,geq=lum='if({inside},lum(X,Y),16)':cb='if({inside},cb(X,Y),128)'"
                 f":cr='if({inside},cr(X,Y),128)',format=yuv420p",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(output)],
                message="Opening the iris across the scene", span=span)
    return output


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
    first, fps = _source_frame(root, plan)
    if plan.format.get("aspect"):
        first = _reframe(root, plan, first, work, run_process, within(0.0, 0.05))
    width, height = first["width"] // 2 * 2, first["height"] // 2 * 2
    size = f"{width}:{height}"
    segment_gain: dict[str, float] = {}
    plan.gains = segment_gain
    total = len(plan.segments)
    count = [0] * total  # frames of each piece
    overlap = [0] * (total + 1)  # frames each transition takes, into segment i
    pictures, sounds = [], []
    speaking: list[bool] = []  # whether someone speaks in each shot: its sound goes to the centre in a 5.1
    starts = _starts(plan)
    for index, segment in enumerate(plan.segments):
        if segment.method.startswith("solid:") and not segment.source:
            solid = work / f"solid-{index:03d}.mp4"
            length = segment.end - segment.start
            run_process(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                         f"color=c={segment.method.split(':', 1)[1]}:s={first['width'] // 2 * 2}x{first['height'] // 2 * 2}"
                         f":r={timebase.ffmpeg_rate(fps)}:d={length:.6f}", "-f", "lavfi", "-t", f"{length:.3f}", "-i",
                         "anullsrc=channel_layout=stereo:sample_rate=48000", "-shortest", "-c:v", "libx264",
                         "-pix_fmt", "yuv420p", "-c:a", "aac", str(solid)],
                        expected_seconds=length, message=f"{segment.shot}: {segment.method.split(':', 1)[1]} screen")
            segment.source = str(solid)
        if _drawn(segment) and not segment.source:
            # One graph, drawn once, written once as the cut's piece (CT-0078).
            kept = work / "stills" / f"{segment.shot}.png"
            _draw_shot(root, segment, work / f"shot-{index:03d}.mp4", first, fps, run_process, plan.notes,
                       plan.beats, starts[index], still=kept)
            if kept.is_file():
                plan.stills[segment.shot] = str(kept)
        source = Path(segment.source) if segment.source else root / segment.media
        length = segment.end - segment.start
        picture = work / f"picture-{index:03d}.mp4"
        if segment.piece:  # drawn by its graph as a piece of the cut: joined as it is
            pictures.append(Path(segment.piece))
            count[index] = _frames_in(Path(segment.piece)) or max(1, round(length * fps))
            continue
        # From the frame the cut point is (snapped when planned); the frame count bounds the piece.
        run_process([ffmpeg, "-y", "-loglevel", "error", "-ss", timebase.seek(segment.start),
                     "-t", f"{length + 2 / fps:.6f}", "-i", str(source), "-map", "0:v:0",
                     "-vf", conform_filter(width, height, transparent=False) + f",fps={timebase.ffmpeg_rate(fps)},format=yuv420p",
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
            unit = "version" if segment.method == "version" else "take"
            whose = f"its {unit}" if segment.join == "j" else f"{previous.shot}'s {unit}"
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
    # Where each piece starts, counted in frames and turned into seconds once: exact at any rate (CT-0079).
    starts, frames_in = [], 0
    for index in range(total):
        frames_in -= overlap[index]
        starts.append(float(timebase.seconds_of(frames_in, fps)))
        frames_in += count[index]
    duration = float(timebase.seconds_of(frames_in, fps))
    plan_duration_frames = round(duration * fps)
    plan.rate, plan.size = fps, (width, height)
    plan.timeline = []
    for index, segment in enumerate(plan.segments):
        if segment.piece:  # drawn by its graph: its own piece, from its first frame
            kind, file, source_in = "drawn", segment.piece, 0.0
        elif segment.source and segment.method.startswith("solid:"):
            kind, file, source_in = "solid", "", 0.0
        else:
            kind, file, source_in = "take", str(Path(segment.source) if segment.source else root / segment.media), \
                segment.start
        plan.timeline.append({"shot": segment.shot, "take": segment.take, "kind": kind, "file": file,
                              "source_in": source_in, "frames": count[index], "overlap_in": overlap[index],
                              "transition": segment.transition,
                              **({"colour": segment.method.split(":", 1)[1]} if kind == "solid" else {})})
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
        if segment.sound_fades_at is not None and before + segment.sound_fades_at < fade_end:
            # The shot's sound goes down from a point (SINGULAR's `som_baixa_de`: when the title comes in).
            fade_out = max(0.12, fade_end - before - segment.sound_fades_at)
        fades = ([f"afade=t=in:d={fade_in:.3f}"] if fade_in else []) + (
            [f"afade=t=out:st={fade_end - fade_out:.3f}:d={fade_out:.3f}"] if fade_out else [])
        # Stretches of the take silenced, in the take's own seconds; the clip starts `before` ahead of the cut.
        clip_start = segment.start - before
        fades += [f"volume=0:enable='between(t,{a - clip_start:.3f},{b - clip_start:.3f})'" for a, b in segment.mute
                  if b > clip_start]
        clip = work / f"sound-{index:03d}.wav"
        # The span in samples, from the same frame boundaries as the picture (CT-0079).
        span_samples = timebase.samples(span_seconds)
        if has_audio:
            command = [ffmpeg, "-y", "-loglevel", "error", "-ss", timebase.seek(segment.start - before),
                       "-t", f"{span_seconds + 0.1:.6f}", "-i", str(sound or source), "-map", "0:a:0"]
        else:
            command = [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-t", f"{span_seconds + 0.1:.6f}",
                       "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        run_process(command + ["-af", ",".join([f"volume={gain}dB", "aresample=48000",
                                                 "aformat=sample_fmts=fltp:channel_layouts=stereo",
                                                 f"apad=whole_len={span_samples}", f"atrim=end_sample={span_samples}",
                                                 *fades]),
                               "-ar", "48000", "-ac", "2", str(clip)],
                    expected_seconds=span_seconds, message=f"{segment.shot}: its sound",
                    span=within(0.6 + 0.25 * index / total, 0.6 + 0.25 * (index + 1) / total))
        sounds.append((clip, max(0.0, starts[index] - before)))
        speaking.append(bool(segment.speech or segment.speech_spans))
    # Voices laid in the montage (a narration): each at its time in its shot, brought to speech level.
    voiced: list[tuple[float, float]] = []
    for index, segment in enumerate(plan.segments):
        for number, (at, file) in enumerate(segment.voice_over):
            path = Path(file)
            if not path.is_file():
                plan.notes.append(f"{segment.shot}: the voice {path.name} is not there; it is not heard.")
                continue
            when = starts[index] + at - segment.start
            if when >= duration:
                continue
            seconds = probe(path)["duration"]
            gain = loudness_gain(path, Segment(segment.shot, "", "", 0.0, seconds, speech=(0.0, seconds)))
            clip = work / f"voice-{index:03d}-{number}.wav"
            run_process([ffmpeg, "-y", "-loglevel", "error", "-i", str(path), "-af",
                         f"volume={gain}dB,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo",
                         "-ar", "48000", "-ac", "2", str(clip)], message=f"{segment.shot}: its voice-over")
            sounds.append((clip, max(0.0, when)))
            speaking.append(True)
            voiced.append((round(when, 3), round(when + seconds, 3)))
    picture = _join_pictures(ffmpeg, plan, pictures, count, overlap, work, fps, width, height, run_process,
                             within(0.85, 0.9))
    captions = [(starts[index] + max(0.0, a - segment.start), starts[index] + min(segment.end, b) - segment.start, text)
                for index, segment in enumerate(plan.segments) for a, b, text in segment.captions
                if b > segment.start and a < segment.end] if plan.format.get("captions") else []
    if plan.reveal.get("kind") == "iris":
        picture = _iris(ffmpeg, picture, plan, work, run_process, within(0.85, 0.9))
    titles = [(starts[index] + max(0.0, a - segment.start), starts[index] + min(segment.end, b) - segment.start, text)
              for index, segment in enumerate(plan.segments) for a, b, text in segment.subtitles
              if b > segment.start and a < segment.end]
    if titles:
        from .formats import write_srt

        plan.subtitle_file = str(write_srt(titles, work / "subtitles.srt"))
    burned = captions + (titles if titles and plan.subtitles.get("burn", True) else [])
    if burned:
        from .formats import subtitles_filter, write_ass

        film = not captions  # a film's subtitles alone: smaller and lower than a format's captions
        ass = write_ass(burned, (width, height), work / "captions.ass",
                        scale=0.056 if film else 0.075, margin_ratio=0.05 if film else None)
        captioned = work / "picture-captioned.mp4"
        run_process([ffmpeg, "-y", "-loglevel", "error", "-i", str(picture), "-vf", subtitles_filter(ass),
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(captioned)],
                    message=f"Burning {len(burned)} captions", span=within(0.9, 0.91))
        picture = captioned
    mixed = work / "sound.wav"
    inputs = [part for clip, _ in sounds for part in ("-i", str(clip))]
    # Each sound at its sample, not its millisecond (CT-0079).
    delays = ";".join(f"[{index}:a]adelay={timebase.samples(at)}S:all=1[s{index}]"
                      for index, (_, at) in enumerate(sounds))
    labels = "".join(f"[s{index}]" for index in range(len(sounds)))
    run_process([ffmpeg, "-y", "-loglevel", "error", *inputs, "-filter_complex",
                 f"{delays};{labels}amix=inputs={len(sounds)}:normalize=0:duration=longest,"
                 f"apad=whole_len={timebase.samples(duration)},atrim=end_sample={timebase.samples(duration)}[a]",
                 "-map", "[a]", "-ar", "48000", "-ac", "2", str(mixed)],
                message="Laying the takes' sound", span=within(0.9, 0.92))
    joined = work / "joined.mp4" if plan.cues else output
    run_process([ffmpeg, "-y", "-loglevel", "error", "-i", str(picture), "-i", str(mixed), "-map", "0:v:0",
                 "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                 "-frames:v", str(plan_duration_frames), "-shortest", "-movflags", "+faststart", str(joined)],
                message="Joining the shots", span=within(0.92, 0.93 if plan.cues else 1.0))
    speech = []
    for index, segment in enumerate(plan.segments):
        if segment.speech_spans:
            speech += [(starts[index] + a - segment.start, starts[index] + b - segment.start)
                       for a, b in segment.speech_spans if b > segment.start and a < segment.end]
        elif segment.speech:
            speech.append((starts[index] + max(0.0, segment.speech[0] - segment.start),
                           starts[index] + min(segment.end, segment.speech[1]) - segment.start))
    speech += voiced
    plan.speech = sorted((round(a, 3), round(b, 3)) for a, b in speech)
    if plan.cues:
        from .sounds import list_sounds, mix

        catalog = {item["id"]: item for item in list_sounds(root)}

        def run_sound(command, expected_seconds=None, message=""):
            run_process(command, expected_seconds=expected_seconds, message=message, span=within(0.93, 1.0))

        plan.sound = mix(joined, plan.cues, catalog, speech, output, work / "sound", run_sound)
    cues = [(work / "sound" / f"sound-{index:03d}.wav", cue, laid["gain_db"])
            for index, (cue, laid) in enumerate(zip(plan.cues, plan.sound))]
    takes = [(clip, at, speaks) for (clip, at), speaks in zip(sounds, speaking)]
    if plan.stems:
        from . import stems

        folder = work / "stems"
        stems.write(takes, cues, speech, duration, folder,
                    lambda command, expected_seconds=None, message="": run_process(
                        command, expected_seconds=expected_seconds, message=message, span=within(0.96, 0.97)))
        plan.stems_folder = str(folder)
    if plan.surround == "5.1":
        from . import surround

        wide = surround.mix(takes, cues, speech, duration, work / "surround.wav",
                            lambda command, expected_seconds=None, message="": run_process(
                                command, expected_seconds=expected_seconds, message=message, span=within(0.97, 0.99)))
        stereo_only = work / "stereo-only.mp4"
        shutil.move(output, stereo_only)
        surround.attach(stereo_only, wide, output, lambda command, message="": run_process(
            command, message=message, span=within(0.99, 1.0)))
        plan.loudness = {name: value for name, value in (("stereo", surround.loudness(output, 0)),
                                                         ("5.1", surround.loudness(output, 1))) if value is not None}
    elif plan.surround:
        plan.notes.append(f"A {plan.surround} mix is not made yet; only 5.1 is (CT-0052).")


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


def _reframe(root: Path, plan: Plan, first: dict[str, Any], work: Path, run_process,
             span: tuple[float, float]) -> dict[str, Any]:
    """Each take reframed to the format's aspect, whole (its handles kept for J/L-cuts); the new frame's size."""

    from .formats import reframe_filter, target_size

    target = target_size(first["width"], first["height"], plan.format["aspect"])
    for index, segment in enumerate(plan.segments):
        if not segment.media:
            continue
        source = root / segment.media
        info = probe(source)
        if (info["width"] // 2 * 2, info["height"] // 2 * 2) == target:
            continue
        where = segment.reframe or {}
        reframed = work / f"reframed-{index:03d}.mp4"
        run_process(["ffmpeg", "-y", "-loglevel", "error", "-i", str(source), "-vf",
                     reframe_filter(info["width"], info["height"], target, float(where.get("x", 0.5)),
                                    float(where.get("y", 0.5))),
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy",
                     str(reframed)], expected_seconds=info["duration"],
                    message=f"{segment.shot}: reframed to {plan.format['aspect']}", span=span)
        segment.media = str(reframed)  # an absolute path: the take is left as it is
    return {**first, "width": target[0], "height": target[1]}


def _graph_join(outgoing: Path, incoming: Path, outgoing_frames: int, frames: int, transition: dict[str, Any],
                destination: Path, *, fps: float, width: int, height: int,
                extra: dict[str, Any] | None = None) -> Path:
    """A join drawn from its recipe's graph -- GL when it covers the graph, else the reference: the last frames of
    one picture, the first of the next, and the recipe's own pictures, both pictures playing through it."""

    from .compositing import reference

    size = (width, height)
    inputs: dict[str, Any] = {
        "from": reference.read(outgoing, frames, size, fps, start=(outgoing_frames - frames) / fps),
        "to": reference.read(incoming, frames, size, fps),
    }
    for name, path in (transition.get("inputs") or {}).items():
        inputs[name] = reference.read(Path(path), frames, size, fps)
    inputs.update(extra or {})
    from .compositing.gl import renderer_for

    pictures, _, _ = reference.render(transition["graph"], inputs, frames=frames, size=size, fps=fps,
                                      renderer=renderer_for(transition["graph"]))
    silent = destination.with_suffix(".picture.mp4")
    reference.write(pictures, silent, fps)
    silent.replace(destination)
    return destination


def shader_recipe(transition: dict[str, Any]) -> dict[str, Any]:
    """A gl-transitions join as a SPEC-0012 graph: one opaque node with the shader, its uniforms and textures."""

    textures = {name: name for name in transition.get("textures") or {}}
    uniforms = {param["name"]: param["default"] for param in transition.get("params") or []}
    ports = {"from": "picture", "to": "picture", "progress": "curve", **{name: "picture" for name in textures}}
    return {"ports": ports, "output": "out",
            "nodes": {"out": {"op": "opaque.gl", "shader": transition["shader"], "from": "from", "to": "to",
                              "progress": "progress", "uniforms": uniforms, "textures": textures}}}


def _lay_overlay(clip: Path, overlay: Path, destination: Path, blend: str, frames: int, fps: float,
                 size: tuple[int, int], notes: list[str], label: str) -> Path:
    """An overlay with alpha over a drawn join, as a graph (ADR 0022): over, or a screen or add blend."""

    from .compositing import reference
    from .compositing.gl import renderer_for
    from .mattes import overlay_notes, overlay_recipe

    said, usable = overlay_notes(overlay, frames / fps, fps, label)
    notes.extend(said)
    if not usable:
        return clip
    graph = overlay_recipe(blend)
    # At its own rate from the join's start; one shorter than the join ends there, transparent after.
    inputs = {"joined": reference.read(clip, frames, size, fps),
              "overlay": reference.read(overlay, frames, size, fps, alpha="straight", hold=False)}
    pictures, _, _ = reference.render(graph, inputs, frames=frames, size=size, fps=fps, renderer=renderer_for(graph))
    reference.write(pictures, destination, fps)
    return destination


def _join_pictures(ffmpeg: str, plan: Plan, pictures: list[Path], count: list[int], overlap: list[int], work: Path,
                   fps: float, width: int, height: int, run_process, span: tuple[float, float]) -> Path:
    """The pieces joined: straight cuts, and each transition as its own clip between the bodies."""

    destination = work / "picture.mp4"
    encode = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", timebase.ffmpeg_rate(fps)]
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
            if transition.get("graph"):
                _graph_join(picture, pictures[index + 1], count[index], frames, transition, clip, fps=fps,
                            width=width, height=height)
            elif isinstance(transition.get("matte"), dict):
                from .mattes import generated_recipe

                _graph_join(picture, pictures[index + 1], count[index], frames,
                            {"graph": generated_recipe(transition["matte"], transition.get("softness") or 0.0)}, clip,
                            fps=fps, width=width, height=height)
            elif transition.get("matte"):
                from .compositing.reference import read
                from .mattes import is_moving, matte_notes, recipe

                matte = Path(transition["matte"])
                moving = is_moving(matte)
                plan.notes.extend(matte_notes(matte, frames / fps, fps, following.shot))
                _graph_join(picture, pictures[index + 1], count[index], frames,
                            {"graph": recipe(moving, transition.get("softness") or 0.0)}, clip, fps=fps, width=width,
                            height=height, extra={"matte_clip": read(matte, frames, (width, height), fps,
                                                                     stretch_to=frames / fps if moving else None)})
            elif transition.get("shader"):
                # A gl-transitions shader: an opaque node of the graph, run by the GL renderer (CT-0072, B1).
                from .compositing.reference import read

                textures = {name: read(Path(path), frames, (width, height), fps)
                            for name, path in (transition.get("textures") or {}).items()}
                _graph_join(picture, pictures[index + 1], count[index], frames, {"graph": shader_recipe(transition)},
                            clip, fps=fps, width=width, height=height, extra=textures)
            else:
                tail = count[index] - frames
                run_process([ffmpeg, "-y", "-loglevel", "error", "-i", str(picture), "-i", str(pictures[index + 1]),
                             "-filter_complex",
                             f"[0:v]trim=start_frame={tail}:end_frame={count[index]},setpts=PTS-STARTPTS[a];"
                             f"[1:v]trim=end_frame={frames},setpts=PTS-STARTPTS[b];"
                             f"[a][b]xfade=transition={transition['mode']}:duration={frames / fps:.3f}:offset=0[v]",
                             "-map", "[v]", "-frames:v", str(frames), *encode, str(clip)],
                            message=f"{following.shot}: {transition['id']}", span=span)
            if transition.get("overlay"):
                clip = _lay_overlay(clip, Path(transition["overlay"]), work / f"join-{index + 1:03d}-overlay.mp4",
                                    transition.get("blend") or "normal", frames, fps, (width, height), plan.notes,
                                    following.shot)
            pieces.append(clip)
    listing = work / "pictures.txt"
    listing.write_text("".join(f"file '{piece.name}'\n" for piece in pieces), encoding="utf-8")
    # Pieces straight from the takes join as they are; with transition clips among them, encoded once more.
    codec = ["-c", "copy"] if not any(overlap) else encode
    run_process([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                 *codec, str(destination)], message="Joining the pictures", span=span)
    return destination
