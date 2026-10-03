"""Where a production's recorded sound and music come from (CT-0048).

SINGULAR's two sources, and one for music:

- **Freesound** (freesound.org): Creative Commons 0 only -- no credit owed,
  commercial use free. The API key (`FREESOUND_API_KEY`) downloads the HQ
  preview (MP3), not the original: enough to cut with; the item says
  `preview-hq`.
- **Sonniss GDC** bundle: royalty-free, commercial use, no credit, not to be
  redistributed. Read from an **unofficial** archive.org mirror, so each item
  is `provisional`: before release, the official pack
  (https://sonniss.com/gameaudiogdc) replaces each file with the one of the
  same name. A scene that uses one is told so.
- **Openverse** (openverse.org): music from Jamendo, ccMixter, Wikimedia
  and others, restricted to licences a film may use without asking: CC0,
  public domain and CC BY (credit owed, kept in the item).

Fetching writes `sounds/<id>/sound.toml` beside the file, with its
provenance, licence, credit, page and status: the production's sound
catalog layer. Searching writes nothing. Credentials are read from the
environment and never printed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .errors import ValidationError

AGENT = "cine-toaster-sounds/1.0"
SONNISS_MIRROR = "sonniss-gdc-2023-game-audio-bundle-normalized"
SONNISS_LICENCE = "Sonniss GDC royalty-free (commercial use, no credit; do not redistribute)"
OPENVERSE_LICENCES = ("cc0", "pdm", "by")
CATEGORIES = ("ambience", "effect", "foley", "music")


def _get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _download(url: str, destination: Path, md5: str | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    digest = hashlib.md5()
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=300) as response, partial.open("wb") as handle:
        while block := response.read(1 << 20):
            handle.write(block)
            digest.update(block)
    if md5 and digest.hexdigest() != md5:
        partial.unlink()
        raise ValidationError(f"The download of {destination.name} does not match its checksum")
    partial.replace(destination)


def slug(text: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:48] or "sound"


def _toml(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml(item) for item in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)


def write_item(root: Path, sound_id: str, *, name: str, category: str, says: str, file: str,
               provenance: str, licence: str, url: str = "", credit: str = "", status: str = "",
               use_when: list[str] | None = None, replace: bool = False) -> Path:
    """`sounds/<id>/sound.toml` for a recording: the production's catalog layer."""

    if category not in CATEGORIES:
        raise ValidationError(f"A sound's category is one of {', '.join(CATEGORIES)}, not {category!r}")
    folder = Path(root) / "sounds" / sound_id
    manifest = folder / "sound.toml"
    if manifest.exists() and not replace:
        raise ValidationError(f"The production already has a sound {sound_id!r} (sounds/{sound_id}); choose another id")
    folder.mkdir(parents=True, exist_ok=True)
    lines = ["schema_version = 1", f"id = {_toml(sound_id)}", f"name = {_toml(name)}", f"category = {_toml(category)}",
             f"says = {_toml(says)}", f"use_when = {_toml(use_when or [])}", "", "[source]", f"file = {_toml(file)}",
             f"provenance = {_toml(provenance)}", f"licence = {_toml(licence)}"]
    for key, value in (("credit", credit), ("url", url), ("status", status)):
        if value:
            lines.append(f"{key} = {_toml(value)}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


# --- Freesound ----------------------------------------------------------------------


def _freesound_key() -> str:
    key = os.environ.get("FREESOUND_API_KEY", "").strip()
    if not key:
        raise ValidationError("FREESOUND_API_KEY is not set (put it in the .env given with --env-file)")
    return key


def freesound_search(terms: str, count: int = 10) -> list[dict[str, Any]]:
    """Creative Commons 0 sounds matching the terms, best first."""

    query = urllib.parse.urlencode({
        "query": terms, "filter": 'license:"Creative Commons 0"', "sort": "score", "page_size": count,
        "fields": "id,name,duration,username,avg_rating,num_downloads,url", "token": _freesound_key()})
    return [{"source": "freesound", "id": str(item["id"]), "name": item["name"], "seconds": item["duration"],
             "by": item["username"], "url": item["url"], "licence": "CC0 1.0"}
            for item in _get_json(f"https://freesound.org/apiv2/search/text/?{query}")["results"]]


def freesound_fetch(root: Path, sound: str, *, sound_id: str = "", category: str = "effect",
                    says: str = "") -> Path:
    token = _freesound_key()
    data = _get_json(f"https://freesound.org/apiv2/sounds/{int(sound)}/?fields=id,name,license,previews,url,username"
                     f"&token={token}")
    if "publicdomain/zero" not in data["license"]:
        raise ValidationError(f"Freesound {sound} is not CC0 ({data['license']}); refused")
    sound_id = sound_id or slug(Path(data["name"]).stem)
    folder = Path(root) / "sounds" / sound_id
    if (folder / "sound.toml").exists():
        raise ValidationError(f"The production already has a sound {sound_id!r}; choose another id")
    file = f"freesound-{data['id']}.mp3"
    _download(data["previews"]["preview-hq-mp3"], folder / file)
    return write_item(root, sound_id, name=data["name"], category=category, says=says or data["name"], file=file,
                      provenance=f"Freesound, by {data['username']}", licence="CC0 1.0", url=data["url"],
                      status="preview-hq")


# --- Sonniss (archive.org mirror) ---------------------------------------------------


def _sonniss_files() -> list[dict[str, Any]]:
    from .jobs import state_root

    cache = state_root() / "sound-sources" / f"{SONNISS_MIRROR}.json"
    if not cache.is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        meta = _get_json(f"https://archive.org/metadata/{SONNISS_MIRROR}")
        cache.write_text(json.dumps([item for item in meta["files"] if item.get("source") == "original"
                                     and item["name"].lower().endswith((".wav", ".flac", ".mp3", ".ogg"))]),
                         encoding="utf-8")
    return json.loads(cache.read_text(encoding="utf-8"))


def sonniss_search(terms: str, count: int = 20) -> list[dict[str, Any]]:
    """Files of the mirrored bundle whose path holds every term (pack and file names describe the sound)."""

    words = [word.lower() for word in terms.split()]
    found = [item for item in _sonniss_files() if all(word in item["name"].lower() for word in words)]
    return [{"source": "sonniss", "id": item["name"], "name": Path(item["name"]).stem,
             "pack": item["name"].split("/")[0], "megabytes": round(int(item.get("size") or 0) / 1e6, 1),
             "licence": SONNISS_LICENCE, "status": "provisional"} for item in found[:count]]


def sonniss_fetch(root: Path, name: str, *, sound_id: str = "", category: str = "effect", says: str = "") -> Path:
    matches = [item for item in _sonniss_files() if item["name"] == name] or \
              [item for item in _sonniss_files() if item["name"].startswith(name)]
    if len(matches) != 1:
        raise ValidationError(f"{len(matches)} files of the Sonniss mirror match {name!r}; name exactly one")
    item = matches[0]
    sound_id = sound_id or slug(Path(item["name"]).stem)
    folder = Path(root) / "sounds" / sound_id
    if (folder / "sound.toml").exists():
        raise ValidationError(f"The production already has a sound {sound_id!r}; choose another id")
    file = Path(item["name"]).name
    url = f"https://archive.org/download/{SONNISS_MIRROR}/{urllib.parse.quote(item['name'])}"
    _download(url, folder / file, item.get("md5"))
    return write_item(root, sound_id, name=Path(item["name"]).stem, category=category, says=says or item["name"],
                      file=file, provenance="Sonniss GDC 2023 (archive.org mirror, unofficial)",
                      licence=SONNISS_LICENCE, url=url, status="provisional")


# --- Openverse (music) --------------------------------------------------------------


def _licence_name(item: dict[str, Any]) -> str:
    code = str(item.get("license") or "")
    if code == "pdm":
        return "Public Domain Mark"
    return f"CC {code.upper()} {item.get('license_version') or ''}".strip()


def openverse_search(terms: str, count: int = 10, music: bool = True) -> list[dict[str, Any]]:
    """Audio a film may use without asking (CC0, public domain, CC BY), music by default."""

    query = {"q": terms, "license": ",".join(OPENVERSE_LICENCES), "page_size": count}
    if music:
        query["category"] = "music"
    data = _get_json(f"https://api.openverse.org/v1/audio/?{urllib.parse.urlencode(query)}")
    return [{"source": "openverse", "id": item["id"], "name": item.get("title") or "",
             "by": item.get("creator") or "", "from": item.get("source") or "",
             "seconds": round((item.get("duration") or 0) / 1000, 1), "licence": _licence_name(item),
             "url": item.get("foreign_landing_url") or ""} for item in data.get("results") or []]


def openverse_fetch(root: Path, audio: str, *, sound_id: str = "", category: str = "music", says: str = "") -> Path:
    item = _get_json(f"https://api.openverse.org/v1/audio/{urllib.parse.quote(audio)}/")
    if item.get("license") not in OPENVERSE_LICENCES:
        raise ValidationError(f"Openverse {audio} is licensed {item.get('license')!r}; only "
                              f"{', '.join(OPENVERSE_LICENCES)} are fetched")
    sound_id = sound_id or slug(item.get("title") or audio)
    folder = Path(root) / "sounds" / sound_id
    if (folder / "sound.toml").exists():
        raise ValidationError(f"The production already has a sound {sound_id!r}; choose another id")
    extension = {"mp32": "mp3", "mp3": "mp3", "ogg": "ogg", "wav": "wav", "flac": "flac"}.get(
        str(item.get("filetype") or "mp3"), "mp3")
    file = f"openverse-{slug(item.get('title') or audio)}.{extension}"
    _download(item["url"], folder / file)
    credit = "" if item.get("license") in ("cc0", "pdm") else (item.get("attribution") or
                                                                 f"{item.get('title')} by {item.get('creator')}")
    return write_item(root, sound_id, name=item.get("title") or sound_id, category=category,
                      says=says or f"{item.get('title')} -- {item.get('creator')}", file=file,
                      provenance=f"Openverse ({item.get('source')}), by {item.get('creator')}",
                      licence=_licence_name(item), url=item.get("foreign_landing_url") or "", credit=credit)


# --- a library already on disk ------------------------------------------------------

#: A library's manifest columns, in English, and the names SINGULAR's MANIFESTO.csv uses.
COLUMNS = {"file": ("file", "arquivo"), "provenance": ("provenance", "origem"), "licence": ("licence", "licenca"),
           "url": ("url",), "status": ("status", "situacao"), "use": ("use", "uso")}
STATUS = {"provisorio": "provisional", "previa-hq": "preview-hq"}
#: A first guess of the category from the file and its use (the library's own words; the author corrects it).
AMBIENCE = re.compile(r"(^|[^a-z])(amb|ambience|ambiance|room ?tone|tom de sala|drone|wind|vento|rain|hum|zumbido|atmos)",
                      re.I)
MUSIC = re.compile(r"(^|[^a-z])(pad|music|score|theme|chimes)", re.I)


def _where(path: Path, folder: Path) -> str:
    """A library file as the manifest names it: relative when it is inside the production, so the film can move."""

    root = folder.parent.parent.resolve()
    if path.resolve().is_relative_to(root):
        return os.path.relpath(path.resolve(), folder.resolve())
    return str(path)


def import_library(root: Path, folder: Path, *, prefix: str = "") -> list[str]:
    """Register a library already on disk, described by its manifest CSV, as the production's sounds.

    The files stay where they are; each gets `sounds/<id>/sound.toml`
    pointing at it with its provenance, licence and status. Existing ids
    are left alone.
    """

    folder = Path(folder).expanduser().resolve()
    manifest = next((path for path in (folder / "manifest.csv", folder / "MANIFESTO.csv") if path.is_file()), None)
    if manifest is None:
        raise ValidationError(f"{folder} has no manifest.csv describing its files")
    made = []
    with manifest.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            value = {key: next((row[name] for name in names if row.get(name)), "") for key, names in COLUMNS.items()}
            path = folder / value["file"]
            if not value["file"] or not path.is_file():
                continue
            use = value["use"].strip()
            sound_id = prefix + slug(use or path.stem)
            if (Path(root) / "sounds" / sound_id / "sound.toml").exists():
                continue
            described = path.name + " " + use
            category = "music" if MUSIC.search(described) else "ambience" if AMBIENCE.search(described) else "effect"
            write_item(root, sound_id, name=use or path.stem, category=category, says=use or path.stem,
                       file=_where(path, Path(root) / "sounds" / sound_id), provenance=value["provenance"],
                       licence=value["licence"],
                       url=value["url"], status=STATUS.get(value["status"], value["status"]),
                       use_when=[use] if use else [])
            made.append(sound_id)
    return made
