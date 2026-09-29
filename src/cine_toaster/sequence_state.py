"""Sequence versions: runtime-owned state beside the manifest that declares them.

A sequence is declared in `project.yaml`, which is authored and never rewritten
(ADR 0006). Its versions -- each an assembled cut of the sequence, the scene
versions it was built from, and the verdict on it -- are runtime state, kept in
`sequences.state.json` beside the manifest and written only by commands,
atomically.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

FILENAME = "sequences.state.json"


def state_path(root: Path) -> Path:
    return Path(root) / FILENAME


def load(root: Path) -> dict[str, Any]:
    path = state_path(root)
    if not path.is_file():
        return {"revision": 0, "sequences": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"revision": 0, "sequences": {}}
    data.setdefault("revision", 0)
    data.setdefault("sequences", {})
    return data


def write(root: Path, data: dict[str, Any]) -> None:
    path = state_path(root)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def versions(root: Path, sequence_id: str) -> list[dict[str, Any]]:
    return list(load(root)["sequences"].get(sequence_id, {}).get("versions", []))
