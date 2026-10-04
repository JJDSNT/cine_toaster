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
from .providers.ltx_prompt import Line, ShotPrompt, block_prompt, block_prompt_sections
from .takes import work_directory_for

#: Measured on SINGULAR (knowledge/providers/ltx-2.5.md): a 10 s clip at
#: 1280x704 took about 64 s on an L40S, warm.
EXECUTION_SECONDS_PER_CLIP_SECOND = 6.4
#: A cold worker loads the model first: 1-02A block 2 ran 97 s warm and 245 s
#: cold (2026-09-29). The estimate assumes the worse case.
COLD_START_SECONDS = 150.0
GUIDE_STRENGTH = 0.7


@dataclass(slots=True)
class Reference:
    role: str
    path: Path
    frame: int
    digest: str
    strength: float = GUIDE_STRENGTH


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
    #: The prompt by shot, then what holds across the block; joined, it is `prompt`.
    sections: list[dict[str, str]] = field(default_factory=list)
    #: What the generation must not do (the production's intent), and how the provider represents it.
    avoid: list[str] = field(default_factory=list)
    negative: str = ""
    avoid_mechanism: str = ""
    #: What holds when the shot begins (the continuity ledger, CT-0059): shown to the author, not sent.
    continuity: list[str] = field(default_factory=list)

    def public_dict(self, root: Path) -> dict[str, Any]:
        return {
            "scene": self.scene, "block": self.block, "shots": self.shots, "seconds": self.seconds,
            "image": self.image.relative_to(root).as_posix(),
            "guides": [{"role": ref.role, "path": ref.path.relative_to(root).as_posix(), "frame": ref.frame,
                        "digest": ref.digest, "strength": ref.strength} for ref in self.guides],
            "prompt": self.prompt, "prompt_sections": self.sections, "seed": self.seed,
            "avoid": self.avoid, "negative": self.negative, "avoid_mechanism": self.avoid_mechanism, "continuity": self.continuity,
            "estimate_usd": self.estimate_usd, "notes": self.notes,
        }


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def estimate(seconds: float, hourly_rate: float = HOURLY_RATE_USD) -> float:
    return round((seconds * EXECUTION_SECONDS_PER_CLIP_SECOND + COLD_START_SECONDS) * hourly_rate / 3600, 3)


def _from_shot(scene: dict[str, Any], shot: dict[str, Any]) -> dict[str, Any] | None:
    for item in shot.get("from") or []:
        ref = str(item.get("ref") or "") if isinstance(item, dict) else ""
        match = next((other for other in scene["shots"] if cast_key(other.get("number")) == cast_key(ref)), None)
        if match:
            return match
    return None


def _camera(scene: dict[str, Any], shot: dict[str, Any]) -> str:
    """How the camera behaves, in words: the shot's own, else its catalog move's (CT-0027)."""

    ids = {camera["id"] for camera in (scene.get("geometry") or {}).get("cameras", [])}
    text = shot.get("camera_text") or ""
    if text and text not in ids and text != shot.get("camera"):
        return text
    return str((shot.get("move") or {}).get("prompt") or "")


def avoidance(production: dict[str, Any], scene: dict[str, Any], shots: list[dict[str, Any]]) -> list[str]:
    """What a generation must not do: the production's, the scene's and each shot's, in that order, once each."""

    seen: list[str] = []
    for item in [*(production.get("avoid") or []), *(scene.get("avoid") or []),
                 *[entry for shot in shots for entry in shot.get("avoid") or []]]:
        if item.lower() not in {existing.lower() for existing in seen}:
            seen.append(item)
    return seen


def _acting(production: dict[str, Any], scene: dict[str, Any], shot: dict[str, Any]) -> list[str]:
    """Each feeling the shot names, as what the model should show (CT-0048)."""

    acting = []
    for item in shot.get("emotion") or []:
        who = _voice(production, scene, item["who"])[0] if item.get("who") else ""
        acting.append(f"{who}: {item['ask']}" if who else item["ask"])
    return acting


def _voice(production: dict[str, Any], scene: dict[str, Any], who: str) -> tuple[str, str]:
    """(how to refer to the speaker, the voice) from the cast sheet, else the scene."""

    key = cast_key(who)
    member = next((m for m in (production.get("cast") or {}).values()
                   if key in {cast_key(n) for n in [m["id"], m["label"], *m.get("names", [])]}), None)
    refer = {cast_key(k): str(v) for k, v in (scene.get("refer_as") or {}).items()}.get(key) or who.title()
    state = {cast_key(k): str(v) for k, v in (scene.get("voice_state") or {}).items()}.get(key, "")
    # The nearest wins, as for looks and styles: a voice the scene restates is the voice in this scene
    # (the check still asks the author to keep only the state there); else the sheet's identity.
    identity = {cast_key(k): str(v) for k, v in (scene.get("voices") or {}).items()}.get(key, "")
    if not identity:
        identity = ((member or {}).get("voice") or {}).get("described", "")
    voice = f"{identity}; now {state}" if identity and state else (identity or state)
    return refer, " ".join(voice.split())


