from __future__ import annotations

import base64
import copy
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import ValidationError
from . import GenerationResult, ProviderError, ProviderNotConfigured
from .comfyui import load_workflow
from .runpod import Transport, run_job


WORKFLOW = Path(__file__).with_name("workflows") / "ltx25_i2v_api.json"
HOURLY_RATE_USD = 1.75
MODEL = "ltx-2.5"
FPS = 24
MAX_SECONDS = 20

# Node ids from the exported graph. They are stable for this workflow file and
# change only when the file is re-exported, which is why the file ships with the
# provider instead of being fetched from a project.
NODES = {
    "prompt": "398:376",
    "image": "395",
    "duration": "398:362",
    "width": "398:372",
    "height": "398:360",
    "fps": "398:361",
    "enhance": "398:380",
    "enhance_on": "398:383",
    "seed_base": "398:338",
    "seed_refine": "398:339",
    "negative": "398:373",
}

NEGATIVE_PROMPT = (
    "pc game, console game, video game, cartoon, childish, ugly, text, subtitles, "
    "watermark, music, background music, distorted face, morphing face, extra fingers"
)

ID_LORA = "ltx-2.3-id-lora-talkvid-3k.safetensors"
CONTROL_LORA = "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"

# The control LoRA halves the guide on the half-resolution pass, so the height
# must be a multiple of 128. 704 fails outright.
CONTROL_RESOLUTION = (1408, 768)

MEDIA_TYPES = {".wav": "data:audio/wav", ".mp4": "data:video/mp4"}


@dataclass(frozen=True, slots=True)
class Guide:
    """A keyframe beyond the first.

    Asking for a state in words does not reliably produce it; supplying an image
    of that state does. `frame` is -1 for the last frame, otherwise a multiple of
    8, because the VAE compresses eight frames into one latent.
    """

    image: Path
    frame: int
    strength: float = 0.7

    def __post_init__(self) -> None:
        if self.frame != -1 and self.frame % 8:
            raise ValidationError(
                f"Guide frame {self.frame} must be -1 or a multiple of 8",
                frame=self.frame,
            )


def _apply_guides(workflow: dict[str, Any], guides: list[Guide]) -> None:
    """Wire extra keyframes into both sampling passes.

    Guides enter the video latent before the audio latent is joined, because the
    node does not accept a combined latent, and are removed with LTXVCropGuides
    after each pass. Strength applies as given on the base pass and scaled on the
    refine pass, matching the official ComfyUI template (0.7 base, 1.0 refine).
    """

    prepared = []
    for index, guide in enumerate(guides):
        workflow[f"g{index}:load"] = {
            "class_type": "LoadImage",
            "inputs": {"image": f"guide{index}.png"},
        }
        workflow[f"g{index}:resize"] = {
            "class_type": "ResizeImageMaskNode",
            "inputs": {**workflow["398:351"]["inputs"], "input": [f"g{index}:load", 0]},
        }
        workflow[f"g{index}:pre"] = {
            "class_type": "LTXVPreprocess",
            "inputs": {"image": [f"g{index}:resize", 0], "img_compression": 18},
        }
        prepared.append([f"g{index}:pre", 0])

    passes = [
        (["398:357", 0], "398:377", "398:388", "398:367", "398:348", "samples"),
        (["398:349", 0], "398:340", "398:391", "398:369", "398:374", "samples"),
    ]
    for pass_index, (latent_in, concat, guider, split, target, key) in enumerate(passes):
        positive, negative, latent = ["398:365", 0], ["398:365", 1], latent_in
        for index, guide in enumerate(guides):
            strength = guide.strength if pass_index == 0 else min(1.0, guide.strength / 0.7)
            node = f"g{index}:guide{pass_index + 1}"
            workflow[node] = {
                "class_type": "LTXVAddGuide",
                "inputs": {
                    "positive": positive,
                    "negative": negative,
                    "vae": ["398:385", 0],
                    "latent": latent,
                    "image": prepared[index],
                    "frame_idx": guide.frame,
                    "strength": round(strength, 3),
                },
            }
            positive, negative, latent = [node, 0], [node, 1], [node, 2]
        workflow[concat]["inputs"]["video_latent"] = latent
        workflow[guider]["inputs"]["positive"] = positive
        workflow[guider]["inputs"]["negative"] = negative
        crop = f"g:crop{pass_index + 1}"
        workflow[crop] = {
            "class_type": "LTXVCropGuides",
            "inputs": {"positive": positive, "negative": negative, "latent": [split, 0]},
        }
        workflow[target]["inputs"][key] = [crop, 2]


