from __future__ import annotations

import hashlib
import os
import tomllib
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from .classify import TEXT_EXTENSIONS, classify
from .model import ProjectItem


IGNORED_DIRECTORIES = {".git", ".hg", ".svn", "__pycache__"}
MAX_TEXT_BYTES = 2 * 1024 * 1024


def project_id_for(root: Path) -> str:
    root = root.expanduser().resolve()
    manifest = root / "project.toml"
    if manifest.is_file():
        try:
            with manifest.open("rb") as handle:
                project_id = tomllib.load(handle).get("id")
        except (OSError, tomllib.TOMLDecodeError):
            project_id = None
        if project_id not in (None, ""):
            return str(project_id)

    normalized = str(root).encode("utf-8")
    return "prj_" + hashlib.blake2s(normalized, digest_size=8).hexdigest()


def item_id_for(project_id: str, relative_path: str) -> str:
    payload = f"{project_id}\0{relative_path}".encode("utf-8")
    return "itm_" + hashlib.blake2s(payload, digest_size=10).hexdigest()


def detect_adapter(root: Path) -> str:
    if (root / "project.toml").is_file():
        return "cine-toaster"
    return "generic"


def _read_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return None
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def scan_project(root: Path) -> Iterator[ProjectItem]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Project directory does not exist: {root}")

    project_id = project_id_for(root)
    root_stat = root.stat()
    yield ProjectItem(
        id=project_id,
        parent_id=None,
        kind="project",
        name=root.name,
        relative_path="",
        is_directory=True,
        media_type=None,
        extension=None,
        size=0,
        modified_ns=root_stat.st_mtime_ns,
    )

    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in IGNORED_DIRECTORIES
        )
        files.sort()
        current_path = Path(current)

        for name in directories:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            parent_relative = PurePosixPath(relative).parent.as_posix()
            if parent_relative == ".":
                parent_relative = ""
            try:
                stat = path.lstat()
            except OSError:
                continue
            kind, media_type = classify(relative, is_directory=True)
            yield ProjectItem(
                id=item_id_for(project_id, relative),
                parent_id=project_id if not parent_relative else item_id_for(project_id, parent_relative),
                kind=kind,
                name=name,
                relative_path=relative,
                is_directory=True,
                media_type=media_type,
                extension=None,
                size=0,
                modified_ns=stat.st_mtime_ns,
            )

        for name in files:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            parent_relative = PurePosixPath(relative).parent.as_posix()
            if parent_relative == ".":
                parent_relative = ""
            try:
                stat = path.lstat()
            except OSError:
                continue
            kind, media_type = classify(relative, is_directory=False)
            yield ProjectItem(
                id=item_id_for(project_id, relative),
                parent_id=project_id if not parent_relative else item_id_for(project_id, parent_relative),
                kind=kind,
                name=name,
                relative_path=relative,
                is_directory=False,
                media_type=media_type,
                extension=path.suffix.lower() or None,
                size=stat.st_size,
                modified_ns=stat.st_mtime_ns,
                text_content=_read_text(path),
            )
