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


class PictureProvider(Protocol):
    """Makes a shot's master picture (ADR 0025). The picture belongs to the film; the model to the adapter.

    What differs between models stays here: whether a source picture is needed,
    how the request is worded, the size, how it is paid. `pictures.py` chooses
    an adapter by the cascade production -> scene -> shot and asks it these.
    """

    id: str
    model: str
    #: True when the model can only repaint a picture (it has no way to compose one).
    needs_source: bool
    #: "usd" (held by the budget) or "quota" (a subscription's; recorded, never priced).
    cost: str

    def prompt(self, request: str, *, source: bool, references: int) -> str: ...

    def size(self, source: Path | None) -> tuple[int, int] | None: ...

    def estimate_usd(self, rate: float | None = None) -> float: ...

    def make(self, *, source: Path | None, references: list[Path], prompt: str, seed: int,
             size: tuple[int, int] | None, output: Path, label: str = "picture",
             state_file: Path | None = None) -> dict[str, Any]: ...


DEFAULT_PICTURE_PROVIDER = "qwen-image-edit"


def picture_providers() -> dict[str, type]:
    """Every adapter that can make a master picture, by id."""

    from .codex_image import CodexImageProvider
    from .qwen_edit import QwenEditProvider

    return {QwenEditProvider.id: QwenEditProvider, CodexImageProvider.id: CodexImageProvider}


__all__ = [
    "DEFAULT_PICTURE_PROVIDER",
    "PictureProvider",
    "picture_providers",
    "GenerationResult",
    "ImageToVideoProvider",
    "ProviderError",
    "ProviderNotConfigured",
]
