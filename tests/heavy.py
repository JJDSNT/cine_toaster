"""The one mark the suite is split by (`tests/run.py`): `@heavy("why")` on a test class or method that needs
what is costly to run -- Blender, a model's inference, a long render. The reason is kept with the mark, so a
heavy test says what makes it so."""

from __future__ import annotations

import importlib.util
import unittest
from typing import Any, Callable

#: The make target that installs each optional module a test may need.
INSTALLED_BY = {"OpenEXR": "make install-vfx", "PyOpenColorIO": "make install-vfx"}


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


def needs(*modules: str) -> Callable[[Any], Any]:
    """Skip a test class or method, saying why and how to install it, when an optional module it needs is not
    here -- a missing extra is never a failure (CT-0096: a clean `make setup` lacked `vfx`, and 26 tests failed
    on `import OpenEXR`)."""

    missing = [module for module in modules if importlib.util.find_spec(module) is None]
    how = sorted({INSTALLED_BY.get(module, f"pip install {module}") for module in missing})
    return unittest.skipIf(bool(missing), f"needs {', '.join(missing)} ({'; '.join(how)})")
