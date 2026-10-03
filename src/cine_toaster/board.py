"""The 3D storyboard: still boards to compose from, and an animatic to check the scene (CT-0049).

Built from the scene's plan exported as USD (`usd_export`), rendered by
Blender in a board's look. Two products, kept apart on purpose:

- **boards**: one still per shot (its start, and its end if asked), with a
  depth map. A board fixes composition -- where the camera stands, the
  lens, where people and things are -- and is a starting picture for a
  master image (`derive: {from: board}`). It carries no motion.
- **the animatic**: the whole scene played through each shot's camera,
  to check the screenplay and the breakdown -- timing, sides, who is in
  frame. It is for people to watch; nothing of it is given to a video model,
  whose movement stays described in words.

Both are derived: written under `renders/boards/<scene>/`, redrawn when
asked, never the record.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .errors import ValidationError

SCRIPT = Path(__file__).with_name("vfx_assets") / "_blender" / "board.py"
FPS = 24


def board_path(root: Path, scene_id: str, shot_id: str, moment: str = "start") -> Path:
    return root / "renders" / "boards" / scene_id / f"{shot_id}-{moment}.png"


def _stage(scene: dict[str, Any], work: Path) -> tuple[Path, list[dict[str, Any]]]:
    from .usd_export import export

    stage = work / f"{scene['id']}.usda"
    summary = export(scene, stage)
    return stage, summary["shots"]


def _run(spec: dict[str, Any], work: Path) -> None:
    from .titles import blender_binary

    blender = blender_binary()
    if not blender:
        raise ValidationError("The 3D storyboard is rendered by Blender, which is not found")
    path = work / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    completed = subprocess.run([blender, "--background", "--factory-startup", "--python", str(SCRIPT), "--",
                                str(path)], capture_output=True, text=True, timeout=3600)
    if completed.returncode != 0 or "Traceback" in completed.stdout + completed.stderr:
        raise ValidationError("Blender could not draw the boards", detail=(completed.stdout + completed.stderr)[-800:])


def _depth_png(exr: Path, png: Path) -> None:
    """The depth pass as a 16-bit picture: near is bright, far is dark (the convention depth guides use)."""

    import numpy as np
    import OpenEXR
    from PIL import Image

    with OpenEXR.File(str(exr)) as file:
        depth = next(np.asarray(channel.pixels, dtype=np.float32) for part in file.parts
                     for name, channel in part.channels.items() if name.endswith("Depth.Z"))
    finite = np.isfinite(depth) & (depth < 1e6)
    near, far = (float(depth[finite].min()), float(depth[finite].max())) if finite.any() else (0.0, 1.0)
    scaled = np.where(finite, 1.0 - (depth - near) / max(1e-6, far - near), 0.0)
    Image.fromarray((np.clip(scaled, 0, 1) * 65535).astype(np.uint16)).save(png)


def boards(root: Path, scene: dict[str, Any], *, shots: list[str] | None = None, ends: bool = False,
           width: int = 1280, height: int = 720, look: str = "clay") -> list[dict[str, Any]]:
    """Draw the boards of a scene's shots (all, or `shots`); returns what was written."""

    import tempfile

    with tempfile.TemporaryDirectory(prefix="boards-") as scratch:
        work = Path(scratch)
        stage, timeline = _stage(scene, work)
        wanted = [item for item in timeline if not shots or item["shot"] in shots]
        if not wanted:
            raise ValidationError(f"{scene['id']} has no shot with a camera to board" +
                                  (f" among {', '.join(shots)}" if shots else ""))
        stills = []
        for item in wanted:
            stills.append({"name": f"{item['shot']}-start", "camera": item["shot"], "frame": item["first_frame"]})
            if ends:
                stills.append({"name": f"{item['shot']}-end", "camera": item["shot"],
                               "frame": item["first_frame"] + item["frames"] - 1})
        _run({"usd": str(stage), "output": str(work / "out"), "width": width, "height": height, "stills": stills,
              "look": look}, work)
        made = []
        for still in stills:
            shot_id, moment = still["name"].rsplit("-", 1)
            target = board_path(root, scene["id"], shot_id, moment)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(work / "out" / f"{still['name']}.png", target)
            _depth_png(work / "out" / f"{still['name']}.exr", target.with_name(f"{target.stem}-depth.png"))
            # What the board was drawn from, to tell later when the plan has moved on.
            target.with_suffix(".json").write_text(json.dumps({"fingerprint": fingerprint(scene), "shot": shot_id,
                                                               "moment": moment}), encoding="utf-8")
            made.append({"shot": shot_id, "moment": moment, "board": str(target),
                         "depth": str(target.with_name(f"{target.stem}-depth.png"))})
    return made


