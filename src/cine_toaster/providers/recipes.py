"""Generation recipes: what each generation adapter does, in filmmaking terms (ADR 0034).

A recipe is how a production agent (and `toast doctor`) knows a generation
path without knowing its graph: what it makes from what, where it runs, what
it needs configured, which model files its ComfyUI graph loads, and what it
costs and takes. The graph and the provider's vocabulary stay in the adapter;
the numbers are the adapter's own constants, read here, never copied.

Health is read from the data plane only (`/health` of a serverless endpoint):
workers and queue. Creating or changing endpoints, pods or volumes is not done
here -- that is runpodctl, the RunPod console or MCP, and a person.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import ProviderError, ProviderNotConfigured

MODEL_SUFFIXES = (".safetensors", ".ckpt", ".pt", ".pth", ".gguf", ".bin")
KNOWLEDGE = Path(__file__).parents[1] / "knowledge" / "providers"


@dataclass(frozen=True)
class Recipe:
    id: str
    #: What it makes, from what, in a film's words.
    does: str
    kind: str                      # image_to_video | picture | reference_image
    transport: str                 # runpod-serverless | codex-cli
    inputs: tuple[str, ...]
    endpoint_env: str = ""
    credentials_env: str = ""
    workflow: Path | None = None
    knowledge: tuple[str, ...] = ()
    #: Read from the adapter at call time, so the recipe never drifts from it.
    numbers: Callable[[], dict[str, Any]] = field(default=lambda: {})
    cost: str = "usd"              # usd (held by the budget) | quota (a subscription's)


def _ltx() -> dict[str, Any]:
    from ..generation import COLD_START_SECONDS, EXECUTION_SECONDS_PER_CLIP_SECOND
    from .ltx import FPS, HOURLY_RATE_USD, MAX_SECONDS, MODEL

    return {"model": MODEL, "max_seconds": MAX_SECONDS, "fps": FPS, "rate_usd_per_hour": HOURLY_RATE_USD,
            "execution_seconds_per_clip_second": EXECUTION_SECONDS_PER_CLIP_SECOND,
            "cold_start_seconds": COLD_START_SECONDS}


def _qwen() -> dict[str, Any]:
    from .qwen_edit import COLD_START_SECONDS, EXECUTION_SECONDS, HOURLY_RATE_USD, MODEL

    return {"model": MODEL, "rate_usd_per_hour": HOURLY_RATE_USD, "execution_seconds": EXECUTION_SECONDS,
            "cold_start_seconds": COLD_START_SECONDS}


def _codex() -> dict[str, Any]:
    from .codex_image import CodexImageProvider

    return {"model": CodexImageProvider.model, "rate_usd_per_hour": None}


RECIPES: dict[str, Recipe] = {recipe.id: recipe for recipe in (
    Recipe("ltx-2-5", "a clip with sound from a block of shots: its first picture, guides at each cut, the "
           "block's prompt, optionally a voice and a control video", "image_to_video", "runpod-serverless",
           ("first picture", "cut guides", "prompt", "reference voice", "control video"),
           endpoint_env="RUNPOD_LTX_ENDPOINT_ID", credentials_env="RUNPOD_API_KEY",
           workflow=Path(__file__).with_name("workflows") / "ltx25_i2v_api.json",
           knowledge=("ltx-2.5", "runpod-serverless"), numbers=_ltx),
    Recipe("qwen-image-edit", "a master picture repainted from a source picture (a render, a blockout) keeping "
           "its geometry, with identity references", "picture", "runpod-serverless",
           ("source picture", "identity references", "prompt"),
           endpoint_env="RUNPOD_QWEN_ENDPOINT_ID", credentials_env="RUNPOD_API_KEY",
           knowledge=("qwen-image-edit", "runpod-serverless"), numbers=_qwen),
    Recipe("codex-image", "a picture composed from words and attached references, on the person's ChatGPT "
           "subscription", "picture", "codex-cli", ("prompt", "references"), numbers=_codex, cost="quota"),
)}


def workflow_models(path: Path) -> list[dict[str, str]]:
    """The model files a ComfyUI API-format graph loads: what the endpoint's volume must hold."""

    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProviderError(f"Unreadable workflow {path}: {error}") from error
    found = []
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        for name, value in (node.get("inputs") or {}).items():
            if isinstance(value, str) and value.lower().endswith(MODEL_SUFFIXES):
                found.append({"loader": str(node.get("class_type", "")), "input": name, "file": value})
    return sorted({(item["loader"], item["input"], item["file"]): item for item in found}.values(),
                  key=lambda item: item["file"])


