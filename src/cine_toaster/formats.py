"""A format's rules applied to a cut: its aspect, and burned-in captions (CT-0049).

A style's `format` axis (a viral vertical, a commercial...) says its
aspect and whether it carries captions. The assembly applies them:

- **aspect**: every take is reframed to it -- a window of the picture, as
  tall or as wide as the take allows, centred unless the shot says where
  (`reframe: {x: 0.3}`, 0 the left edge, 1 the right; `y` likewise) -- and
  scaled so the long side keeps the take's resolution. Titles are drawn in
  the new frame, so no text is cut;
- **captions**: the words spoken, in short groups timed to the speech --
  from the word sidecar's words when it has them, else the shot's lines
  spread over its speech -- burned into the picture (libass).

A cut can be **delivered in several formats at once** (`deliver:` on the
production or a scene): each rendition is the same cut -- the same takes,
joins and sound -- reframed and captioned for its format, kept with the
version.

An end card stays the author's: a format that wants one advises when the
last shot is not a title.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: A caption holds at most this many words, and breaks at a pause longer than this.
CAPTION_WORDS = 4
CAPTION_PAUSE = 0.6
CAPTION_MIN_SECONDS = 0.7


def ratio(aspect: str) -> float | None:
    """'9:16' -> 0.5625; '2.39:1' -> 2.39; nothing understood -> None."""

    try:
        width, _, height = str(aspect).partition(":")
        value = float(width) / float(height or 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return value if value > 0 else None


def target_size(width: int, height: int, aspect: str) -> tuple[int, int]:
    """The frame of the format, keeping the take's long side; even numbers for the encoder."""

    wanted = ratio(aspect)
    if not wanted or abs(wanted - width / height) < 0.01:
        return width // 2 * 2, height // 2 * 2
    long_side = max(width, height)
    if wanted >= 1:
        out_width, out_height = long_side, long_side / wanted
    else:
        out_width, out_height = long_side * wanted, long_side
    return int(round(out_width / 2)) * 2, int(round(out_height / 2)) * 2


def reframe_filter(width: int, height: int, target: tuple[int, int], x: float = 0.5, y: float = 0.5) -> str:
    """Crop the take to the target's proportion around (x, y), then scale to the target."""

    wanted = target[0] / target[1]
    if width / height > wanted:  # the take is wider: a window of its full height
        crop_width, crop_height = int(height * wanted) // 2 * 2, height
    else:
        crop_width, crop_height = width, int(width / wanted) // 2 * 2
    left = int(max(0, min(width - crop_width, width * x - crop_width / 2)))
    top = int(max(0, min(height - crop_height, height * y - crop_height / 2)))
    return f"crop={crop_width}:{crop_height}:{left}:{top},scale={target[0]}:{target[1]},setsar=1"


def spoken_words(media: Path, pattern: str) -> list[tuple[float, float, str]]:
    """The words of a take's sidecar with their text, when it has text: (start, end, word)."""

    sidecar = media.parent / pattern.format(stem=media.stem, name=media.name)
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    words = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and "start" in item and "end" in item and str(item.get("word") or item.get("text")
                                                                                  or "").strip():
            words.append((float(item["start"]), float(item["end"]), str(item.get("word") or item["text"]).strip()))
    return sorted(words)


def groups(words: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    """Words in short captions: at most CAPTION_WORDS, broken at a pause."""

    captions: list[tuple[float, float, str]] = []
    current: list[tuple[float, float, str]] = []
    for word in words:
        if current and (len(current) >= CAPTION_WORDS or word[0] - current[-1][1] > CAPTION_PAUSE):
            captions.append((current[0][0], current[-1][1], " ".join(item[2] for item in current)))
            current = []
        current.append(word)
    if current:
        captions.append((current[0][0], current[-1][1], " ".join(item[2] for item in current)))
    return [(start, max(end, start + CAPTION_MIN_SECONDS), text) for start, end, text in captions]


def spread(text: str, start: float, end: float) -> list[tuple[float, float, str]]:
    """A line without word timings, spread evenly over its speech in groups."""

    words = text.split()
    if not words or end <= start:
        return []
    step = (end - start) / len(words)
    return groups([(start + index * step, start + (index + 1) * step, word) for index, word in enumerate(words)])


def _ass_time(seconds: float) -> str:
    hours, rest = divmod(max(0.0, seconds), 3600)
    minutes, rest = divmod(rest, 60)
    return f"{int(hours)}:{int(minutes):02d}:{rest:05.2f}"


def write_ass(captions: list[tuple[float, float, str]], size: tuple[int, int], path: Path) -> Path:
    """Captions as an ASS file: bold, outlined, in the lower third, sized to the frame."""

    width, height = size
    font = max(18, round(min(width, height) * 0.075))
    margin = round(height * (0.2 if height > width else 0.08))
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV",
        f"Style: Caption,DejaVu Sans,{font},&H00FFFFFF,&H00000000,&H64000000,-1,1,{max(2, font // 12)},0,2,"
        f"{round(width * 0.06)},{round(width * 0.06)},{margin}", "",
        "[Events]", "Format: Layer, Start, End, Style, Text",
    ]
    for start, end, text in captions:
        clean = text.replace("\n", " ").replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,{clean}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def subtitles_filter(path: Path) -> str:
    """The FFmpeg filter that burns an ASS file, its path escaped for the filtergraph."""

    escaped = str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return f"subtitles='{escaped}'"


def end_card_missing(style: dict[str, Any], shots: list[dict[str, Any]]) -> bool:
    form = style.get("format") or {}
    kept = [shot for shot in shots if not shot.get("out_of_cut")]
    return bool(form.get("end_card") and kept and not kept[-1].get("title"))


def renditions(value: Any, styles: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """`deliver: [viral-vertical, {aspect: "1:1", captions: true}]` as renditions {id, name, aspect, captions}.

    A name is a format style (or a name it is known by); a mapping says its
    aspect, and may name itself (`name:`).
    """

    from .styles import lookup

    found: list[dict[str, Any]] = []
    problems: list[str] = []
    for entry in value if isinstance(value, list) else [value] if value else []:
        if isinstance(entry, dict):
            aspect = str(entry.get("aspect") or "")
            if not ratio(aspect):
                problems.append(f"delivers a rendition with the aspect {aspect!r}, which is not width:height")
                continue
            name = str(entry.get("name") or aspect)
            found.append({"id": _slug(name), "name": name, "aspect": aspect, "captions": bool(entry.get("captions"))})
            continue
        item = styles.get(str(entry)) or lookup(styles, str(entry))
        if item is None or item["axis"] != "format":
            problems.append(f"delivers {entry!r}, which is not a format in the style catalog")
            continue
        found.append({"id": item["id"], "name": item["name"], "aspect": item["format"]["aspect"] or "16:9",
                      "captions": item["format"]["captions"]})
    ids = [item["id"] for item in found]
    for duplicate in sorted({item for item in ids if ids.count(item) > 1}):
        problems.append(f"delivers {duplicate!r} twice")
    return found, problems


def _slug(text: str) -> str:
    import re

    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower().replace(":", "x"))).strip("-") or "rendition"
