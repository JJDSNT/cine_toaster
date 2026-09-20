from __future__ import annotations

from typing import Any


class CineToasterError(Exception):
    """Base class for domain errors crossing an interface boundary.

    Every interface (CLI, HTTP, UI, agent tool) reports the same ``code`` for
    the same domain failure, so callers can react without parsing messages.
    """

    code = "error"
    http_status = 500

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def public_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, **self.details}}


class ValidationError(CineToasterError):
    """The requested intent is malformed or violates a domain rule."""

    code = "validation_failed"
    http_status = 422


class ResourceNotFoundError(CineToasterError):
    """A referenced project, scene, shot, or take does not exist."""

    code = "not_found"
    http_status = 404


class TakeNotEligibleError(CineToasterError):
    """The take exists but may not be selected in its current state."""

    code = "take_not_eligible"
    http_status = 409


class RevisionConflictError(CineToasterError):
    """Someone committed a newer revision than the caller expected."""

    code = "revision_conflict"
    http_status = 409

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(
            f"Expected revision {expected} but the scene is at revision {actual}",
            expected_revision=expected,
            actual_revision=actual,
        )


class PersistenceError(CineToasterError):
    """Canonical state could not be committed; prior state is unchanged."""

    code = "persistence_failed"
    http_status = 500


class PermissionDeniedError(CineToasterError):
    """The actor may not perform this command on this project."""

    code = "permission_denied"
    http_status = 403
