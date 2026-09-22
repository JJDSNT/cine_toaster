"""A look: the visual contract a shot is made under.

A production already declares one -- Singular carries `look:` on 177 of its 359
shots -- but it declared a name with nothing behind it. This gives the name a
body, at project level, so that what must stay consistent across scenes is
written once (ADR 0012).

Resolution is a cascade: project, sequence, scene, shot. The nearest
declaration wins, and the path it took is reported, because a value a director
cannot trace is a value they will not trust.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any

import yaml


LOOKS_DIRECTORY = "looks"
LOOK_FILE = "look.yaml"

#: The sections a look may carry. Anything else is kept and shown, never
#: dropped, on the same rule as a shot's extra fields (SPEC-0004).
SECTIONS = (
    "palette",
    "typography",
    "motion",
    "audio",
    "generation",
    "grade",
    "rules",
)


@dataclass(frozen=True, slots=True)
class Look:
    id: str
    label: str
    sections: dict[str, Any] = dataclass_field(default_factory=dict)
    extra: dict[str, Any] = dataclass_field(default_factory=dict)
    path: str = ""

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            **{name: self.sections.get(name) for name in SECTIONS},
            "extra": self.extra,
            "path": self.path,
        }

    @property
    def pacing(self) -> dict[str, Any]:
        """Motion rules a runner and a check both read."""

        motion = self.sections.get("motion") or {}
        return motion if isinstance(motion, dict) else {}


def load_looks(root: Path) -> dict[str, Look]:
    """Every look declared by the production, by id."""

    directory = root / LOOKS_DIRECTORY
    if not directory.is_dir():
        return {}

    looks: dict[str, Look] = {}
    for path in sorted(directory.glob(f"*/{LOOK_FILE}")):
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(document, dict):
            continue
        look_id = str(document.get("id") or path.parent.name)
        sections = {name: document[name] for name in SECTIONS if name in document}
        extra = {
            key: value
            for key, value in document.items()
            if key not in SECTIONS and key not in {"id", "label"}
        }
        looks[look_id] = Look(
            id=look_id,
            label=str(document.get("label") or look_id),
            sections=sections,
            extra=extra,
            path=path.relative_to(root).as_posix(),
        )
    return looks


def resolve(
    *,
    shot: str = "",
    scene: str = "",
    sequence: str = "",
    project: str = "",
) -> tuple[str, str]:
    """The look in force, and the level that decided it.

    Returned rather than applied, so the interface can say *why* a shot looks
    the way it does instead of only what it looks like.
    """

    for level, value in (
        ("shot", shot),
        ("scene", scene),
        ("sequence", sequence),
        ("project", project),
    ):
        if value:
            return value, level
    return "", ""
