"""A new production, from nothing or from a screenplay (CT-0098).

The production is written once, in the native format (ADR 0010), and is then
the person's: nothing here runs again over it. Given a screenplay, each of its
scenes gets a breakdown linked by heading (SPEC-0006) and no shots -- the
start of phase 1, where the screenplay and the storyboard are fitted together.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ValidationError
from .vocabulary import PROJECT_FILE

SCRIPT_PATH = "story/screenplay.fountain"
# The guide travels in the wheel beside the code; a checkout reads it from docs/.
GUIDE_PATHS = (Path(__file__).with_name("guide") / "making-a-film.md",
               Path(__file__).parents[2] / "docs" / "making-a-film.md")


@dataclass(slots=True)
class Created:
    root: Path
    project_id: str
    scenes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def guide_text() -> str:
    """docs/making-a-film.md: how a film is made with Cine Toaster, for a person or a production agent."""

    path = next((path for path in GUIDE_PATHS if path.is_file()), None)
    if path is None:
        raise ValidationError("The guide is not installed (docs/making-a-film.md)")
    return path.read_text(encoding="utf-8")


def slug(text: str, fallback: str = "film") -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:40] or fallback


def _quoted(text: str) -> str:
    # JSON strings are YAML strings: a heading's colons and quotes stay text.
    return json.dumps(text, ensure_ascii=False)


def _screenplay_text(source: Path | None, title: str, notes: list[str]) -> str:
    if source is None:
        return f"Title: {title}\n\n"
    if source.suffix.lower() == ".fdx":
        from .fdx import import_fdx

        try:
            conversion = import_fdx(source.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValidationError(f"{source}: {error}") from error
        notes.append("Final Draft converted to Fountain: " + conversion.report().replace("\n", "; "))
        return conversion.text
    return source.read_text(encoding="utf-8")


def _manifest(project_id: str, title: str, logline: str) -> str:
    lines = [
        "# A Cine Toaster production: the runtime reads these files directly (docs/making-a-film.md).",
        "schema_version: 1",
        f"id: {project_id}",
        f"title: {_quoted(title)}",
    ]
    if logline:
        lines.append(f"logline: {_quoted(logline)}")
    lines += [
        "",
        "paths:",
        "  scenes: scenes",
        f"  script: {SCRIPT_PATH}",
        "",
        "# Sequences are ordered runs of scenes, assembled and reviewed as one (ADR 0008).",
        "sequences: []",
        "",
    ]
    return "\n".join(lines)


def _breakdown(scene_id: str, order: int, heading: str, occurrence: int) -> str:
    lines = [
        f"scene: {scene_id}",
        f"order: {order}",
        f"title: {_quoted(heading)}",
        "",
        "# The screenplay scene this breakdown films (SPEC-0006); the words live only in the screenplay.",
        "script:",
        f"  heading: {_quoted(heading)}",
    ]
    if occurrence > 1:
        lines.append(f"  occurrence: {occurrence}")
    lines += [
        "",
        "# The storyboard: one entry per shot, each saying which part of the scene it covers.",
        "# `toast script link` suggests the covers once shots exist.",
        "shots: []",
        "",
    ]
    return "\n".join(lines)


def create_production(root: Path, title: str, *, screenplay: Path | None = None, project_id: str = "",
                      logline: str = "") -> Created:
    """Write a new production at root, which must not exist or be empty."""

    title = title.strip()
    if not title:
        raise ValidationError("A production needs a title")
    root = root.expanduser().resolve()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValidationError(f"{root} exists and is not empty; a new production is never written over one")
    if screenplay is not None and not screenplay.is_file():
        raise ValidationError(f"No screenplay at {screenplay}")
    project_id = slug(project_id or title)

    created = Created(root=root, project_id=project_id)
    text = _screenplay_text(screenplay, title, created.notes)

    from .screenplay import parse

    parsed = parse(text)
    root.mkdir(parents=True, exist_ok=True)
    (root / PROJECT_FILE).write_text(_manifest(project_id, title, logline.strip()), encoding="utf-8")
    script = root / SCRIPT_PATH
    script.parent.mkdir(parents=True)
    script.write_text(text, encoding="utf-8")
    (root / "scenes").mkdir()
    for index, scene in enumerate(parsed.scenes, start=1):
        order = index * 10
        scene_id = f"SC-{order:03d}"
        folder = root / "scenes" / f"{order:03d}-{slug(scene.heading, 'scene')}"
        folder.mkdir()
        (folder / "scene.yaml").write_text(_breakdown(scene_id, order, scene.heading, scene.occurrence),
                                           encoding="utf-8")
        created.scenes.append(scene_id)
    return created
