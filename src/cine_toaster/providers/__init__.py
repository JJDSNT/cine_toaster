from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..errors import CineToasterError


class ProviderError(CineToasterError):
    """A generation provider failed, or refused the request."""

    code = "provider_failed"
    http_status = 502


class ProviderNotConfigured(ProviderError):
    """Credentials or an endpoint are missing for this provider."""

    code = "provider_not_configured"
    http_status = 400


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """What a provider produced, and what it cost to produce it.

    Provenance is recorded as the provider's own namespaced payload. The Core
    preserves it without interpreting it, which is what lets a take be
    reproduced later without every layer learning one provider's vocabulary.
    """

    media: Path
    provider: str
    model: str
    seed: int
    duration_seconds: float = 0.0
    cost_usd: float = 0.0
    provenance: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {
            "media": str(self.media),
            "provider": self.provider,
            "model": self.model,
            "seed": self.seed,
            "duration_seconds": self.duration_seconds,
            "cost_usd": self.cost_usd,
            "provenance": self.provenance,
        }


class ImageToVideoProvider(Protocol):
    """The one capability the production actually uses today.

    Deliberately narrow. A wider interface written before a second provider
    exists would describe an imagined provider rather than a real one.
    """

    id: str

    def generate(
        self,
        *,
        image: Path,
        output: Path,
        seconds: int,
        prompt: str,
        seed: int = 1,
        guides: tuple[tuple[Path, int, float], ...] = (),
        reference_voice: Path | None = None,
        control_video: tuple[Path, float] | None = None,
        label: str = "",
    ) -> GenerationResult: ...


__all__ = [
    "GenerationResult",
    "ImageToVideoProvider",
    "ProviderError",
    "ProviderNotConfigured",
]
