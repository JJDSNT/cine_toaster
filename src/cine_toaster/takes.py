from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# A shot's alternatives are files, discovered by reading the work directory.
# Nothing declares them, because a declaration is a second copy of a truth the
# filesystem already holds, and a second copy drifts.
#
#   trabalho/c04.mp4                        the clip currently in the cut
#   trabalho/c04-pov.mp4                    another candidate
#   trabalho/_tomadas/c04-t11.mp4           a take kept for comparison
#   trabalho/_descartados/c04-lado-errado.mp4   rejected, and why
#
# The reason a take was rejected lives in its filename. That is where a
# production naturally writes it, so that is where this reads it from.

WORK_DIRECTORY = "trabalho"
TAKES_DIRECTORY = "_tomadas"
REJECTED_DIRECTORY = "_descartados"
MEDIA_SUFFIXES = (".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp")

CURRENT_TAKE_ID = "CUT"


@dataclass(frozen=True, slots=True)
class DiscoveredTake:
    id: str
    label: str
    status: str
    media: str
    note: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "media": self.media,
            "poster": "",
            "note": self.note,
            "duration_seconds": 0.0,
            "cost_usd": 0.0,
            "created_at": "",
            "provenance": {},
            "selectable": self.status != "rejected",
        }


def shot_key(number: Any) -> str:
    """One spelling for a shot number.

    A breakdown numbers a shot `2`, `3a`, `18b`; its files are named `c02`,
    `c3a`, `c18b`. A leading zero must never decide whether a choice is honoured.
    """

    text = str(number).strip().upper().removeprefix("P")
    match = re.fullmatch(r"0*(\d+)([A-Z]*)", text)
    return (match.group(1) + match.group(2).lower()) if match else text.lower()


def _readable(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().capitalize()


def _take_id(slug: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", slug).strip("-").upper() or "TAKE"


def _candidates(number: Any) -> set[str]:
    key = shot_key(number)
    match = re.fullmatch(r"(\d+)([a-z]*)", key)
    if match is None:
        return {f"c{key}"}
    digits, suffix = match.groups()
    return {f"c{int(digits):02d}{suffix}", f"c{int(digits)}{suffix}"}


def discover(work_directory: Path, number: Any, *, relative_to: Path) -> list[DiscoveredTake]:
    """Every registered alternative for one shot, newest convention first."""

    if not work_directory.is_dir():
        return []

    stems = _candidates(number)
    found: dict[str, DiscoveredTake] = {}

    def register(path: Path, take_id: str, status: str, note: str) -> None:
        if take_id in found:
            return
        found[take_id] = DiscoveredTake(
            id=take_id,
            label=note or take_id,
            status=status,
            media=path.relative_to(relative_to).as_posix(),
            note=note,
        )

    for stem in sorted(stems):
        for suffix in MEDIA_SUFFIXES:
            path = work_directory / f"{stem}{suffix}"
            if path.is_file():
                register(path, CURRENT_TAKE_ID, "candidate", "In the assembled cut")
                break
        if CURRENT_TAKE_ID in found:
            break

    for directory, status in (
        (work_directory, "candidate"),
        (work_directory / TAKES_DIRECTORY, "candidate"),
        (work_directory / REJECTED_DIRECTORY, "rejected"),
    ):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.suffix.lower() not in MEDIA_SUFFIXES:
                continue
            for stem in stems:
                if path.stem.startswith(f"{stem}-"):
                    slug = path.stem[len(stem) + 1 :]
                    register(path, _take_id(slug), status, _readable(slug))
                    break

    return sorted(found.values(), key=lambda take: (take.status == "rejected", take.id))


def work_directory_for(scene_file: Path) -> Path:
    """Where a scene's generated media lives: beside its breakdown."""

    return scene_file.parent / WORK_DIRECTORY
