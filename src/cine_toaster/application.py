from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from .project import load_production


class ProjectSourceError(ValueError):
    """Base error raised while resolving an application project source."""


class UnsupportedProjectSourceError(ProjectSourceError):
    """Raised when no source adapter supports a locator scheme."""


class ProjectIdentityConflictError(ProjectSourceError):
    """Raised when one project id is opened from two different locations."""

    def __init__(
        self,
        project_id: str,
        existing: ProjectLocator,
        incoming: ProjectLocator,
    ) -> None:
        self.project_id = project_id
        self.existing = existing
        self.incoming = incoming
        super().__init__(
            f"Project id {project_id!r} is already open from {existing.uri}; "
            f"cannot also open {incoming.uri}"
        )


@dataclass(frozen=True, slots=True)
class ProjectLocator:
    """Infrastructure address for a project source, not project identity."""

    scheme: str
    uri: str

    @classmethod
    def from_path(cls, path: Path | str) -> ProjectLocator:
        root = Path(path).expanduser().resolve()
        return cls(scheme="file", uri=root.as_uri())

    def local_path(self) -> Path:
        parsed = urlparse(self.uri)
        if self.scheme != "file" or parsed.scheme != "file":
            raise UnsupportedProjectSourceError(
                f"Project locator is not a local file source: {self.uri}"
            )
        if parsed.netloc not in ("", "localhost"):
            raise UnsupportedProjectSourceError(
                f"Remote file hosts are not supported: {self.uri}"
            )
        return Path(unquote(parsed.path)).resolve()


@dataclass(frozen=True, slots=True)
class MaterializedProject:
    """A filesystem project ready for use by the Project Core."""

    workspace_id: str
    project_id: str
    title: str
    locator: ProjectLocator
    local_root: Path
    source_revision: str | None
    sync_state: str
    read_only: bool
    materialized_at: str


class LocalProjectSource:
    """Open an external local directory without copying it into the app."""

    scheme = "file"

    def open(self, locator: ProjectLocator) -> MaterializedProject:
        root = locator.local_path()
        if not root.is_dir():
            raise NotADirectoryError(f"Project directory does not exist: {root}")

        production = load_production(root)
        workspace_key = hashlib.blake2s(locator.uri.encode("utf-8"), digest_size=10)
        return MaterializedProject(
            workspace_id="ws_" + workspace_key.hexdigest(),
            project_id=production["id"],
            title=production["title"],
            locator=locator,
            local_root=root,
            source_revision=None,
            sync_state="clean",
            read_only=not os.access(root, os.W_OK),
            materialized_at=datetime.now(UTC).isoformat(),
        )


class ProjectManager:
    """Register independently located projects for one application runtime."""

    def __init__(self) -> None:
        self._sources = {LocalProjectSource.scheme: LocalProjectSource()}
        self._projects: dict[str, MaterializedProject] = {}

    def open_project(
        self,
        project: Path | str | ProjectLocator,
    ) -> MaterializedProject:
        locator = (
            project if isinstance(project, ProjectLocator) else ProjectLocator.from_path(project)
        )
        source = self._sources.get(locator.scheme)
        if source is None:
            raise UnsupportedProjectSourceError(
                f"Unsupported project source scheme: {locator.scheme}"
            )

        materialized = source.open(locator)
        existing = self._projects.get(materialized.project_id)
        if existing is not None:
            if existing.locator == materialized.locator:
                return existing
            raise ProjectIdentityConflictError(
                materialized.project_id,
                existing.locator,
                materialized.locator,
            )

        self._projects[materialized.project_id] = materialized
        return materialized

    def get(self, project_id: str) -> MaterializedProject:
        try:
            return self._projects[project_id]
        except KeyError as error:
            raise KeyError(f"Project is not open: {project_id}") from error

    def list_projects(self) -> tuple[MaterializedProject, ...]:
        return tuple(self._projects.values())

    def close_project(self, project_id: str) -> MaterializedProject:
        try:
            return self._projects.pop(project_id)
        except KeyError as error:
            raise KeyError(f"Project is not open: {project_id}") from error
