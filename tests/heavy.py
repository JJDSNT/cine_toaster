"""The one mark the suite is split by (`tests/run.py`): `@heavy("why")` on a test class or method that needs
what is costly to run -- Blender, a model's inference, a long render. The reason is kept with the mark, so a
heavy test says what makes it so."""

from __future__ import annotations

from typing import Any, Callable


def heavy(reason: str) -> Callable[[Any], Any]:
    if not reason:
        raise ValueError("A heavy test says why it is heavy")

    def mark(target: Any) -> Any:
        target.__heavy__ = reason
        return target

    return mark


def is_heavy(test: Any) -> bool:
    method = getattr(test, getattr(test, "_testMethodName", ""), None)
    return bool(getattr(method, "__heavy__", None) or getattr(type(test), "__heavy__", None))
