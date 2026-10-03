"""Sound: a catalog of ambiences, effects, Foley and music, placed on the cut (CT-0048).

From SINGULAR's practice (its `AMBIENTES` and `EFEITOS` tables, its sound
layers and its bed that stops before the end), as a catalog like titles and
transitions. An item is a manifest (`sound_assets/<id>/sound.toml`): what it
is, when to use it, its source and its defaults:

- `generate`: an FFmpeg audio graph ending on an open output, `{d}` its
  duration -- every built-in item, ours, no licence to check;
- `file`: a recording beside the manifest (or a path), with its `licence`
  and `credit` -- a production's own Foley, a library pack, a score.

Catalogs layer: built in, `CINE_TOASTER_SOUNDS_PATH`, then the
production's `sounds/`; a later layer replaces an item with the same id.

Where sound is placed:

- a shot's `sounds: [door, {id: alarm, at: 1.2, level: -20}]`: from `at`
  seconds into the shot as cut, for the item's duration;
- a scene's `ambience` and `music`: an id or `{id, from, at, to, until,
  duration, level, fade_in, fade_out, duck}` -- from a shot (the first by
  default, `at` seconds into it) to the end of `to` (inclusive) or the start
  of `until` (exclusive), the last shot by default. Several may be listed.

Each placed sound is brought to its `level` (integrated LUFS; the take's
speech is at -20): ambience -34, effects -24, Foley -28, music -24. Music
is lowered by `duck` dB (10 by default) under the speech the cut knows of
(the word timings of each take), with short ramps, never cut off.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from .errors import ValidationError

BUILTIN = Path(__file__).with_name("sound_assets")
CATEGORIES = ("ambience", "effect", "foley", "music")
#: What each category starts from, unless the item or the placement says otherwise.
DEFAULTS: dict[str, dict[str, Any]] = {
    "ambience": {"level": -34.0, "loop": True, "fade_in": 1.0, "fade_out": 1.2, "duck": 0.0, "duration": 0.0},
    "effect": {"level": -24.0, "loop": False, "fade_in": 0.0, "fade_out": 0.05, "duck": 0.0, "duration": 1.0},
    "foley": {"level": -28.0, "loop": False, "fade_in": 0.0, "fade_out": 0.05, "duck": 0.0, "duration": 1.0},
    "music": {"level": -24.0, "loop": False, "fade_in": 1.5, "fade_out": 2.0, "duck": 10.0, "duration": 0.0},
}
#: How long the music takes to go down before a line, and to come back after it.
DUCK_RAMP = 0.3
PLACEMENT_KEYS = {"id", "at", "from", "to", "until", "reason", *next(iter(DEFAULTS.values()))}


# --- the catalog -------------------------------------------------------------------


def _roots(project_root: Path | None) -> list[tuple[str, Path]]:
    roots = [("built-in", BUILTIN)]
    for position, raw in enumerate(filter(None, os.environ.get("CINE_TOASTER_SOUNDS_PATH", "").split(os.pathsep)), 1):
        roots.append((f"external-{position}", Path(raw).expanduser()))
    if project_root is not None:
        roots.append(("project", Path(project_root).expanduser().resolve() / "sounds"))
    return roots


def _load(path: Path, origin: str) -> dict[str, Any]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValidationError(f"Unreadable sound {path}: {error}") from error
    category = str(raw.get("category") or "effect")
    source = raw.get("source") or {}
    file = str(source.get("file") or "")
    resolved = (path.parent / file).expanduser() if file else None
    return {
        "id": str(raw.get("id") or path.parent.name),
        "name": str(raw.get("name") or path.parent.name),
        "category": category,
        "says": str(raw.get("says") or ""),
        "use_when": [str(item) for item in raw.get("use_when") or []],
        "avoid_when": [str(item) for item in raw.get("avoid_when") or []],
        "params": {**DEFAULTS.get(category, DEFAULTS["effect"]), **(raw.get("params") or {})},
        "generate": str(source.get("generate") or "").strip(),
        "file": str(resolved) if resolved else "",
        "exists": bool(resolved and resolved.is_file()) if resolved else bool(source.get("generate")),
        "licence": str(source.get("licence") or ("ours (generated)" if source.get("generate") else "")),
        "credit": str(source.get("credit") or ""),
        # Where the recording came from (a library, a search), its page, and whether it is final.
        "provenance": str(source.get("provenance") or ""),
        "url": str(source.get("url") or ""),
        "status": str(source.get("status") or ""),
        "origin": origin,
        "directory": str(path.parent),
    }


def list_sounds(project_root: Path | None = None) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for origin, root in _roots(project_root):
        if root.is_dir():
            for manifest in sorted(root.glob("*/sound.toml")):
                item = _load(manifest, origin)
                by_id[item["id"]] = item
    order = {name: index for index, name in enumerate(CATEGORIES)}
    return sorted(by_id.values(), key=lambda item: (order.get(item["category"], 99), item["name"]))


def expand(raw: Any, catalog: dict[str, dict[str, Any]], *, placed_on: str = "shot",
           shots: tuple[str, ...] = ()) -> tuple[list[dict[str, Any]], list[str]]:
    """Placements with their items' defaults: (sounds, problems).

    `raw` is an id, a mapping, or a list of either. On a scene (`placed_on`
    "scene"), `from`, `to` and `until` must name its shots.
    """

    if raw in (None, "", [], {}):
        return [], []
    expanded, problems = [], []
    for entry in raw if isinstance(raw, list) else [raw]:
        declared = {"id": str(entry)} if isinstance(entry, str) else dict(entry or {})
        item = catalog.get(str(declared.get("id") or ""))
        if item is None:
            problems.append(f"names the sound {declared.get('id')!r}, which is not in the sound catalog")
            continue
        if not item["exists"]:
            problems.append(f"names the sound {item['id']!r}, whose file {item['file']} is missing")
            continue
        unknown = sorted(set(declared) - PLACEMENT_KEYS)
        if unknown:
            problems.append(f"places {item['id']!r} with {', '.join(unknown)}, which a sound does not have")
            continue
        params = {**item["params"], **{key: value for key, value in declared.items() if key in item["params"]}}
        try:
            numbers = {key: float(params[key]) for key in ("level", "fade_in", "fade_out", "duck", "duration")}
            at = float(declared.get("at") or 0.0)
        except (TypeError, ValueError):
            problems.append(f"places {item['id']!r} with a level, a time or a fade that is not a number")
            continue
        if at < 0 or min(numbers["fade_in"], numbers["fade_out"], numbers["duration"], numbers["duck"]) < 0:
            problems.append(f"places {item['id']!r} with a negative time, duration, fade or duck")
            continue
        placement = {"id": item["id"], "category": item["category"], "at": at, **numbers,
                     "loop": bool(params.get("loop")), "reason": str(declared.get("reason") or "")}
        if placed_on == "scene":
            for key in ("from", "to", "until"):
                if declared.get(key) is not None:
                    shot = str(declared[key]).strip().upper()
                    if shots and shot not in shots:
                        problems.append(f"plays {item['id']!r} {key} {shot}, which is not one of its shots")
                        break
                    placement[key] = shot
            else:
                expanded.append(placement)
            continue
        expanded.append(placement)
    return expanded, problems


# --- placing on the cut -------------------------------------------------------------


def place(scene: dict[str, Any], segments: list[Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Where each sound plays on the cut's timeline: (cues, notes).

    `segments` are the plan's, in order, each with `shot`, `start` and `end`.
    A cue is its placement with `start` and `length` in seconds of the cut.
    """

    starts, ends, clock = {}, {}, 0.0
    for segment in segments:
        clock -= getattr(segment, "overlap", 0.0)  # a transition takes from both shots it joins
        starts[segment.shot] = clock
        clock += segment.end - segment.start
        ends[segment.shot] = clock
    total = clock
    cues, notes = [], []
    by_shot = {shot["id"]: shot for shot in scene.get("shots") or []}
    for segment in segments:
        for sound in (by_shot.get(segment.shot) or {}).get("sounds") or []:
            begin = starts[segment.shot] + sound["at"]
            if begin >= ends[segment.shot]:
                notes.append(f"{segment.shot}: {sound['id']} at {sound['at']} s starts after the shot is cut; "
                             "it is not heard.")
                continue
            length = sound["duration"] or (ends[segment.shot] - begin)
            cues.append({**sound, "kind": "shot", "shot": segment.shot, "start": round(begin, 3),
                         "length": round(min(length, total - begin), 3)})
    for kind in ("ambience", "music"):
        for sound in scene.get(kind) or []:
            first = sound.get("from") or segments[0].shot
            if first not in starts:
                notes.append(f"The {kind} {sound['id']} starts on {first}, which is not in this version; "
                             "it is not heard.")
                continue
            begin = starts[first] + sound["at"]
            if sound.get("until"):
                finish = starts.get(sound["until"])
            elif sound.get("to"):
                finish = ends.get(sound["to"])
            else:
                finish = total
            if finish is None:
                notes.append(f"The {kind} {sound['id']} ends on {sound.get('until') or sound.get('to')}, which is not "
                             "in this version; it plays to the end.")
                finish = total
            if sound["duration"]:
                finish = min(finish, begin + sound["duration"])
            if finish - begin <= 0.05:
                notes.append(f"The {kind} {sound['id']} ends before it starts; it is not heard.")
                continue
            cues.append({**sound, "kind": kind, "start": round(begin, 3), "length": round(finish - begin, 3)})
    return cues, notes


