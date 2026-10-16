"""A film's references: what inspired it or was tried for it, kept with where it came from (CT-0100).

A reference is not material of the film. It is a draft board, a probe, a
painting, a still from another film -- something the production looks at. Each
lives in `references/<id>/`: its files and a `reference.yaml` that says what it
is, who or what made it, from what prompt and earlier references, under which
licence, and each file's digest. The record is authored: `add` writes it once,
and nothing rewrites it.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .errors import ValidationError
from .new_production import slug

DIRECTORY = "references"
RECORD = "reference.yaml"
KINDS = ("generated", "found", "made")


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _problems(folder: Path, record: dict[str, Any], known: set[str]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []

    def note(code: str, severity: str, message: str) -> None:
        found.append({"code": code, "severity": severity, "message": message})

    files = record.get("files") or {}
    if not isinstance(files, dict) or not files:
        note("reference_files", "error", "reference.yaml lists no files (files: {name: sha256})")
        files = {}
    for name, expected in files.items():
        path = folder / str(name)
        if not path.is_file():
            note("reference_missing", "error", f"{name} is listed but not here")
        elif expected and digest(path) != str(expected):
            note("reference_changed", "error", f"{name} is not the file that was recorded (its digest changed)")
    listed = {str(name) for name in files}
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.name != RECORD and path.name not in listed:
            note("reference_unlisted", "warning", f"{path.name} is here but not in reference.yaml")
    kind = record.get("kind")
    if kind not in KINDS:
        note("reference_kind", "error", f"kind must be one of {', '.join(KINDS)}, not {kind!r}")
    if kind == "found" and not record.get("licence"):
        note("reference_licence", "warning", "found elsewhere with no licence recorded: usable only for looking")
    for parent in record.get("from") or []:
        if parent not in known:
            note("reference_from", "error", f"made from {parent!r}, which is not a reference of this film")
    return found


def load_references(root: Path) -> list[dict[str, Any]]:
    """Every reference of the production, with what its record says and what is wrong with it."""

    directory = Path(root).expanduser().resolve() / DIRECTORY
    if not directory.is_dir():
        return []
    folders = sorted(path for path in directory.iterdir() if path.is_dir())
    known = {folder.name for folder in folders}
    references = []
    for folder in folders:
        path = folder / RECORD
        if not path.is_file():
            references.append({"id": folder.name, "title": "", "findings": [
                {"code": "reference_record", "severity": "error", "message": f"no {RECORD} in {folder.name}"}]})
            continue
        try:
            record = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as error:
            references.append({"id": folder.name, "title": "", "findings": [
                {"code": "reference_record", "severity": "error", "message": f"{RECORD} does not parse: {error}"}]})
            continue
        references.append({**record, "id": folder.name, "path": str(folder),
                           "findings": _problems(folder, record, known)})
    return references


def add_reference(root: Path, files: list[Path], *, title: str, kind: str, made_by: str = "",
                  made_on: str = "", source: str = "", prompt: str = "", parents: list[str] | None = None,
                  licence: str = "", credit: str = "", notes: list[str] | None = None,
                  name: str = "", generation: dict[str, Any] | None = None) -> Path:
    """Copy files into a new reference with its record; never into one that exists."""

    root = Path(root).expanduser().resolve()
    if not title.strip():
        raise ValidationError("A reference needs a title: what it is")
    if kind not in KINDS:
        raise ValidationError(f"kind must be one of {', '.join(KINDS)}")
    if not files:
        raise ValidationError("A reference needs at least one file")
    for file in files:
        if not file.is_file():
            raise ValidationError(f"No file at {file}")
    if len({file.name for file in files}) != len(files):
        raise ValidationError("Two files share a name; a reference keeps each under its own")
    known = {item["id"] for item in load_references(root)}
    for parent in parents or []:
        if parent not in known:
            raise ValidationError(f"No reference {parent!r} in this film")
    made_on = made_on or date.today().isoformat()
    folder = root / DIRECTORY / f"{made_on}-{slug(name or title, 'reference')}"
    if folder.exists():
        raise ValidationError(f"{folder.name} exists; a reference is never written over (choose --name)")

    record: dict[str, Any] = {"title": title.strip(), "kind": kind}
    for key, value in (("made_by", made_by), ("made_on", made_on), ("source", source), ("prompt", prompt),
                       ("licence", licence), ("credit", credit)):
        if value:
            record[key] = value
    if parents:
        record["from"] = list(parents)
    if notes:
        record["notes"] = list(notes)
    if generation:
        record["generation"] = generation
    record["files"] = {file.name: digest(file) for file in files}

    folder.mkdir(parents=True)
    for file in files:
        shutil.copy2(file, folder / file.name)
    (folder / RECORD).write_text(
        "# A reference of this film (docs/making-a-film.md): what the production looks at, not its material.\n"
        + yaml.safe_dump(record, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
    return folder


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def image_providers() -> dict[str, Any]:
    """The providers that make a picture from a description and reference pictures (CT-0101)."""

    from .providers.codex_image import CodexImageProvider

    return {CodexImageProvider.id: CodexImageProvider}


def reference_images(root: Path, ids: list[str]) -> list[Path]:
    """The pictures of the named references, in order: what a generation is shown."""

    known = {item["id"]: item for item in load_references(root)}
    pictures: list[Path] = []
    for reference_id in ids:
        item = known.get(reference_id)
        if item is None:
            raise ValidationError(f"No reference {reference_id!r} in this film")
        folder = Path(item["path"])
        pictures += [folder / str(name) for name in (item.get("files") or {})
                     if Path(str(name)).suffix.lower() in IMAGE_SUFFIXES]
    return pictures


def generate_reference(root: Path, *, prompt: str, title: str, parents: list[str] | None = None,
                       provider: str = "codex-image", requested_by: str = "", notes: list[str] | None = None,
                       name: str = "", runner: Any = None, codex_home: Path | None = None) -> Path:
    """Make one picture from a description and the parents' pictures, and keep it as a reference."""

    import tempfile

    if not prompt.strip():
        raise ValidationError("A generation needs a description")
    makers = image_providers()
    if provider not in makers:
        raise ValidationError(f"No image provider {provider!r}; there is {', '.join(makers)}")
    parents = list(parents or [])
    pictures = reference_images(root, parents)
    maker = makers[provider](runner=runner, codex_home=codex_home)
    with tempfile.TemporaryDirectory(prefix="cine-toaster-reference-") as directory:
        output = Path(directory) / "image.png"
        generation = maker.generate(prompt=prompt, references=pictures, output=output, label=title)
        film = Path(root).expanduser().resolve()
        for item in generation["references"]:  # the film's own pictures, by their place in it
            if Path(item["file"]).is_relative_to(film):
                item["file"] = str(Path(item["file"]).relative_to(film))
        made_by = f"{generation['made_with']} ({provider})" + (f", asked by {requested_by}" if requested_by else "")
        return add_reference(root, [output], title=title, kind="generated", made_by=made_by,
                             source=generation.get("codex_file", ""), prompt=prompt, parents=parents,
                             notes=notes, name=name, generation=generation)

