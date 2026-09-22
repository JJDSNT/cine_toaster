from __future__ import annotations

from ..errors import CineToasterError


class MediaDependencyError(CineToasterError):
    """An optional image or video dependency is not installed."""

    code = "media_dependency_missing"
    http_status = 500


def require(module: str, extra: str = "media"):
    """Import an optional dependency, or say exactly how to get it.

    These operations need numpy, Pillow or OpenCV, which are large and useless
    to someone who only wants to read a production and decide between takes. The
    core install stays light and the error tells you what to add.
    """

    try:
        return __import__(module)
    except ImportError as error:  # pragma: no cover - exercised by the skip guard
        raise MediaDependencyError(
            f"{module} is required for this operation. Install it with: "
            f"pip install 'cine-toaster[{extra}]'",
            module=module,
            extra=extra,
        ) from error


def available(module: str) -> bool:
    try:
        __import__(module)
    except ImportError:
        return False
    return True


__all__ = ["MediaDependencyError", "available", "require"]