def animatic(root: Path, scene: dict[str, Any], *, width: int = 960, height: int = 540, step: int = 2) -> Path:
    """The scene played through its shots' cameras, for people to check; returns the video."""

    import tempfile

    ffmpeg = shutil.which("ffmpeg")
    with tempfile.TemporaryDirectory(prefix="animatic-") as scratch:
        work = Path(scratch)
        stage, timeline = _stage(scene, work)
        if not timeline:
            raise ValidationError(f"{scene['id']} has no shot with a camera to play")
        _run({"usd": str(stage), "output": str(work / "out"), "width": width, "height": height,
              "animatic": {"shots": [{"camera": item["shot"], "first": item["first_frame"], "frames": item["frames"]}
                                     for item in timeline], "step": step}}, work)
        output = root / "renders" / "boards" / scene["id"] / "animatic.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ffmpeg, "-v", "error", "-y", "-framerate", f"{FPS / step:g}", "-i",
                        str(work / "out" / "animatic" / "f_%04d.png"), "-vf", "format=yuv420p", "-c:v", "libx264",
                        "-crf", "20", str(output)], check=True)
    return output


def fingerprint(scene: dict[str, Any]) -> str:
    """What the boards depend on: the plan and the shots' moves (to tell when they are stale)."""

    relevant = {"geometry": scene.get("geometry"),
                "shots": [{"id": shot["id"], "motion": shot.get("motion"), "duration": shot.get("duration_seconds")}
                          for shot in scene.get("shots") or []]}
    return hashlib.sha256(json.dumps(relevant, sort_keys=True, default=str).encode()).hexdigest()[:16]


def stale(root: Path, scene: dict[str, Any], shot_id: str, moment: str = "start") -> bool:
    """Whether a board was drawn from a plan that has since changed."""

    record = board_path(root, scene["id"], shot_id, moment).with_suffix(".json")
    if not record.is_file():
        return False
    return json.loads(record.read_text(encoding="utf-8")).get("fingerprint") != fingerprint(scene)


#: One scale of shot sizes, measured the same way for every shot: how much of the frame's
#: height the followed subject would fill, head to feet (a close-up's figure runs far out of frame).
SIZES = (("EXTREME CLOSE-UP", 6.0), ("CLOSE-UP", 3.2), ("MEDIUM CLOSE-UP", 1.9), ("MEDIUM", 1.15),
         ("FULL", 0.75), ("WIDE", 0.3), ("EXTREME WIDE", 0.0))
SIZE_NAMES = [name for name, _ in SIZES]
#: Kinds of shot beside the size: two are measured, two must be declared (`framing:`).
FRAMINGS = ("TWO SHOT", "OVER SHOULDER", "INSERT", "POV")
ALIASES = {"ECU": "EXTREME CLOSE-UP", "CU": "CLOSE-UP", "MCU": "MEDIUM CLOSE-UP", "MS": "MEDIUM", "MID": "MEDIUM",
           "FS": "FULL", "FULL SHOT": "FULL", "LS": "WIDE", "WS": "WIDE", "LONG": "WIDE", "EWS": "EXTREME WIDE",
           "ELS": "EXTREME WIDE", "OTS": "OVER SHOULDER", "OVER THE SHOULDER": "OVER SHOULDER", "2-SHOT": "TWO SHOT"}


def canonical(value: Any) -> str:
    text = " ".join(str(value or "").upper().replace("_", " ").replace("-", " ").split())
    text = text.replace("CLOSE UP", "CLOSE-UP")
    return ALIASES.get(text, text)


