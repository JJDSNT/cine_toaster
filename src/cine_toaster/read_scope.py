"""One read of the production per view: a request-scoped memo, never a cache that outlives it.

A view such as the Creation journal's assembles a dozen sub-views, and each
used to load the production and its references from disk again -- eight
production loads for one page. Inside `read_scope()`, the same root is read
once; outside it (every command that writes, every test), nothing is shared.
Callers inside a scope must treat what they get as read-only.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any, Callable, Iterator

_SCOPE: contextvars.ContextVar[dict | None] = contextvars.ContextVar("cine_toaster_read_scope", default=None)


@contextmanager
def read_scope() -> Iterator[None]:
    """Reads of the same root inside this block share one result. Nested scopes join the outer one."""

    if _SCOPE.get() is not None:
        yield
        return
    token = _SCOPE.set({})
    try:
        yield
    finally:
        _SCOPE.reset(token)


def scoped(kind: str, key: Any, compute: Callable[[], Any]) -> Any:
    scope = _SCOPE.get()
    if scope is None:
        return compute()
    if (kind, key) not in scope:
        scope[(kind, key)] = compute()
    return scope[(kind, key)]
