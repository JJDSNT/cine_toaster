"""Generation recipes: what each generation adapter does, in filmmaking terms (ADR 0034).

A recipe is how a production agent (and `toast doctor`) knows a generation
path without knowing its graph: what it makes from what, where it runs, what
it needs configured, which model files its ComfyUI graph loads, and what it
costs and takes. The graph and the provider's vocabulary stay in the adapter;
the numbers are the adapter's own constants, read here, never copied.

Health is read from the data plane (`/health`: workers and queue) and the
endpoint's scaling from REST v2 (`GET /serverless/{id}`), both read-only. A
batch is planned against them: sent together it pays one cold start, sent one
by one past the idle timeout it pays one per job; and lowering workers while
jobs are in flight strands them (both losses the author reported, 2026-10-17). Creating or changing endpoints, pods or volumes is not done
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


def endpoint_config(recipe_id: str, fetch: Callable[[str, dict], dict] | None = None) -> dict[str, Any]:
    """How the endpoint scales -- min/max workers, idle timeout, scaler, FlashBoot -- read, never written.

    REST v2 `GET /serverless/{id}`. Knowing the idle timeout is what lets a batch
    land on warm workers instead of paying one cold start per job.
    """

    recipe = RECIPES.get(recipe_id)
    if recipe is None or recipe.transport != "runpod-serverless":
        return {"readable": False, "reason": "no serverless endpoint for this recipe"}
    endpoint = os.environ.get(recipe.endpoint_env, "")
    if not endpoint:
        return {"readable": False, "reason": f"{recipe.endpoint_env} is not set"}
    from .runpod_billing import _get

    try:
        value = (fetch or _get)(f"/serverless/{endpoint}", {})
    except ProviderNotConfigured as error:
        return {"readable": False, "reason": error.message}
    except Exception as error:
        return {"readable": False, "reason": f"configuration not readable: {error}"}
    workers, scaling = value.get("workers") or {}, value.get("scaling") or {}
    return {"readable": True, "workers_min": workers.get("min"), "workers_max": workers.get("max"),
            "idle_timeout_seconds": workers.get("idleTimeout"), "scaling": scaling,
            "flashboot": value.get("flashboot"), "gpu_pools": (value.get("gpu") or {}).get("pools") or [],
            "data_centers": value.get("dataCenterIds") or []}


def scale_down_guard(state: dict[str, Any]) -> dict[str, Any]:
    """Whether lowering workers or the idle timeout now would strand work. Measured loss: it was done mid-batch."""

    if not state.get("readable"):
        return {"safe": False, "reason": "health not readable: assume work is in flight"}
    jobs = state.get("jobs") or {}
    in_flight = int(jobs.get("inQueue") or 0) + int(jobs.get("inProgress") or 0)
    return {"safe": in_flight == 0, "in_flight": in_flight,
            "reason": "no job queued or running" if not in_flight else
                      f"{in_flight} job(s) queued or running: lowering workers or idle timeout now strands them"}


def batch_plan(recipe_id: str, jobs: int, *, seconds_each: float | None = None,
               state: dict[str, Any] | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """What a batch of `jobs` costs in cold starts sent together versus one by one, and how to send it."""

    if recipe_id not in RECIPES:
        raise ProviderNotConfigured(f"No generation recipe {recipe_id!r}", allowed=sorted(RECIPES))
    if type(jobs) is not int or jobs < 1:
        raise ProviderError("A batch has at least one job")
    numbers = describe(RECIPES[recipe_id])
    cold = float(numbers.get("cold_start_seconds") or 0)
    execution = seconds_each if seconds_each is not None else float(
        numbers.get("execution_seconds") or (numbers.get("execution_seconds_per_clip_second") or 0) * 10)
    rate = float(numbers.get("rate_usd_per_hour") or 0)
    state = state if state is not None else health(recipe_id)
    config = config if config is not None else endpoint_config(recipe_id)
    warm = int(state.get("warm_workers") or 0) if state.get("readable") else 0
    most = int(config.get("workers_max") or 1) if config.get("readable") else 1
    idle = config.get("idle_timeout_seconds") if config.get("readable") else None
    rounds = -(-jobs // max(most, 1))
    starts_together = 0 if warm >= min(jobs, most) else min(jobs, most) - warm
    advice = [f"Send the {jobs} job(s) together: up to {most} worker(s) start once and the rest queue on warm "
              "workers." if jobs > 1 else "One job."]
    if idle is not None:
        advice.append(f"Workers stay warm {idle} s after their last job: anything sent later pays a cold start "
                      f"(about {cold:.0f} s) again.")
        if jobs > 1 and idle < execution:
            advice.append("The idle timeout is shorter than one job: raise it for the batch (and restore it after), "
                          "in the RunPod console or runpodctl, before sending -- never while jobs are in flight.")
    else:
        advice.append("The idle timeout is not known here: read it before sending one job at a time.")
    guard = scale_down_guard(state)
    if not guard["safe"]:
        advice.append(f"Do not lower workers or the idle timeout until the batch ends: {guard['reason']}.")
    seconds_together = (cold if starts_together else 0) + rounds * execution
    return {"recipe": recipe_id, "jobs": jobs, "seconds_each": execution, "warm_workers": warm,
            "workers_max": most if config.get("readable") else None, "idle_timeout_seconds": idle,
            "together": {"cold_starts": starts_together, "seconds": round(seconds_together),
                         "cold_usd": round(starts_together * cold * rate / 3600, 3)},
            "one_by_one_worst": {"cold_starts": jobs, "seconds": round(jobs * (cold + execution)),
                                 "cold_usd": round(jobs * cold * rate / 3600, 3)},
            "scale_down": guard, "advice": advice,
            "assumes": "cold start and execution are the adapter's estimates, not this endpoint's measurement"}


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
    value = {"recipe": recipe_id, "readable": True, "workers": workers, "jobs": jobs,
             "warm_workers": warm, "cold_start_likely": warm == 0,
             "unhealthy": int(workers.get("unhealthy") or 0), "throttled": int(workers.get("throttled") or 0)}
    return {**value, "scale_down": scale_down_guard(value)}