def known_failures(recipe: Recipe) -> list[dict[str, Any]]:
    """Measured failure patterns from the knowledge notes this recipe cites."""

    import tomllib

    claims = []
    for note in recipe.knowledge:
        path = KNOWLEDGE / f"{note}.md"
        try:
            text = path.read_text(encoding="utf-8")
            front = tomllib.loads(text.split("+++")[1]) if text.startswith("+++") else {}
        except (OSError, IndexError, tomllib.TOMLDecodeError):
            continue
        for claim in front.get("claims") or []:
            if claim.get("workaround"):
                claims.append({"note": note, "id": claim.get("id"), "claim": claim.get("claim"),
                               "workaround": claim.get("workaround"), "status": claim.get("status"),
                               "measured_on": str(claim.get("measured_on") or "")})
    return claims


def describe(recipe: Recipe) -> dict[str, Any]:
    """The recipe as a record: what it does and whether this machine is configured for it (never a secret)."""

    missing = [name for name in (recipe.endpoint_env, recipe.credentials_env) if name and not os.environ.get(name)]
    if recipe.transport == "codex-cli":
        import shutil
        missing += [] if shutil.which(os.environ.get("CINE_TOASTER_CODEX_CLI", "codex")) else ["codex on PATH"]
    return {"id": recipe.id, "does": recipe.does, "kind": recipe.kind, "transport": recipe.transport,
            "inputs": list(recipe.inputs), "cost": recipe.cost, **recipe.numbers(),
            "endpoint_env": recipe.endpoint_env, "configured": not missing, "missing": missing,
            "models": workflow_models(recipe.workflow) if recipe.workflow else [],
            "known_failures": known_failures(recipe)}


def recipes() -> list[dict[str, Any]]:
    return [describe(recipe) for recipe in RECIPES.values()]


def health(recipe_id: str, transport: Callable[[str, dict | None], dict] | None = None) -> dict[str, Any]:
    """Workers and queue of a recipe's endpoint, read from the data plane; says plainly what it could not read."""

    recipe = RECIPES.get(recipe_id)
    if recipe is None:
        raise ProviderNotConfigured(f"No generation recipe {recipe_id!r}", allowed=sorted(RECIPES))
    if recipe.transport != "runpod-serverless":
        return {"recipe": recipe_id, "readable": False, "reason": f"{recipe.transport} has no endpoint to read"}
    endpoint = os.environ.get(recipe.endpoint_env, "")
    if not endpoint:
        return {"recipe": recipe_id, "readable": False, "reason": f"{recipe.endpoint_env} is not set"}
    from .runpod import request

    try:
        answer = (transport or request)(f"/{endpoint}/health", None)
    except ProviderNotConfigured as error:
        return {"recipe": recipe_id, "readable": False, "reason": error.message}
    except Exception as error:  # an unreachable endpoint is a finding, not a crash
        return {"recipe": recipe_id, "readable": False, "reason": f"health not readable: {error}"}
    workers, jobs = answer.get("workers") or {}, answer.get("jobs") or {}
    warm = int(workers.get("idle") or 0) + int(workers.get("running") or 0) + int(workers.get("ready") or 0)
    return {"recipe": recipe_id, "readable": True, "workers": workers, "jobs": jobs,
            "warm_workers": warm, "cold_start_likely": warm == 0,
            "unhealthy": int(workers.get("unhealthy") or 0), "throttled": int(workers.get("throttled") or 0)}
