from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .index import workspace_cache_dir


MAX_REPLAY_EVENTS = 500


@dataclass(frozen=True, slots=True)
class Event:
    """Something that already happened to canonical production state.

    Events are operational: they drive live interfaces and give an audit trail
    for a session. Deleting the log loses history of *when* work happened, never
    the production truth itself, which lives in the project directory.
    """

    id: str
    type: str
    project_id: str
    occurred_at: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, event_type: str, project_id: str, **payload: Any) -> Event:
        return cls(
            id="evt_" + uuid.uuid4().hex[:16],
            type=event_type,
            project_id=project_id,
            occurred_at=datetime.now(UTC).isoformat(),
            payload=payload,
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "project_id": self.project_id,
            "occurred_at": self.occurred_at,
            "payload": self.payload,
        }


def event_log_path(root: Path) -> Path:
    return workspace_cache_dir(root) / "events.jsonl"


def append_event(root: Path, event: Event) -> Event:
    """Append one committed event.

    Called only after a successful canonical write. A failure to record the
    event must not fail the command that already committed, so the caller gets
    the event back either way.
    """

    path = event_log_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event.public_dict(), ensure_ascii=False) + "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        return event
    return event


def read_events(root: Path, *, offset: int = 0, limit: int | None = None) -> tuple[list[dict[str, Any]], int]:
    """Read events written after ``offset`` bytes.

    Returns the parsed events and the new byte offset, so an interface can poll
    for new activity without re-reading or remembering the whole log.
    """

    path = event_log_path(root)
    if not path.is_file():
        return [], 0

    size = path.stat().st_size
    if offset > size:
        # The log was truncated or rebuilt; restart from the beginning.
        offset = 0
    if offset == size:
        return [], size

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        handle.seek(offset)
        payload = handle.read()
        new_offset = offset + len(payload.encode("utf-8"))

    for line in payload.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if limit is not None and len(events) > limit:
        events = events[-limit:]
    return events, new_offset


def tail_events(root: Path, limit: int = 50) -> list[dict[str, Any]]:
    events, _ = read_events(root, offset=0, limit=min(limit, MAX_REPLAY_EVENTS))
    return events
