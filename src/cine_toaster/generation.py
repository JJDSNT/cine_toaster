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


def _anchor_strength(production: dict[str, Any], scene_id: str, shot: dict[str, Any]) -> float:
    """`clips.anchor_end`: a strength, or a map of `SC-xxx Pn` to strengths, for shots held to their own picture."""

    value = (production.get("clips") or {}).get("anchor_end")
    if isinstance(value, dict):
        value = value.get(f"{scene_id} {shot['id']}")
    try:
        return float(value) if value else 0.0
    except (TypeError, ValueError):
        return 0.0


#: The frame (a multiple of 8) by which a chained scene has become its own first picture.
CHAIN_ARRIVAL_FRAME = 48


def entry_chain(root: Path, production: dict[str, Any], scene: dict[str, Any], shot_id: str) -> dict[str, Any] | None:
    """The last frame of the previous scene, when this scene starts on it (`clips: {chain_entries: true}`).

    SINGULAR measured it (claim last-frame-chaining): a stretch generated from
    the last frame of the one before joins invisibly. A scene entered on action
    or on a match begins on that frame and becomes its own first picture -- and
    its style -- within its first two seconds, in the motion (Demo 01: ending on
    the next scene's picture made Lia leave the frame to reach it).
    """

    from .blocks import last_frame

    if not (production.get("clips") or {}).get("chain_entries"):
        return None
    if str((scene.get("enter") or {}).get("type") or "") not in ("action", "match"):
        return None
    moving = [shot for shot in scene["shots"] if shot.get("kind") != "title" and shot.get("source") != "composed"]
    if not moving or moving[0]["id"] != shot_id:
        return None
    sequence = next((item for item in production.get("sequences") or [] if scene["id"] in (item.get("scene_ids") or [])),
                    None)
    order = list((sequence or {}).get("scene_ids") or [])
    if scene["id"] not in order or order.index(scene["id"]) == 0:
        return None
    previous = next((item for item in production["scenes"] if item["id"] == order[order.index(scene["id"]) - 1]), None)
    before = [shot for shot in (previous or {}).get("shots", []) if shot.get("kind") != "title"
              and shot.get("source") != "composed"]
    if not before:
        return None
    work = work_directory_for(root / previous["file"])
    frame = _kept_end(root, work, before[-1]) or last_frame(work, root, previous, str(before[-1]["number"]))
    if frame is not None and not frame.is_relative_to(root):
        # Kept beside the clip, inside the film (SINGULAR's `p<n>-ultimo.png`): the chained scene's start is a
        # production input with an address, not a cache file.
        import shutil

        from .blocks import _picture_stems

        kept = work / f"{_picture_stems(str(before[-1]['number']))[-1]}-ultimo.png"
        shutil.copyfile(frame, kept)
        frame = kept
    if frame is None:
        raise ValidationError(f"{scene['id']} starts on the last frame of {previous['id']} {before[-1]['id']}, "
                              "which has no chosen take yet: generate and choose it first")
    style = (scene.get("style") or {}).get("prompt", "")
    text = ("It begins exactly on the previous moment and continues its motion without a stop; within the first "
            "two seconds the whole drawing transforms, in the motion, into this frame's look"
            + (f": {style.split('.')[0].strip()}" if style else "") + ".")
    return {"scene": previous["id"], "shot": before[-1]["id"], "frame": frame, "text": text}


def _kept_end(root: Path, work: Path, shot: dict[str, Any]) -> Path | None:
    """The last frame the cut keeps of a trimmed shot: a chain starts where the film is, not where the take ends.

    Demo 01: SC-040 was trimmed at the white of the spray, but its take ran on into an artefact, and SC-050
    began on the artefact.
    """

    import shutil
    import subprocess

    trim = shot.get("trim") or {}
    if not ("tail" in trim or "out" in trim):
        return None
    take = next((item for item in shot.get("takes") or [] if item.get("id") == shot.get("selected_take")), None)
    if not take or not take.get("media") or not shutil.which("ffmpeg"):
        return None
    clip = root / take["media"]
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
                           capture_output=True, text=True)
    try:
        length = float(probe.stdout.strip())
    except ValueError:
        return None
    end = float(trim["out"]) if "out" in trim else length - float(trim["tail"])
    from .blocks import _picture_stems

    kept = work / f"{_picture_stems(str(shot['number']))[-1]}-ultimo.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(end - 0.05, 0):.3f}", "-i", str(clip),
                    "-frames:v", "1", str(kept)], check=False, timeout=120)
    return kept if kept.is_file() else None


#: How strongly a bridge's last frame is held to the next scene's first master.
BRIDGE_STRENGTH = 1.0


