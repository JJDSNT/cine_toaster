"""A version's cut as OpenTimelineIO, to finish it in an editor (CT-0096): the picture's counterpart of the stems.

Written beside the version (`versions/vN.otio`) when it is asked for (`toast assemble --otio`), from the cut as
the assembly made it -- the frames each shot took on the timeline, the transitions between them, counted in
frames (CT-0079):

- **V1**, the cut: each shot a clip. A take is its file, from its cut point; a shot the compositing graph drew
  (a composite, a title, an effect, a still, a card) is its drawn piece, kept beside the version
  (`vN.media/`), since nothing else holds it; a solid screen is a generator, no file. Each clip says which shot
  and take it is (metadata `cine_toaster`).
- **Transitions** between clips, centred on the cut, of the frames the assembly overlapped -- an editor has
  the handles they need, as the assembly had.
- **V2**, disabled: the version itself, to check the conform against.
- **A1**, the version's mix; **A2...**, its stems when they were made (`--stems`): dialogue, room, effects,
  ambience, music.

What it does not carry yet, and says so in the timeline's metadata: J- and L-cuts are in the mix, not split
on the tracks; a sequence's scene joins are its scene versions' pictures.

OpenTimelineIO (Apache-2.0) is an optional extra (`make install-otio`); without it, asking for `--otio` is
refused with the command to run. Paths are absolute file URLs (what editors resolve); each clip's metadata
keeps the production-relative path too.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from .errors import ValidationError


def unavailable_reason() -> str:
    try:
        import opentimelineio  # noqa: F401
    except ImportError:
        return "OpenTimelineIO is not installed (make install-otio, or pip install -e '.[otio]')"
    return ""


def _url(path: Path) -> str:
    import opentimelineio as otio

    return otio.url_utils.url_from_filepath(str(Path(path).resolve()))


def _relative(path: Path, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


def write(items: list[dict[str, Any]], *, root: Path, name: str, fps: Any, size: tuple[int, int],
          version_file: Path, stems: dict[str, Path], output: Path) -> Path:
    """`items`: the cut as the assembly made it, one a shot -- `shot`, `take`, `kind` (take | drawn | solid),
    `file` (its picture, absolute), `source_in` (seconds into it where the shot starts), `frames` (its frames on
    the timeline), `overlap_in` (frames of the transition into it), `transition` (as the assembly resolved it),
    `colour` (a solid's)."""

    reason = unavailable_reason()
    if reason:
        raise ValidationError(f"A cut as OpenTimelineIO needs OpenTimelineIO: {reason}")
    import opentimelineio as otio

    rate = float(Fraction(fps).limit_denominator(1001000)) if not isinstance(fps, (int, float)) else float(fps)
    at = lambda frames: otio.opentime.RationalTime(frames, rate)  # noqa: E731
    seconds = lambda value: otio.opentime.RationalTime.from_seconds(value, rate)  # noqa: E731
    # Each transition centred on the cut, over the frames the assembly overlapped. In OpenTimelineIO a
    # transition's `in_offset` runs before the cut, on the entering shot's frames before its visible start, and
    # its `out_offset` after it, on the leaving shot's frames past its visible end: those are trimmed from the
    # clips, so the timeline keeps the assembly's length.
    entering = [int(item.get("overlap_in") or 0) for item in items] + [0]
    before = [frames // 2 for frames in entering]  # from the head of the shot entering
    after = [frames - frames // 2 for frames in entering]  # from the tail of the shot leaving
    cut = otio.schema.Track(name="V1 -- the cut", kind=otio.schema.TrackKind.Video)
    timeline_frames = 0
    for index, item in enumerate(items):
        head, tail = before[index], after[index + 1]
        frames = int(item["frames"]) - head - tail
        if frames <= 0:
            raise ValidationError(f"{item['shot']} is shorter than the transitions around it")
        if entering[index] and index:
            transition = item.get("transition") or {}
            cut.append(otio.schema.Transition(
                name=str(transition.get("id") or "transition"),
                transition_type=otio.schema.TransitionTypes.SMPTE_Dissolve,
                in_offset=at(before[index]), out_offset=at(after[index]),
                metadata={"cine_toaster": {"id": transition.get("id"), "seconds": transition.get("seconds"),
                                           "drawn_as": "the assembly's own transition; a dissolve here"}}))
        start = seconds(float(item.get("source_in") or 0.0)) + at(head)
        if item["kind"] == "solid":
            reference = otio.schema.GeneratorReference(name="solid", generator_kind="SolidColor",
                                                       parameters={"color": str(item.get("colour") or "black")})
        else:
            reference = otio.schema.ExternalReference(target_url=_url(Path(item["file"])))
        cut.append(otio.schema.Clip(
            name=f"{item['shot']} {item.get('take') or ''}".strip(), media_reference=reference,
            source_range=otio.opentime.TimeRange(start, at(frames)),
            metadata={"cine_toaster": {"shot": item["shot"], "take": item.get("take"), "kind": item["kind"],
                                       **({"file": _relative(Path(item["file"]), root)} if item.get("file") else {})}}))
        timeline_frames += int(item["frames"]) - entering[index]
    length = otio.opentime.TimeRange(at(0), at(timeline_frames))
    reference = otio.schema.Track(name="V2 -- the version, to conform against", kind=otio.schema.TrackKind.Video)
    reference.enabled = False
    reference.append(otio.schema.Clip(name=Path(version_file).name, source_range=length,
                                      media_reference=otio.schema.ExternalReference(target_url=_url(version_file))))
    tracks = [cut, reference]
    for label, file in [("the mix", version_file), *sorted(stems.items())]:
        track = otio.schema.Track(name=f"A{len(tracks) - 1} -- {label}", kind=otio.schema.TrackKind.Audio)
        track.append(otio.schema.Clip(name=label, source_range=length,
                                      media_reference=otio.schema.ExternalReference(target_url=_url(file))))
        tracks.append(track)
    timeline = otio.schema.Timeline(name=name, global_start_time=at(0), metadata={"cine_toaster": {
        "rate": str(fps), "size": list(size), "version": _relative(version_file, root),
        "not_carried": ["J- and L-cuts are in the mix, not split on the tracks",
                        "a transition's own look (a matte, a shader) is drawn in the version; here a dissolve"]}})
    for track in tracks:
        timeline.tracks.append(track)
    output.parent.mkdir(parents=True, exist_ok=True)
    otio.adapters.write_to_file(timeline, str(output))
    return output