# --- rendering ----------------------------------------------------------------------


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if not found:
        raise ValidationError("FFmpeg is needed for sound")
    return found


def _probe_seconds(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    completed = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                               capture_output=True, text=True, timeout=60)
    try:
        return float(completed.stdout.strip() or 0)
    except ValueError:
        return 0.0


def prepare_command(item: dict[str, Any], cue: dict[str, Any], output: Path) -> tuple[list[str], float]:
    """The FFmpeg command that writes a cue's sound, 48 kHz stereo, faded: (command, length)."""

    length = float(cue["length"])
    if item["file"] and not cue.get("loop"):
        available = _probe_seconds(Path(item["file"]))
        if available:
            length = min(length, available)
    fades = []
    fade_in = min(float(cue["fade_in"]), length / 2)
    fade_out = min(float(cue["fade_out"]), length / 2)
    if fade_in > 0:
        fades.append(f"afade=t=in:d={fade_in:.3f}")
    if fade_out > 0:
        fades.append(f"afade=t=out:st={length - fade_out:.3f}:d={fade_out:.3f}")
    tail = ",".join(["aresample=48000", "aformat=sample_fmts=fltp:channel_layouts=stereo",
                     f"atrim=0:{length:.3f}", "asetpts=PTS-STARTPTS", *fades])
    command = [_ffmpeg(), "-y", "-loglevel", "error"]
    if item["generate"]:
        command += ["-filter_complex", item["generate"].replace("{d}", f"{length:.3f}") + "," + tail]
    else:
        command += [*(["-stream_loop", "-1"] if cue.get("loop") else []), "-i", item["file"], "-af", tail]
    return command + ["-t", f"{length:.3f}", "-ar", "48000", "-ac", "2", str(output)], length