def entry_bridge(root: Path, production: dict[str, Any], scene: dict[str, Any], shot_id: str) -> dict[str, Any] | None:
    """The next scene's first master, when this shot ends a scene and the next is entered on action (Demo 01).

    A film that asks for it (`clips: {end_on_entry: true}`) has the last shot of
    each scene guided at its last frame by the master of the shot that enters
    the next scene on action or on a match -- so the cut, and a change of style
    across it, happens inside one generated motion instead of between two clips.
    """

    from .blocks import reference_picture

    clips = production.get("clips") or {}
    if not clips.get("end_on_entry") or clips.get("chain_entries"):
        return None
    if not scene["shots"] or scene["shots"][-1]["id"] != shot_id:
        # The last shot that makes a picture: a title or a card after it does not move.
        moving = [shot for shot in scene["shots"] if shot.get("kind") != "title" and shot.get("source") != "composed"]
        if not moving or moving[-1]["id"] != shot_id:
            return None
    sequence = next((item for item in production.get("sequences") or [] if scene["id"] in (item.get("scene_ids") or [])),
                    None)
    order = list((sequence or {}).get("scene_ids") or [])
    if scene["id"] not in order or order.index(scene["id"]) + 1 >= len(order):
        return None
    following = next((item for item in production["scenes"] if item["id"] == order[order.index(scene["id"]) + 1]), None)
    if not following or str((following.get("enter") or {}).get("type") or "") not in ("action", "match"):
        return None
    first = next((shot for shot in following["shots"] if shot.get("kind") != "title"), None)
    if first is None:
        return None
    picture = reference_picture(work_directory_for(root / following["file"]), root, following, first)
    if picture is None:
        return None
    style = (following.get("style") or {}).get("prompt", "")
    # Measured on Demo 01 (SC-040 P2 v1): told only to transform, the model let Lia fall out of the frame and
    # held the end picture still for half the clip. The person stays, moving, and arrives in the next pose.
    text = ("Everyone in the frame stays in the frame and keeps moving the whole time, arriving at the very end in "
            "exactly the pose of the next frame. Without stopping the motion, during the second half the whole "
            "image gradually transforms into the next frame's drawing"
            + (f": {style.split('.')[0].strip()}" if style else "") + ".")
    return {"scene": following["id"], "shot": first["id"], "picture": picture, "text": text}


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
    bridge = entry_bridge(root, production, scene, block.shots[-1])
    chain = entry_chain(root, production, scene, block.shots[0])
    for shot_id in block.shots:
        shot = shots[shot_id]
        source = _from_shot(scene, shot)
        picture = shot.get("picture") or (source or {}).get("picture") or ""
        if not picture:
            notes.append(f"{shot_id} has no picture description (`picture`); the prompt names only its action"
                         " -- the start image shows the rest.")
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
        # The action: the shot's description, else its breakdown label -- the one line every breakdown has
        # (Demo 01's shots said what happens only there, and the prompt said nothing of it).
        action = shot.get("description") or ("" if shot.get("label") == shot_id else shot.get("label") or "")
        if bridge and shot_id == block.shots[-1]:
            action = (action + " " + bridge["text"]).strip()
        if chain and shot_id == block.shots[0]:
            action = (chain["text"] + " " + action).strip()
        prompts.append(ShotPrompt(picture, _camera(scene, shot), action, lines,
                                  sound if isinstance(sound, str) else "", _acting(production, scene, shot),
                                  "bridge" if bridge and shot_id == block.shots[-1]
                                  else str(shot.get("holds") or "setting"),
                                  str((shot.get("cut") or {}).get("type") or "hard")))
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
    if chain:
        # Start on the previous scene's last frame; arrive at this scene's first picture two seconds in.
        guides = [Reference("chained", chain["frame"], 0, _digest(chain["frame"]), 1.0),
                  Reference(block.shots[0], references[0], CHAIN_ARRIVAL_FRAME, _digest(references[0]),
                            strength(block.shots[0]))]
        notes.append(f"Starts on the last frame of {chain['scene']} {chain['shot']} (chain_entries) and becomes "
                     f"{block.shots[0]}'s picture by frame {CHAIN_ARRIVAL_FRAME}.")
    for shot_id, ref, frame in zip(block.shots[1:], references[1:], frames[1:]):
        if shots[shot_id].get("guide_at_cut") is False:
            notes.append(f"{shot_id} asks for no guide at its cut; the model finds that shot by the prompt alone.")
            continue
        guides.append(Reference(shot_id, ref, frame, _digest(ref), strength(shot_id)))
    anchor = _anchor_strength(production, scene_id, shots[block.shots[-1]])
    if anchor and not bridge:
        # The shot ends held to its own picture: measured on Demo 01 (SC-070 P2), a wide hold drifted into another
        # person's close-up twice; its own master at the last frame keeps who and where it is.
        guides.append(Reference("anchor", references[-1], -1, _digest(references[-1]), anchor))
        notes.append(f"Ends anchored to its own picture at strength {anchor} (clips.anchor_end).")
    if bridge:
        # Full strength: a bridge must land on the next scene's first picture (0.7 let it drift, Demo 01).
        guides.append(Reference("end", bridge["picture"], -1, _digest(bridge["picture"]), BRIDGE_STRENGTH))
        notes.append(f"Ends on {bridge['scene']} {bridge['shot']}'s master (its entry is on action): the clip carries "
                     "the cut and the change of style inside the motion.")
    from .providers.ltx import AVOID_MECHANISM, negative_text

    avoid = avoidance(production, scene, [shots[shot_id] for shot_id in block.shots])
    from .continuity import describe, state_at

    continuity = describe(state_at(production, scene_id, block.shots[0]), scene_id)
    return BlockPlan(
        continuity=continuity,
        avoid=avoid, negative=negative_text(avoid), avoid_mechanism=AVOID_MECHANISM,
        scene=scene_id, block=block.id, shots=block.shots, seconds=int(seconds),
        image=chain["frame"] if chain else references[0],
        guides=guides, prompt=block_prompt(prompts, style), seed=seed, estimate_usd=estimate(seconds, rate), notes=notes,
        sections=[{"shot": shot_id, "text": text}
                  for shot_id, text in zip([*block.shots, ""], block_prompt_sections(prompts, style))],
    )