def _apply_identity_lora(workflow: dict[str, Any], strength: float = 1.0, guidance: float = 3.0) -> None:
    """Lock face and voice without training.

    The face comes from the first frame and the voice from about five seconds of
    reference audio. The LoRA is from LTX 2.3; the vendor states most 2.3 LoRAs
    run on 2.5, which is what this measures in practice.
    """

    workflow["id:lora"] = {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {"model": ["398:384", 0], "lora_name": ID_LORA, "strength_model": strength},
    }
    workflow["id:audio"] = {"class_type": "LoadAudio", "inputs": {"audio": "voice.wav"}}
    workflow["id:voice"] = {
        "class_type": "LTXVReferenceAudio",
        "inputs": {
            "model": ["id:lora", 0],
            "positive": ["398:364", 0],
            "negative": ["398:373", 0],
            "reference_audio": ["id:audio", 0],
            "audio_vae": ["398:386", 0],
            "identity_guidance_scale": guidance,
            "start_percent": 0.0,
            "end_percent": 1.0,
        },
    }
    workflow["398:365"]["inputs"]["positive"] = ["id:voice", 1]
    workflow["398:365"]["inputs"]["negative"] = ["id:voice", 2]
    workflow["398:388"]["inputs"]["model"] = ["id:voice", 0]
    workflow["398:391"]["inputs"]["model"] = ["id:lora", 0]


def _apply_control_video(workflow: dict[str, Any], strength: float = 0.7) -> None:
    """Drive geometry, camera and motion from a control video.

    The first frame still decides appearance; the control video decides where
    things are and how they move. It must have the same frame count as the clip
    (24·s+1) and the same aspect ratio. Strength 1 follows the 3D exactly;
    0.5–0.8 guides more loosely.
    """

    workflow["ic:lora"] = {
        "class_type": "LTXICLoRALoaderModelOnly",
        "inputs": {
            "model": workflow["398:388"]["inputs"]["model"],
            "lora_name": CONTROL_LORA,
            "strength_model": 1.0,
        },
    }
    workflow["398:388"]["inputs"]["model"] = ["ic:lora", 0]
    workflow["ic:video"] = {"class_type": "LoadVideo", "inputs": {"file": "control.mp4"}}
    workflow["ic:frames"] = {
        "class_type": "GetVideoComponents",
        "inputs": {"video": ["ic:video", 0]},
    }
    guider = workflow["398:388"]["inputs"]
    workflow["ic:guide"] = {
        "class_type": "LTXAddVideoICLoRAGuide",
        "inputs": {
            "positive": guider["positive"],
            "negative": guider["negative"],
            "vae": ["398:385", 0],
            "latent": workflow["398:377"]["inputs"]["video_latent"],
            "image": ["ic:frames", 0],
            "frame_idx": 0,
            "strength": round(strength, 3),
            "latent_downscale_factor": ["ic:lora", 1],
            "crop": "disabled",
            "use_tiled_encode": False,
            "tile_size": 256,
            "tile_overlap": 64,
        },
    }
    workflow["398:377"]["inputs"]["video_latent"] = ["ic:guide", 2]
    guider["positive"], guider["negative"] = ["ic:guide", 0], ["ic:guide", 1]
    if "g:crop1" in workflow:
        # Keyframes already crop; the same crop removes this guide too.
        workflow["g:crop1"]["inputs"]["positive"] = ["ic:guide", 0]
        workflow["g:crop1"]["inputs"]["negative"] = ["ic:guide", 1]
    else:
        workflow["ic:crop"] = {
            "class_type": "LTXVCropGuides",
            "inputs": {
                "positive": ["ic:guide", 0],
                "negative": ["ic:guide", 1],
                "latent": ["398:367", 0],
            },
        }
        workflow["398:348"]["inputs"]["samples"] = ["ic:crop", 2]