def loudness(path: Path) -> float | None:
    """Integrated loudness in LUFS; a short sound is measured padded to the meter's window."""

    completed = subprocess.run([_ffmpeg(), "-hide_banner", "-i", str(path), "-af", "apad=whole_dur=0.8,ebur128",
                                "-f", "null", "-"], capture_output=True, text=True, timeout=120)
    measured = re.findall(r"I:\s+(-?[\d.]+) LUFS", completed.stderr)
    if not measured or float(measured[-1]) < -69:
        return None
    return float(measured[-1])


def duck_expression(speech: list[tuple[float, float]], duck_db: float) -> str:
    """A volume expression: 1 away from speech, `duck_db` lower under it, with ramps."""

    if not speech or duck_db <= 0:
        return "1"
    floor = 10 ** (-duck_db / 20)
    ramps = [f"clip(min((t-{a - DUCK_RAMP:.3f})/{DUCK_RAMP},({b + DUCK_RAMP:.3f}-t)/{DUCK_RAMP}),0,1)"
             for a, b in speech]
    under = ramps[0]
    for ramp in ramps[1:]:
        under = f"max({under},{ramp})"
    return f"1-{1 - floor:.4f}*{under}"


def mix(picture: Path, cues: list[dict[str, Any]], catalog: dict[str, dict[str, Any]],
        speech: list[tuple[float, float]], output: Path, work: Path, run_process) -> list[dict[str, Any]]:
    """Lay the cues under the cut's own sound and write `output`; return what was laid, with gains."""

    work.mkdir(parents=True, exist_ok=True)
    inputs, chains, laid = [], [], []
    for index, cue in enumerate(cues):
        item = catalog[cue["id"]]
        prepared = work / f"sound-{index:03d}.wav"
        command, length = prepare_command(item, cue, prepared)
        run_process(command, expected_seconds=length, message=f"Sound: {cue['id']}")
        measured = loudness(prepared)
        gain = 0.0 if measured is None else round(max(-30.0, min(30.0, cue["level"] - measured)), 1)
        label = f"c{index}"
        chain = f"[{index + 1}:a]volume={gain}dB,adelay={int(round(cue['start'] * 1000))}:all=1"
        if cue["duck"] > 0 and speech:
            chain += f",volume='{duck_expression(speech, cue['duck'])}':eval=frame"
        chains.append(chain + f"[{label}]")
        inputs += ["-i", str(prepared)]
        laid.append({key: cue[key] for key in ("kind", "id", "start", "length", "level", "duck")}
                    | ({"shot": cue["shot"]} if cue.get("shot") else {})
                    | {"gain_db": gain, "licence": item["licence"], **({"credit": item["credit"]} if item["credit"] else {})})
    if not chains:
        shutil.copyfile(picture, output)
        return []
    labels = "".join(f"[c{index}]" for index in range(len(chains)))
    # amix's duration=first ends early when a delayed input is still playing; mix them all, then trim to the cut.
    total = _probe_seconds(picture)
    graph = ";".join(chains) + (f";[0:a]{labels}amix=inputs={len(chains) + 1}:normalize=0:duration=longest,"
                                f"apad=whole_dur={total:.3f},atrim=0:{total:.3f},"
                                "alimiter=limit=0.95:level=disabled[a]")
    run_process([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(picture), *inputs, "-filter_complex", graph,
                 "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                 "-movflags", "+faststart", str(output)], message="Mixing the sound")
    return laid


def preview(item: dict[str, Any], output: Path, seconds: float = 0.0) -> Path:
    """An item heard alone, at its level: a WAV to listen to in the catalog."""

    cue = {**item["params"], "length": seconds or float(item["params"].get("duration") or 0) or 6.0}
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = output.with_suffix(".raw.wav")
    command, _ = prepare_command(item, cue, raw)
    subprocess.run(command, check=True, capture_output=True, timeout=300)
    measured = loudness(raw)
    gain = 0.0 if measured is None else max(-30.0, min(30.0, float(item["params"]["level"]) - measured))
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(raw), "-af", f"volume={gain:.1f}dB",
                    str(output)], check=True, capture_output=True, timeout=120)
    raw.unlink(missing_ok=True)
    return output


def cached_preview(item: dict[str, Any]) -> Path:
    """A preview kept in the disposable cache, keyed by the item's manifest."""

    import hashlib

    from .jobs import state_root

    manifest = Path(item["directory"]) / "sound.toml"
    key = hashlib.sha256(manifest.read_bytes() + item["file"].encode() + Path(__file__).read_bytes()).hexdigest()[:16]
    path = state_root() / "sound-previews" / f"{item['id']}-{key}.wav"
    if not path.is_file():
        preview(item, path)
    return path
