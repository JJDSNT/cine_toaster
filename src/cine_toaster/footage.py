"""Footage from outside: a shot says which stretch of which public file it is (CT-0066).

Open-licence footage is too large to keep with a production's records, and a
copy with no record of where it came from cannot be shown. So the breakdown
declares it, and the file is fetched:

    footage:
      url: https://images-assets.nasa.gov/video/.../launch~orig.mp4
      page: https://images.nasa.gov/details/...     # where a person reads about it
      in: 46            # seconds into the file
      duration: 8       # the shot's duration when left out
      licence: Public domain (NASA media usage guidelines)
      credit: NASA/Sam Lott

`toast footage fetch` reads each stretch from where the file is (only the
stretch, not the file), keeps it in the cache (disposable: deleting it loses
time, never the film), and brings it in as the shot's take through
`commands.add_take`, with its origin beside it. A shot that already has a
take is left alone.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .errors import ValidationError

REQUIRED = ("url", "licence")


def cache_directory() -> Path:
    configured = os.environ.get("XDG_CACHE_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".cache"
    return base / "cine-toaster" / "footage"


def read(raw: Any) -> dict[str, Any] | None:
    """A shot's `footage` as declared, with numbers as numbers; None when there is none."""

    if not isinstance(raw, dict) or not raw:
        return None

    def number(key: str) -> float:
        try:
            return float(raw.get(key) or 0)
        except (TypeError, ValueError):
            return -1.0

    return {"url": str(raw.get("url") or "").strip(), "page": str(raw.get("page") or "").strip(),
            "in": number("in"), "duration": number("duration"),
            "licence": str(raw.get("licence") or raw.get("license") or "").strip(),
            "credit": str(raw.get("credit") or "").strip()}


def problem(footage: dict[str, Any]) -> str:
    """Why this declaration cannot be fetched or shown, or ''."""

    missing = [key for key in REQUIRED if not footage.get(key)]
    if missing:
        return f"declares footage without its {' and '.join(missing)}"
    if not footage["url"].startswith(("https://", "http://", "file://")):
        return f"names footage at {footage['url']!r}, which is not an address to fetch"
    if footage["in"] < 0 or footage["duration"] < 0:
        return "gives its footage an `in` or a `duration` that is not a number of seconds"
    return ""


def address(url: str) -> str:
    """The URL as FFmpeg can open it: a local path for `file://`, else percent-encoded."""

    if url.startswith("file://"):
        return urllib.request.url2pathname(urllib.parse.urlparse(url).path)
    # NASA's own links carry spaces; a browser encodes them, and so must this.
    return urllib.parse.quote(url, safe=":/?&=~%+,;@#")


def stretch_path(url: str, start: float, seconds: float) -> Path:
    name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return cache_directory() / f"{name}-{start:g}-{seconds:g}.mp4"


def cut(url: str, start: float, seconds: float, destination: Path) -> Path:
    """The stretch as its own clip, read straight from where the file is.

    FFmpeg seeks in the remote file and reads only what the stretch needs, so
    eight seconds of a six-gigabyte file is not a six-gigabyte download. It is
    re-encoded, so it starts on a frame it can be cut from. A stretch already
    in the cache is not fetched again.
    """

    if destination.is_file() and destination.stat().st_size:
        return destination
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValidationError("FFmpeg is needed to fetch footage")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.stem + ".part.mp4")
    try:
        completed = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{seconds:.3f}", "-i", address(url),
             "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(partial)],
            capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired as error:
        partial.unlink(missing_ok=True)
        raise ValidationError(f"Fetching {url} took more than half an hour and was stopped") from error
    if completed.returncode != 0 or not partial.is_file() or not partial.stat().st_size:
        partial.unlink(missing_ok=True)
        raise ValidationError(f"Could not fetch {seconds:g} s at {start:g} s of {url}: "
                              f"{completed.stderr.strip()[-300:] or 'nothing was written'}")
    partial.replace(destination)
    return destination


@dataclass(frozen=True, slots=True)
class Fetched:
    scene: str
    shot: str
    status: str  # fetched | kept | refused
    detail: str = ""


def fetch(root: Path, production: dict[str, Any], actor: Any, *, scene_id: str | None = None,
          report: Callable[[str], None] | None = None, cutter=cut) -> list[Fetched]:
    """Bring every declared stretch in as its shot's take. A shot with a take is kept as it is."""

    from .commands import add_take

    root = Path(root).expanduser().resolve()
    results: list[Fetched] = []
    for scene in production["scenes"]:
        if scene_id and scene["id"] != scene_id:
            continue
        for shot in scene["shots"]:
            footage = shot.get("footage")
            if not footage:
                continue
            if shot.get("takes"):
                results.append(Fetched(scene["id"], shot["id"], "kept", "it has a take"))
                continue
            wrong = problem(footage)
            if wrong:
                results.append(Fetched(scene["id"], shot["id"], "refused", f"{shot['id']} {wrong}"))
                continue
            seconds = footage["duration"] or float(shot.get("duration_seconds") or 0)
            if not seconds:
                results.append(Fetched(scene["id"], shot["id"], "refused",
                                       f"{shot['id']} gives neither its footage nor itself a duration"))
                continue
            if report:
                report(f"{scene['id']} {shot['id']}: fetching {footage['url']}")
            try:
                stretch = cutter(footage["url"], footage["in"], seconds,
                                 stretch_path(footage["url"], footage["in"], seconds))
                made = add_take(root, scene_id=scene["id"], shot_id=shot["id"], source=stretch, actor=actor,
                                kind="archival", origin=footage["page"] or footage["url"],
                                licence=footage["licence"], credit=footage["credit"],
                                excerpt={"url": footage["url"], "in": footage["in"], "duration": seconds})
            except ValidationError as error:
                results.append(Fetched(scene["id"], shot["id"], "refused", str(error)))
                continue
            results.append(Fetched(scene["id"], shot["id"], "fetched", made.event["payload"]["media"]))
    return results
