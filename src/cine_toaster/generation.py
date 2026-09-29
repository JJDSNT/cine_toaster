"""A block of shots, planned as one generation from the production's records (CT-0037).

The plan is built from what the production declares -- the shots of the block,
their pictures, cameras, actions, lines, voices and sound -- and told to the
provider in its own grammar. Everything that will be sent is known before
anything is: the starting picture, the guides at each cut, the prompt, the
length, and an estimate of the cost, which the budget must allow.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .blocks import reference_picture, requested_cuts, scene_blocks
from .cast import cast_key
from .errors import ValidationError
from .providers.ltx import FPS, HOURLY_RATE_USD, MAX_SECONDS
from .providers.ltx_prompt import Line, ShotPrompt, block_prompt
from .takes import work_directory_for

#: Measured on SINGULAR (knowledge/providers/ltx-2.5.md): a 10 s clip at
#: 1280x704 took about 64 s on an L40S. The estimate keeps that ratio and adds
#: the queue a warm worker still spends.
EXECUTION_SECONDS_PER_CLIP_SECOND = 6.4
QUEUE_SECONDS = 15.0
GUIDE_STRENGTH = 0.7


@dataclass(slots=True)
class Reference:
    role: str
    path: Path
    frame: int
    digest: str


@dataclass(slots=True)
class BlockPlan:
    scene: str
    block: str
    shots: list[str]
    seconds: int
    image: Path
    guides: list[Reference]
    prompt: str
    seed: int
    estimate_usd: float
    notes: list[str] = field(default_factory=list)

    def public_dict(self, root: Path) -> dict[str, Any]:
        return {
            "scene": self.scene, "block": self.block, "shots": self.shots, "seconds": self.seconds,
            "image": self.image.relative_to(root).as_posix(),
            "guides": [{"role": ref.role, "path": ref.path.relative_to(root).as_posix(), "frame": ref.frame,
                        "digest": ref.digest} for ref in self.guides],
            "prompt": self.prompt, "seed": self.seed, "estimate_usd": self.estimate_usd, "notes": self.notes,
        }


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def estimate(seconds: float, hourly_rate: float = HOURLY_RATE_USD) -> float:
    return round((seconds * EXECUTION_SECONDS_PER_CLIP_SECOND + QUEUE_SECONDS) * hourly_rate / 3600, 3)


def _from_shot(scene: dict[str, Any], shot: dict[str, Any]) -> dict[str, Any] | None:
    for item in shot.get("from") or []:
        ref = str(item.get("ref") or "") if isinstance(item, dict) else ""
        match = next((other for other in scene["shots"] if cast_key(other.get("number")) == cast_key(ref)), None)
        if match:
            return match
    return None


def _camera(scene: dict[str, Any], shot: dict[str, Any]) -> str:
    ids = {camera["id"] for camera in (scene.get("geometry") or {}).get("cameras", [])}
    text = shot.get("camera_text") or ""
    return text if text and text not in ids and text != shot.get("camera") else ""


def _voice(production: dict[str, Any], scene: dict[str, Any], who: str) -> tuple[str, str]:
    """(how to refer to the speaker, the voice) from the cast sheet, else the scene."""

    key = cast_key(who)
    member = next((m for m in (production.get("cast") or {}).values()
                   if key in {cast_key(n) for n in [m["id"], m["label"], *m.get("names", [])]}), None)
    refer = {cast_key(k): str(v) for k, v in (scene.get("refer_as") or {}).items()}.get(key) or who.title()
    state = {cast_key(k): str(v) for k, v in (scene.get("voice_state") or {}).items()}.get(key, "")
    identity = ((member or {}).get("voice") or {}).get("described", "")
    if not identity:
        identity = {cast_key(k): str(v) for k, v in (scene.get("voices") or {}).items()}.get(key, "")
    voice = f"{identity}; now {state}" if identity and state else (identity or state)
    return refer, " ".join(voice.split())


def hourly_rate(root: Path, endpoint: str) -> float:
    """The production's declared price for the endpoint, else the provider's assumed one."""

    from .project import _read_yaml

    rates = _read_yaml(root / "project.yaml").get("generation_rates") or {}
    return float(rates.get(endpoint, HOURLY_RATE_USD))


def plan_block(root: Path, production: dict[str, Any], scene_id: str, block_id: str, seed: int = 1,
               rate: float = HOURLY_RATE_USD) -> BlockPlan:
    """Everything one generation of the block will be given, and what it should cost."""

    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        raise ValidationError(f"No scene {scene_id!r}")
    work = work_directory_for(root / scene["file"])
    block = next((item for item in scene_blocks(scene, work, root) if item.id == str(block_id)), None)
    if block is None:
        raise ValidationError(f"{scene_id} has no block {block_id!r}")
    if not block.contiguous:
        raise ValidationError(f"Block {block_id} is not a run of consecutive shots")
    seconds = sum(block.durations)
    if seconds != int(seconds) or not 1 <= seconds <= MAX_SECONDS:
        raise ValidationError(f"Block {block_id} runs {seconds:g} s; LTX 2.5 takes 1 to {MAX_SECONDS} whole seconds "
                              f"(claim duration-limits)")
    shots = {shot["id"]: shot for shot in scene["shots"]}
    notes: list[str] = []
    prompts, references = [], []
    for shot_id in block.shots:
        shot = shots[shot_id]
        source = _from_shot(scene, shot)
        picture = shot.get("picture") or (source or {}).get("picture") or ""
        if not picture:
            notes.append(f"{shot_id} has no picture description (`picture`); the prompt names only its action.")
        reference = reference_picture(work, root, scene, shot)
        if reference is None:
            raise ValidationError(f"{shot_id} has no reference picture to start or guide from "
                                  f"(its still, p<n>.png, or the image of the shot it is made from)")
        references.append(reference)
        lines = []
        for line in shot.get("lines") or []:
            if not line.get("in_take", True):
                continue
            refer, voice = _voice(production, scene, line.get("who", ""))
            voice = line.get("voice") or voice
            lines.append(Line(refer, line.get("en") or line.get("text") or "", line.get("delivery", ""), voice))
        sound = shot.get("sound")
        prompts.append(ShotPrompt(picture, _camera(scene, shot), shot.get("description") or "", lines,
                                  sound if isinstance(sound, str) else ""))
    frames = requested_cuts(block.durations, FPS)
    # Frame 0 is guided with the first picture too: alone, the first image gives
    # way in a long block (claim frame-zero-guide); each later shot's picture
    # guides its cut (claim keyframe-guides).
    guides = [Reference("first", references[0], 0, _digest(references[0]))]
    guides += [Reference(shot_id, ref, frame, _digest(ref))
               for shot_id, ref, frame in zip(block.shots[1:], references[1:], frames[1:])]
    return BlockPlan(
        scene=scene_id, block=block.id, shots=block.shots, seconds=int(seconds), image=references[0],
        guides=guides, prompt=block_prompt(prompts), seed=seed, estimate_usd=estimate(seconds, rate), notes=notes,
    )