def framing(scene: dict[str, Any], shot: dict[str, Any]) -> dict[str, str]:
    """A shot's size, measured on its blocking frame, and its kind (declared, or two shot/over shoulder seen).

    The size is always measured, so every shot of every scene is named by the
    same rule; a declared `size` is reported beside it, not instead of it.
    """

    from .blocking import blocking_frame, public_frame

    extra = shot.get("extra_fields") or {}
    declared_size = canonical(shot.get("size") or extra.get("size"))
    declared_kind = canonical(shot.get("framing") or extra.get("framing"))
    frame = blocking_frame(scene, shot, "start")
    measured, kind = "", ""
    if frame is not None:
        target = ((shot.get("motion") or {}).get("start") or {}).get("camera", {}).get("target_ref") or ""
        figures = [item for item in public_frame(frame)["figures"] if not item.get("behind")]
        followed = next((item for item in figures if item["subject"] == target and item.get("in_frame")), None)
        fraction = float(followed.get("height_fraction") or 0) if followed else 0.0
        measured = next(name for name, threshold in SIZES if fraction >= threshold) if followed else "WIDE"
        people = [item for item in figures if item.get("in_frame") and item.get("kind") != "object"]
        near_edge = [item for item in people if item["subject"] != target and item.get("depth", 99) < 1.6
                     and abs(item.get("x", 0)) > 0.45]
        if near_edge:
            kind = "OVER SHOULDER"
        elif len(people) >= 2 and SIZE_NAMES.index(measured) >= SIZE_NAMES.index("MEDIUM"):
            kind = "TWO SHOT"
    return {"size": measured, "declared_size": declared_size, "kind": declared_kind or kind}


def label(scene: dict[str, Any], shot: dict[str, Any], number: int | None = None) -> str:
    """`1 · WIDE · PUSH IN`: the number, the kind or the size, and the move when there is one."""

    measured = framing(scene, shot)
    parts = [str(number) if number is not None else shot["id"]]
    parts.append(measured["kind"] or measured["declared_size"] or measured["size"])
    move = (shot.get("move") or {}).get("id") or ""
    if move and move != "locked-off":
        parts.append(move.replace("-", " ").upper())
    return " · ".join(part for part in parts if part)


def shot_size(scene: dict[str, Any], shot: dict[str, Any]) -> str:
    return framing(scene, shot)["size"]


def sheet(root: Path, scene: dict[str, Any], *, columns: int = 3, tile: tuple[int, int] = (480, 270)) -> Path:
    """The scene's boards as one labelled grid, shot by shot, as a board wall is pinned up."""

    from PIL import Image, ImageDraw, ImageFont

    items = []
    for number, shot in enumerate(scene.get("shots") or [], 1):
        path = board_path(root, scene["id"], shot["id"])
        if path.is_file():
            items.append((number, shot, path))
    if not items:
        raise ValidationError(f"{scene['id']} has no boards yet (toast board frames)")
    width, height = tile
    rows = -(-len(items) // columns)
    gap = 12
    canvas = Image.new("RGB", (columns * (width + gap) + gap, rows * (height + gap) + gap + 40), (14, 15, 17))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
        heading = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
    except OSError:
        font = heading = ImageFont.load_default()
    draw.text((gap, 10), f"{scene['id']} · {scene.get('title') or ''}".upper(), fill=(220, 222, 224), font=heading)
    for index, (number, shot, path) in enumerate(items):
        x = gap + (index % columns) * (width + gap)
        y = 40 + gap + (index // columns) * (height + gap)
        canvas.paste(Image.open(path).convert("RGB").resize((width, height)), (x, y))
        text = label(scene, shot, number)
        box = draw.textbbox((0, 0), text, font=font)
        draw.rectangle((x + 8, y + height - 30, x + 20 + box[2], y + height - 8), fill=(20, 22, 26))
        draw.text((x + 14, y + height - 28), text, fill=(235, 236, 238), font=font)
    output = root / "renders" / "boards" / scene["id"] / "sheet.png"
    canvas.save(output)
    return output