def hourly_rate(root: Path, endpoint: str) -> float:
    """The production's declared price for the endpoint, else the provider's assumed one."""

    from .project import _read_yaml

    rates = _read_yaml(root / "project.yaml").get("generation_rates") or {}
    return float(rates.get(endpoint, HOURLY_RATE_USD))


def plan_shot(root: Path, production: dict[str, Any], scene_id: str, shot_id: str, seed: int = 1,
              rate: float = HOURLY_RATE_USD) -> BlockPlan:
    """One shot outside any block, planned as a generation of its own; its result is a take."""

    return plan_block(root, production, scene_id, "", seed=seed, rate=rate, shot_id=shot_id)


def plan_block(root: Path, production: dict[str, Any], scene_id: str, block_id: str, seed: int = 1,
               rate: float = HOURLY_RATE_USD, shot_id: str = "") -> BlockPlan:
    """Everything one generation of the block (or of one shot) will be given, and what it should cost."""

    import math

    from .blocks import Block

    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        raise ValidationError(f"No scene {scene_id!r}")
    work = work_directory_for(root / scene["file"])
    early_notes: list[str] = []
    if shot_id:
        shot = next((item for item in scene["shots"] if item["id"] == shot_id), None)
        if shot is None:
            raise ValidationError(f"{scene_id} has no shot {shot_id!r}")
        if shot.get("block"):
            raise ValidationError(f"{shot_id} is part of block {shot['block']}: generate the block, so its shots "
                                  "keep one light and one room")
        wanted = float(shot.get("generated_seconds") or shot.get("duration_seconds") or 0)
        if wanted <= 0:
            raise ValidationError(f"{shot_id} has no duration to generate")
        whole = max(1, math.ceil(wanted))
        if whole != wanted:
            early_notes.append(f"{shot_id} runs {wanted:g} s; LTX 2.5 generates whole seconds, so {whole} s "
                               "are asked for and the cut trims the rest.")
        block = Block(shot_id, [shot_id], [float(whole)])
    else:
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
    notes: list[str] = list(early_notes)
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
        feelings = {cast_key(item["who"]): item for item in shot.get("emotion") or [] if item.get("who")}
        lines = []
        for line in shot.get("lines") or []:
            if not line.get("in_take", True):
                continue
            refer, voice = _voice(production, scene, line.get("who", ""))
            voice = line.get("voice") or voice
            # A line without its own delivery is spoken as the speaker feels (CT-0048).
            manner = line.get("delivery") or (feelings.get(cast_key(line.get("who", ""))) or {}).get("voice", "")
            lines.append(Line(refer, line.get("en") or line.get("text") or "", manner, voice))
        sound = shot.get("sound")
        prompts.append(ShotPrompt(picture, _camera(scene, shot), shot.get("description") or "", lines,
                                  sound if isinstance(sound, str) else "", _acting(production, scene, shot),
                                  str(shot.get("holds") or "setting")))
    # The style in force reaches the model in words of craft, never a name (CT-0049).
    style = (scene.get("style") or {}).get("prompt", "")
    frames = requested_cuts(block.durations, FPS)
    # Frame 0 is guided with the first picture too: alone, the first image gives
    # way in a long block (claim frame-zero-guide); each later shot's picture
    # guides its cut (claim keyframe-guides).
    # A shot may ask for its guide's strength, or for no guide at its cut
    # (SINGULAR's `forca_corte` and `guia_no_corte`).
    def strength(shot_id: str) -> float:
        value = shots[shot_id].get("guide_strength")
        return float(value) if value not in (None, "") else GUIDE_STRENGTH

    guides = [Reference("first", references[0], 0, _digest(references[0]), strength(block.shots[0]))]
    for shot_id, ref, frame in zip(block.shots[1:], references[1:], frames[1:]):
        if shots[shot_id].get("guide_at_cut") is False:
            notes.append(f"{shot_id} asks for no guide at its cut; the model finds that shot by the prompt alone.")
            continue
        guides.append(Reference(shot_id, ref, frame, _digest(ref), strength(shot_id)))
    from .providers.ltx import AVOID_MECHANISM, negative_text

    avoid = avoidance(production, scene, [shots[shot_id] for shot_id in block.shots])
    from .continuity import describe, state_at

    continuity = describe(state_at(production, scene_id, block.shots[0]), scene_id)
    return BlockPlan(
        continuity=continuity,
        avoid=avoid, negative=negative_text(avoid), avoid_mechanism=AVOID_MECHANISM,
        scene=scene_id, block=block.id, shots=block.shots, seconds=int(seconds), image=references[0],
        guides=guides, prompt=block_prompt(prompts, style), seed=seed, estimate_usd=estimate(seconds, rate), notes=notes,
        sections=[{"shot": shot_id, "text": text}
                  for shot_id, text in zip([*block.shots, ""], block_prompt_sections(prompts, style))],
    )
