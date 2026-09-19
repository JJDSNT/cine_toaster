from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProjectItem:
    """One indexed filesystem item.

    The first milestone deliberately keeps this model small. Richer production
    concepts can be added later without changing the fact that every item has
    a stable address inside an external project directory.
    """

    id: str
    parent_id: str | None
    kind: str
    name: str
    relative_path: str
    is_directory: bool
    media_type: str | None
    extension: str | None
    size: int
    modified_ns: int
    text_content: str | None = None

    def public_dict(self, *, include_text: bool = False) -> dict[str, Any]:
        value = asdict(self)
        if not include_text:
            value.pop("text_content", None)
        return value


@dataclass(frozen=True, slots=True)
class ProjectSummary:
    id: str
    name: str
    root: str
    adapter: str
    indexed_at: str
    item_count: int
    file_count: int
    directory_count: int
    total_bytes: int

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)

