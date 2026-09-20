from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .model import ProjectItem, ProjectSummary
from .scanner import detect_adapter, project_id_for, scan_project


SCHEMA_VERSION = 1


def cache_root() -> Path:
    configured = os.environ.get("XDG_CACHE_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".cache"
    return base / "cine-toaster" / "projects"


def workspace_key(root: Path) -> str:
    """Stable cache key for one project location.

    Operational state is keyed by location rather than project id so a cache
    can be built before any manifest is parsed.
    """

    resolved = str(root.expanduser().resolve()).encode("utf-8")
    return hashlib.blake2s(resolved, digest_size=10).hexdigest()


def workspace_cache_dir(root: Path) -> Path:
    return cache_root() / workspace_key(root)


def index_path_for(root: Path) -> Path:
    return workspace_cache_dir(root) / "index.sqlite"


def _connect(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def build_index(root: Path) -> ProjectSummary:
    root = root.expanduser().resolve()
    target = index_path_for(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.tmp-{os.getpid()}")
    if temporary.exists():
        temporary.unlink()

    indexed_at = datetime.now(UTC).isoformat()
    project_id = project_id_for(root)
    adapter = detect_adapter(root)
    item_count = file_count = directory_count = total_bytes = 0

    connection = _connect(temporary)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode = OFF;
            PRAGMA synchronous = OFF;
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE items (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                relative_path TEXT NOT NULL UNIQUE,
                is_directory INTEGER NOT NULL,
                media_type TEXT,
                extension TEXT,
                size INTEGER NOT NULL,
                modified_ns INTEGER NOT NULL,
                text_content TEXT
            );
            CREATE INDEX idx_items_parent ON items(parent_id, is_directory DESC, name COLLATE NOCASE);
            CREATE INDEX idx_items_kind ON items(kind);
            CREATE INDEX idx_items_media_type ON items(media_type);
            """
        )
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [
                ("schema_version", str(SCHEMA_VERSION)),
                ("project_id", project_id),
                ("project_name", root.name),
                ("project_root", str(root)),
                ("adapter", adapter),
                ("indexed_at", indexed_at),
            ],
        )

        batch: list[tuple[object, ...]] = []
        for item in scan_project(root):
            item_count += 1
            if item.is_directory:
                directory_count += 1
            else:
                file_count += 1
                total_bytes += item.size
            batch.append(
                (
                    item.id,
                    item.parent_id,
                    item.kind,
                    item.name,
                    item.relative_path,
                    int(item.is_directory),
                    item.media_type,
                    item.extension,
                    item.size,
                    item.modified_ns,
                    item.text_content,
                )
            )
            if len(batch) >= 500:
                connection.executemany(
                    "INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", batch
                )
                batch.clear()
        if batch:
            connection.executemany(
                "INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", batch
            )
        connection.commit()
    except Exception:
        connection.close()
        temporary.unlink(missing_ok=True)
        raise
    else:
        connection.close()
        os.replace(temporary, target)

    return ProjectSummary(
        id=project_id,
        name=root.name,
        root=str(root),
        adapter=adapter,
        indexed_at=indexed_at,
        item_count=item_count,
        file_count=file_count,
        directory_count=directory_count,
        total_bytes=total_bytes,
    )


def _item_from_row(row: sqlite3.Row) -> ProjectItem:
    return ProjectItem(
        id=row["id"],
        parent_id=row["parent_id"],
        kind=row["kind"],
        name=row["name"],
        relative_path=row["relative_path"],
        is_directory=bool(row["is_directory"]),
        media_type=row["media_type"],
        extension=row["extension"],
        size=row["size"],
        modified_ns=row["modified_ns"],
        text_content=row["text_content"],
    )


class ProjectIndex:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.path = index_path_for(self.root)
        if not self.path.exists():
            raise FileNotFoundError(f"Project is not indexed: {self.root}")

    def _connection(self) -> sqlite3.Connection:
        return _connect(self.path, readonly=True)

    def metadata(self) -> dict[str, str]:
        with self._connection() as connection:
            return {
                row["key"]: row["value"]
                for row in connection.execute("SELECT key, value FROM metadata")
            }

    def summary(self) -> ProjectSummary:
        metadata = self.metadata()
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS item_count,
                       SUM(CASE WHEN is_directory = 0 THEN 1 ELSE 0 END) AS file_count,
                       SUM(CASE WHEN is_directory = 1 THEN 1 ELSE 0 END) AS directory_count,
                       SUM(CASE WHEN is_directory = 0 THEN size ELSE 0 END) AS total_bytes
                FROM items
                """
            ).fetchone()
        return ProjectSummary(
            id=metadata["project_id"],
            name=metadata["project_name"],
            root=metadata["project_root"],
            adapter=metadata["adapter"],
            indexed_at=metadata["indexed_at"],
            item_count=row["item_count"] or 0,
            file_count=row["file_count"] or 0,
            directory_count=row["directory_count"] or 0,
            total_bytes=row["total_bytes"] or 0,
        )

    def get(self, item_id: str) -> ProjectItem | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return _item_from_row(row) if row else None

    def get_by_path(self, relative_path: str) -> ProjectItem | None:
        normalized = relative_path.strip("/")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM items WHERE relative_path = ?", (normalized,)
            ).fetchone()
        return _item_from_row(row) if row else None

    def children(self, parent_id: str) -> list[ProjectItem]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM items
                WHERE parent_id = ?
                ORDER BY is_directory DESC, name COLLATE NOCASE
                """,
                (parent_id,),
            ).fetchall()
        return [_item_from_row(row) for row in rows]

    def ancestors(self, item: ProjectItem) -> list[ProjectItem]:
        result: list[ProjectItem] = []
        current: ProjectItem | None = item
        while current is not None:
            result.append(current)
            current = self.get(current.parent_id) if current.parent_id else None
        result.reverse()
        return result

    def search(
        self,
        query: str,
        *,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        query = query.strip()
        if not query:
            return []
        pattern = f"%{query}%"
        clauses = ["(name LIKE ? OR relative_path LIKE ? OR text_content LIKE ?)"]
        parameters: list[object] = [pattern, pattern, pattern]
        if kind:
            clauses.append("kind = ?")
            parameters.append(kind)
        parameters.append(limit)
        sql = (
            "SELECT * FROM items WHERE "
            + " AND ".join(clauses)
            + " ORDER BY is_directory DESC, name COLLATE NOCASE LIMIT ?"
        )
        with self._connection() as connection:
            rows = connection.execute(sql, parameters).fetchall()

        lowered = query.casefold()
        results: list[dict[str, object]] = []
        for row in rows:
            item = _item_from_row(row)
            value = item.public_dict()
            content = item.text_content or ""
            position = content.casefold().find(lowered)
            if position >= 0:
                start = max(0, position - 90)
                end = min(len(content), position + len(query) + 140)
                snippet = " ".join(content[start:end].split())
                if start:
                    snippet = "…" + snippet
                if end < len(content):
                    snippet += "…"
                value["snippet"] = snippet
            results.append(value)
        return results

    def all_items(self) -> list[ProjectItem]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM items ORDER BY relative_path COLLATE NOCASE"
            ).fetchall()
        return [_item_from_row(row) for row in rows]

