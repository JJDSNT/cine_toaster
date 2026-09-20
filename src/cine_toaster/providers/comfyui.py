from __future__ import annotations

import base64
import copy
import json
import random
from pathlib import Path
from typing import Any

from . import ProviderError, ProviderNotConfigured
from .runpod import Transport, cost_usd, request, run_job


HOURLY_RATE_USD = 1.22

# A ComfyUI workflow is a graph of numbered nodes, and node numbers change every
# time someone re-exports it from the UI. Overrides are therefore applied by
# node *type*, so a re-export does not silently stop applying the seed.


def patch_workflow(
    workflow: dict[str, Any],
    *,
    prompt: str | None = None,
    negative: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    width: int | None = None,
    height: int | None = None,
    checkpoint: str | None = None,
) -> dict[str, Any]:
    """Apply overrides by node type rather than by node id."""

    patched = copy.deepcopy(workflow)
    positive_done = False
    for node in patched.values():
        node_type = node.get("class_type")
        inputs = node.setdefault("inputs", {})
        if node_type == "CLIPTextEncode":
            # Convention: the first text node is the positive prompt, and a node
            # titled "neg…" is the negative one.
            if node.get("_meta", {}).get("title", "").lower().startswith("neg"):
                if negative is not None:
                    inputs["text"] = negative
            elif not positive_done:
                if prompt is not None:
                    inputs["text"] = prompt
                positive_done = True
        elif node_type == "KSampler":
            if seed is not None:
                inputs["seed"] = seed
            if steps is not None:
                inputs["steps"] = steps
            if cfg is not None:
                inputs["cfg"] = cfg
        elif node_type == "RandomNoise":
            # Flux keeps the seed here instead.
            if seed is not None:
                inputs["noise_seed"] = seed
        elif node_type == "BasicScheduler":
            if steps is not None:
                inputs["steps"] = steps
        elif node_type == "EmptyLatentImage":
            if width:
                inputs["width"] = width
            if height:
                inputs["height"] = height
        elif node_type == "CheckpointLoaderSimple" and checkpoint:
            inputs["ckpt_name"] = checkpoint
    return patched


def save_images(images: list[Any], destination: Path, tag: str) -> list[Path]:
    """Write the base64 images a worker returned, skipping S3 references."""

    destination.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for index, image in enumerate(images):
        if isinstance(image, dict) and image.get("type") == "s3_url":
            continue
        blob = image.get("data") if isinstance(image, dict) else image
        if not blob:
            continue
        name = (image.get("filename") if isinstance(image, dict) else None) or f"{tag}_{index}.png"
        path = destination / f"{tag}_{index}_{name}".replace("/", "_")
        path.write_bytes(base64.b64decode(blob))
        saved.append(path)
    return saved


def run_workflow(
    endpoint_id: str,
    workflow: dict[str, Any],
    *,
    destination: Path,
    state_file: Path,
    seed: int | None = None,
    label: str = "comfyui",
    transport: Transport | None = None,
    **overrides: Any,
) -> tuple[list[Path], int]:
    """Run one ComfyUI graph and keep whatever images come back."""

    if not endpoint_id:
        raise ProviderNotConfigured("No ComfyUI endpoint id was given")
    chosen_seed = seed if seed is not None else random.randrange(2**32)
    patched = patch_workflow(workflow, seed=chosen_seed, **overrides)
    output = run_job(
        endpoint_id,
        {"workflow": patched},
        state_file=state_file,
        label=label,
        transport=transport,
    )
    images = output.get("images") or []
    if not images:
        raise ProviderError(f"{label}: the worker returned no images", endpoint=endpoint_id)
    return save_images(images, destination, f"{label}_{chosen_seed}"), chosen_seed


def health(endpoint_id: str) -> dict[str, Any]:
    return request(f"/{endpoint_id}/health", None)


def load_workflow(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProviderError(f"Unreadable ComfyUI workflow {path}: {error}") from error


__all__ = [
    "HOURLY_RATE_USD",
    "cost_usd",
    "health",
    "load_workflow",
    "patch_workflow",
    "run_workflow",
    "save_images",
]
