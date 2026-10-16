"""Qwen Image Edit on a RunPod serverless endpoint: a picture repainted, not recomposed.

The endpoint takes the picture to edit as `image_base64` and identity
references as `image_base64_2`, `_3`…, with a prompt, a seed and a size, and
returns `{"image": <base64>}`. What the model obeys and how it fails is in
`knowledge/providers/qwen-image-edit.md`; the rules here answer those claims.
"""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Any

from . import ProviderError, ProviderNotConfigured
from .runpod import Transport, run_job

MODEL = "qwen-image-edit"
#: SINGULAR's figure for this endpoint (RTX 4090 / Ada 24 GB pools).
HOURLY_RATE_USD = 1.58
EXECUTION_SECONDS = 45.0
COLD_START_SECONDS = 90.0

#: Without these the editor recomposes instead of repainting, and the 3D
#: model's geometry -- the reason the render exists -- is lost (claim
#: `recomposes-without-geometry-clauses`). Measured wording from SINGULAR.
GEOMETRY = ("IMAGE 1 is the ONLY source of truth for geometry and composition: keep the exact camera, "
            "framing, perspective, and the position and size of every element. Repaint surfaces only. "
            "Do not reframe, recenter, zoom, or move any object. ")
IDENTITY = (" The other images are for identity only: ignore their composition, framing and background. "
            "Nothing that is not in image 1 may be added.")
SELF_CHECK = (" Self-check: overlaid at 50% on image 1 there are no double edges — every wall, window, door, "
              "bed, machine and person keeps exactly the same outline and the same place in the frame.")


def edit_prompt(request: str, with_references: bool) -> str:
    return GEOMETRY + " ".join(request.split()) + (IDENTITY if with_references else "") + SELF_CHECK


def size_like(path: Path, widest: int = 1408) -> tuple[int, int]:
    """Width and height in multiples of 32, in the source's proportion (claim `size-follows-source`)."""

    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size
    target = min(widest, max(1024, round(width * 2 / 32) * 32))
    return target, max(32, round(target * height / width / 32) * 32)


def padded(path: Path, width: int, height: int) -> bytes:
    """A reference completed with neutral grey to the frame's proportion.

    The editor follows the proportion of most of its images; square cast
    sheets against a 16:9 render made it recompose (claim `majority-aspect`).
    """

    from PIL import Image

    image = Image.open(path).convert("RGB")
    w, h = image.size
    if abs(w / h - width / height) >= 0.01:
        if w / h < width / height:
            canvas = Image.new("RGB", (round(h * width / height), h), (118, 118, 118))
            canvas.paste(image, ((canvas.width - w) // 2, 0))
        else:
            canvas = Image.new("RGB", (w, round(w * height / width)), (118, 118, 118))
            canvas.paste(image, (0, (canvas.height - h) // 2))
        image = canvas
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class QwenEditProvider:
    id = "qwen-image-edit"
    model = MODEL
    needs_source = True
    cost = "usd"

    def prompt(self, request: str, *, source: bool, references: int) -> str:
        return edit_prompt(request, bool(references))

    def size(self, source: Path | None) -> tuple[int, int] | None:
        return size_like(source) if source is not None else None

    def estimate_usd(self, rate: float | None = None) -> float:
        # A warm edit took under a minute in SINGULAR; the estimate assumes a cold worker.
        return round((EXECUTION_SECONDS + COLD_START_SECONDS) * (rate or HOURLY_RATE_USD) / 3600, 3)

    def make(self, *, source: Path | None, references: list[Path], prompt: str, seed: int,
             size: tuple[int, int] | None, output: Path, label: str = "picture",
             state_file: Path | None = None) -> dict[str, Any]:
        if source is None or size is None:
            raise ProviderError(f"{label}: Qwen Image Edit repaints a picture and needs one to start from")
        return self.edit(source=source, references=references, prompt=prompt, seed=seed, size=size,
                         output=output, label=label, state_file=state_file)

    def __init__(self, endpoint_id: str | None = None, *, transport: Transport | None = None) -> None:
        self.endpoint_id = endpoint_id or os.environ.get("RUNPOD_QWEN_ENDPOINT_ID", "")
        self.transport = transport

    def edit(self, *, source: Path, references: list[Path], prompt: str, seed: int, size: tuple[int, int],
             output: Path, label: str = "picture", state_file: Path | None = None) -> dict[str, Any]:
        if not self.endpoint_id:
            raise ProviderNotConfigured("RUNPOD_QWEN_ENDPOINT_ID is not set")
        width, height = size
        payload: dict[str, Any] = {"prompt": prompt, "seed": seed, "width": width, "height": height,
                                   "image_base64": base64.b64encode(padded(source, width, height)).decode()}
        for index, reference in enumerate(references):
            payload[f"image_base64_{index + 2}"] = base64.b64encode(padded(reference, width, height)).decode()
        result = run_job(self.endpoint_id, payload, state_file=state_file or output.with_name(output.name + ".job.json"),
                         label=label, transport=self.transport)
        data = result.get("image") if isinstance(result, dict) else None
        if not data:
            raise ProviderError(f"{label}: the worker returned no image", endpoint=self.endpoint_id)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ".tmp")
        temporary.write_bytes(base64.b64decode(str(data).split(",", 1)[-1]))
        os.replace(temporary, output)
        return {"endpoint": self.endpoint_id, "width": width, "height": height}


from ..pictures import edge_score  # noqa: E402  (kept importable from here; the measure is the film's)