def build_request(
    *,
    image: Path,
    seconds: int,
    prompt: str,
    seed: int,
    enhance: bool = False,
    width: int = 1280,
    height: int = 720,
    guides: tuple[Guide, ...] = (),
    reference_voice: Path | None = None,
    control_video: tuple[Path, float] | None = None,
) -> dict[str, Any]:
    """Assemble the graph and the files that travel with it."""

    if not 1 <= seconds <= MAX_SECONDS or int(seconds) != seconds:
        raise ValidationError(f"Duration must be a whole number of seconds, 1 to {MAX_SECONDS}")

    workflow = copy.deepcopy(load_workflow(WORKFLOW))
    workflow[NODES["prompt"]]["inputs"]["value"] = " ".join(prompt.split())
    workflow[NODES["image"]]["inputs"]["image"] = "frame.png"
    workflow[NODES["duration"]]["inputs"]["value"] = int(seconds)
    workflow[NODES["width"]]["inputs"]["value"] = width
    workflow[NODES["height"]]["inputs"]["value"] = height
    workflow[NODES["fps"]]["inputs"]["value"] = FPS
    # The prompt enhancer rewrites the prompt, and a written breakdown is already
    # specific. Off by default: enhancement trades direction for cliché.
    workflow[NODES["enhance"]]["inputs"]["sampling_mode"] = "on" if enhance else "off"
    workflow[NODES["enhance"]]["inputs"]["sampling_mode.seed"] = seed % 10**9 or 1
    workflow[NODES["enhance_on"]]["inputs"]["value"] = enhance
    workflow[NODES["negative"]]["inputs"]["text"] = NEGATIVE_PROMPT

    stream = random.Random(seed)
    workflow[NODES["seed_base"]]["inputs"]["noise_seed"] = stream.randrange(1, 10**15)
    workflow[NODES["seed_refine"]]["inputs"]["noise_seed"] = stream.randrange(1, 10**15)

    files: list[tuple[str, Path]] = [("frame.png", image)]
    files += [(f"guide{index}.png", guide.image) for index, guide in enumerate(guides)]
    if guides:
        _apply_guides(workflow, list(guides))
    if reference_voice is not None:
        _apply_identity_lora(workflow)
        files.append(("voice.wav", reference_voice))
    if control_video is not None:
        video, strength = control_video
        workflow[NODES["width"]]["inputs"]["value"] = CONTROL_RESOLUTION[0]
        workflow[NODES["height"]]["inputs"]["value"] = CONTROL_RESOLUTION[1]
        _apply_control_video(workflow, strength)
        files.append(("control.mp4", video))

    return {
        "workflow": workflow,
        "images": [
            {
                "name": name,
                "image": MEDIA_TYPES.get(path.suffix.lower(), "data:image/png")
                + ";base64,"
                + base64.b64encode(path.read_bytes()).decode(),
            }
            for name, path in files
        ],
    }


def find_video(output: dict[str, Any]) -> str | None:
    """Locate the video in a worker response.

    Workers return it under `videos` or `images`, sometimes with no filename, so
    it is recognised by the MP4 header rather than by where it was filed.
    """

    if isinstance(output.get("output"), dict):
        output = output["output"]
    for key in ("videos", "images"):
        for item in output.get(key) or []:
            data = item if isinstance(item, str) else (
                item.get("data") or item.get("video") or item.get("base64")
            )
            if not data:
                continue
            head = base64.b64decode(data.split(",", 1)[-1][:64] + "==")
            if b"ftyp" in head[:16]:
                return data
    return None


class LtxProvider:
    """LTX 2.5 image-to-video, with sound, on a Runpod serverless endpoint.

    What this model obeys and what it inverts is recorded as data, not folklore:
    see `knowledge/providers/ltx-2-5.md` in the production, which carries each
    claim with its measurement date.
    """

    id = "ltx-2-5"
    model = MODEL

    def __init__(self, endpoint_id: str | None = None, *, transport: Transport | None = None) -> None:
        self.endpoint_id = endpoint_id or os.environ.get("RUNPOD_LTX_ENDPOINT_ID", "")
        self.transport = transport

    def generate(
        self,
        *,
        image: Path,
        output: Path,
        seconds: int,
        prompt: str,
        seed: int = 1,
        guides: tuple[Guide, ...] = (),
        reference_voice: Path | None = None,
        control_video: tuple[Path, float] | None = None,
        label: str = "ltx",
        enhance: bool = False,
    ) -> GenerationResult:
        if not self.endpoint_id:
            raise ProviderNotConfigured("RUNPOD_LTX_ENDPOINT_ID is not set")

        payload = build_request(
            image=image,
            seconds=seconds,
            prompt=prompt,
            seed=seed,
            enhance=enhance,
            guides=guides,
            reference_voice=reference_voice,
            control_video=control_video,
        )
        result = run_job(
            self.endpoint_id,
            payload,
            state_file=output.with_suffix(output.suffix + ".job.json"),
            label=label,
            transport=self.transport,
        )
        data = find_video(result)
        if not data:
            raise ProviderError(
                f"{label}: the worker returned no video",
                endpoint=self.endpoint_id,
            )

        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_bytes(base64.b64decode(data.split(",", 1)[-1]))
        os.replace(temporary, output)

        return GenerationResult(
            media=output,
            provider=self.id,
            model=MODEL,
            seed=seed,
            duration_seconds=float(seconds),
            provenance={
                "endpoint": self.endpoint_id,
                "fps": FPS,
                "enhance": enhance,
                "guides": [
                    {"frame": guide.frame, "strength": guide.strength} for guide in guides
                ],
                "identity_lora": ID_LORA if reference_voice else None,
                "control_lora": CONTROL_LORA if control_video else None,
            },
        )


__all__ = ["Guide", "LtxProvider", "build_request", "find_video", "HOURLY_RATE_USD", "MODEL"]
