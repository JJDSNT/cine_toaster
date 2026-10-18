"""Master pictures, made by whichever adapter the production chooses (CT-0037; ADR 0025).

SINGULAR's method, measured on its scenes: the room is designed once in 3D
and rendered per camera; the people are then painted into that render by an
image editor that is told to keep the geometry, given each character's
sheet for identity. A shot declares it as `derive: {from, with, request}`.
That is one method, not the rule: the adapter is chosen by the cascade
`pictures: {provider}` in project.yaml -> the scene -> `derive.provider`, and
an adapter that composes (not only repaints) needs no `from`.

Nothing is replaced. The production's picture `p<n>.png` stays; each edit is
a version beside it (`p<n>-1.png`, `p<n>-2.png`…), with what it was made from
and how faithful its edges are to the source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .blocks import _picture_stems, reference_picture
from .cast import _digest, cast_key
from .errors import ValidationError
from .takes import shot_key, work_directory_for

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def relative(root: Path, path: Path) -> str:
    """A project-relative path, however either side was spelled."""

    return path.resolve().relative_to(root.resolve()).as_posix()


def edge_score(result: Path, source: Path) -> float:
    """How closely the result's edges match the source's (PSNR of edges; higher is more faithful).

    It says without looking whether the picture was repainted or recomposed,
    whatever made it: about 17 is good, SINGULAR's accepted edits scored 20.3-20.6.
    """

    import numpy as np
    from PIL import Image, ImageFilter

    def edges(path: Path):
        image = Image.open(path).convert("L").resize((640, 352)).filter(ImageFilter.FIND_EDGES)
        return np.asarray(image, dtype=float)

    mse = float(((edges(result) - edges(source)) ** 2).mean())
    return round(10 * float(np.log10(255 ** 2 / mse)), 2) if mse else 99.0


def picture_provider(production: dict[str, Any], scene: dict[str, Any] | None = None,
                     shot: dict[str, Any] | None = None) -> tuple[str, str]:
    """The adapter that makes this picture, and the level that chose it: the nearest wins."""

    from .providers import DEFAULT_PICTURE_PROVIDER, picture_providers

    def chosen(value: Any) -> str:
        return str(value.get("provider") or "") if isinstance(value, dict) else ""

    for level, value in (("shot", (shot or {}).get("derive")), ("scene", (scene or {}).get("pictures")),
                         ("production", production.get("pictures"))):
        if chosen(value):
            if chosen(value) not in picture_providers():
                raise ValidationError(f"No picture provider {chosen(value)!r} ({level}); there is "
                                      f"{', '.join(picture_providers())}")
            return chosen(value), level
    return DEFAULT_PICTURE_PROVIDER, "default"


@dataclass(slots=True)
class PicturePlan:
    scene: str
    shot: str
    stem: str
    source: Path | None
    references: list[dict[str, Any]]
    request: str
    prompt: str
    seed: int
    size: tuple[int, int] | None
    estimate_usd: float
    provider: str = "qwen-image-edit"
    provider_level: str = "default"
    model: str = "qwen-image-edit"
    #: "usd", held by the budget, or "quota", a subscription's: recorded, never priced.
    cost: str = "usd"
    notes: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    avoid_mechanism: str = ""
    #: What holds when the shot begins (the continuity ledger, CT-0059): shown to the author, not sent.
    continuity: list[str] = field(default_factory=list)

    def public_dict(self, root: Path) -> dict[str, Any]:
        return {
            "scene": self.scene, "shot": self.shot, "model": self.model, "provider": self.provider,
            "provider_level": self.provider_level, "cost": self.cost,
            "source": ({"path": relative(root, self.source), "digest": _digest(self.source)}
                       if self.source is not None else None),
            "references": [{**ref, "path": relative(root, ref["path"]), "digest": _digest(ref["path"])}
                           for ref in self.references],
            "request": self.request, "prompt": self.prompt, "seed": self.seed,
            "width": self.size[0] if self.size else None, "height": self.size[1] if self.size else None,
            "estimate_usd": self.estimate_usd, "notes": self.notes,
            "avoid": self.avoid, "avoid_mechanism": self.avoid_mechanism, "continuity": self.continuity,
        }


def picture_versions(work: Path, stem: str) -> list[Path]:
    """The shot's own picture, then each edit of it, in order."""

    if not work.is_dir():
        return []
    pattern = re.compile(rf"{re.escape(stem)}(?:-(\d+))?")
    found = []
    for path in work.iterdir():
        match = pattern.fullmatch(path.stem)
        if match and path.suffix.lower() in IMAGE_SUFFIXES and path.is_file():
            found.append((int(match[1] or 0), path))
    return [path for _, path in sorted(found)]


def adopt_drawing(root: Path, scene_id: str, shot_id: str, *, offset: float = 0.5) -> dict[str, Any]:
    """The shot's approved storyboard drawing as its next master version, fitted to the film's frame.

    When a drawing already is the picture (Demo 01: an image tool refused to
    redraw a deer it took for a protected character), it becomes a version
    beside the others -- cropped to the film's proportions, `offset` placing
    the window from the left (0) to the right (1) of what is cut -- with a
    record of where it came from. Nothing is generated; nothing is replaced.
    """

    import json

    from PIL import Image

    from .project import load_production
    from .storyboard import load_storyboard

    root = Path(root).expanduser().resolve()
    if not 0.0 <= float(offset) <= 1.0:
        raise ValidationError("offset is from 0 (keep the left) to 1 (keep the right)")
    production = load_production(root)
    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    shot = next((item for item in (scene or {}).get("shots", []) if item["id"] == shot_id), None)
    if shot is None:
        raise ValidationError(f"No shot {scene_id} {shot_id}")
    drawings = [item for item in load_storyboard(root)["candidates"] if item["scene"] == scene_id and item["shot"] == shot_id]
    drawing = max(drawings, key=lambda item: item.get("version") or 0, default=None)
    if drawing is None:
        raise ValidationError(f"{scene_id} {shot_id} has no storyboard drawing")
    source = root / drawing["image"]["path"]
    frame = production.get("frame") or {}
    target = (frame["width"] / frame["height"]) if frame.get("width") and frame.get("height") else 16 / 9
    work = work_directory_for(root / scene["file"])
    work.mkdir(parents=True, exist_ok=True)
    stem = picture_stem(work, str(shot["number"]))
    versions = picture_versions(work, stem)
    numbers = [int(m[1]) for path in versions if (m := re.fullmatch(rf"{re.escape(stem)}-(\d+)", path.stem))]
    output = work / f"{stem}-{max(numbers, default=0) + 1}.png"
    with Image.open(source) as image:
        width, height = image.size
        if width / height > target:  # wider: keep the full height, choose the columns
            new = round(height * target)
            left = round((width - new) * float(offset))
            box = (left, 0, left + new, height)
        else:  # taller: keep the full width, choose the rows
            new = round(width / target)
            top = round((height - new) * float(offset))
            box = (0, top, width, top + new)
        image.convert("RGB").crop(box).save(output)
    record = {"kind": "adopted_drawing", "scene": scene_id, "shot": shot_id, "drawing": drawing["id"],
              "drawing_version": drawing.get("version"), "source": relative(root, source),
              "crop": {"box": list(box), "offset": float(offset), "from": [width, height]},
              "made_with": "the approved storyboard drawing, cropped to the film's frame; nothing generated"}
    output.with_name(output.name + ".provenance.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {"picture": relative(root, output), **record}


def picture_stem(work: Path, number: str) -> str:
    """The name the shot's picture goes by: the one on disk, else `p08`, `pmA`."""

    stems = _picture_stems(number)
    for stem in stems:
        if any((work / f"{stem}{suffix}").is_file() for suffix in IMAGE_SUFFIXES):
            return stem
    return stems[-1]


def _file(scene_file: Path, value: str) -> Path | None:
    candidate = (scene_file.parent / value).resolve()
    return candidate if value and candidate.suffix.lower() in IMAGE_SUFFIXES and candidate.is_file() else None


#: A derivation from the scene's location: `location:CAM-A`, or `location` for the shot's own camera.
LOCATION_PREFIX = "location"


def location_camera(name: str, shot: dict[str, Any] | None = None) -> str | None:
    """The camera whose plate `name` asks for, or None when it names no plate."""

    text = str(name or "").strip()
    if text.lower() == LOCATION_PREFIX:
        return str((shot or {}).get("camera") or "")
    if text.lower().startswith(LOCATION_PREFIX + ":"):
        return text.split(":", 1)[1].strip()
    return None


def source_picture(root: Path, scene: dict[str, Any], name: str, shot: dict[str, Any] | None = None) -> Path | None:
    """The picture a derivation edits: a file, the picture of the shot or master it names, or a location's plate."""

    text = str(name or "").strip().lower()
    if text == "storyboard":
        # The shot's current storyboard drawing (its latest version): the approved composition to finish.
        from .storyboard import load_storyboard

        drawings = [item for item in load_storyboard(root)["candidates"]
                    if shot and item["scene"] == scene["id"] and item["shot"] == shot.get("id")]
        latest = max(drawings, key=lambda item: item.get("version") or 0, default=None)
        path = root / latest["image"]["path"] if latest else None
        return path if path and path.is_file() else None
    if text in ("board", "board:start", "board:end"):
        # The shot's own 3D board (CT-0049): a composition to start the picture from.
        from .board import board_path

        path = board_path(root, scene["id"], (shot or {}).get("id", ""), "end" if text.endswith("end") else "start")
        return path if shot and path.is_file() else None
    camera = location_camera(name, shot)
    if camera is not None:
        from .locations import plate

        return plate(root, scene["location"], camera) if scene.get("location") and camera else None
    scene_file = root / scene["file"]
    direct = _file(scene_file, name)
    if direct:
        return direct
    work = work_directory_for(scene_file)
    shot = next((item for item in scene["shots"] if shot_key(item.get("number")) == shot_key(name)), None)
    if shot is None:
        return None
    for stem in _picture_stems(str(shot.get("number"))):
        for suffix in IMAGE_SUFFIXES:
            if (work / f"{stem}{suffix}").is_file():
                return work / f"{stem}{suffix}"
    # A render that only points to a file (`from: ../blockout/B.png`).
    for item in shot.get("from") or []:
        path = _file(scene_file, str(item.get("ref") or ""))
        if path:
            return path
    return reference_picture(work, root, scene, shot)


def face_reference(root: Path, production: dict[str, Any], scene: dict[str, Any], name: str) -> dict[str, Any]:
    """The face a cast member lends, in the variant this scene chose."""

    key = cast_key(name)
    member = next((m for m in (production.get("cast") or {}).values()
                   if key in {cast_key(n) for n in [m["id"], m["label"], *m.get("names", [])]}), None)
    if member is None:
        raise ValidationError(f"{name} has no cast sheet to lend a face (cast/<id>/character.yaml)")
    chosen = {cast_key(k): str(v) for k, v in (scene.get("cast") or {}).items()}.get(key, "")
    pool = (member["variants"].get(chosen) or {}).get("references") or member["references"]
    master = next((ref for ref in pool if ref["kind"] == "face" and ref["role"] == "master"), None)
    if master is None or not master["exists"]:
        raise ValidationError(f"{member['label']}'s sheet has no face master"
                              + (f" for the variant {chosen!r}" if chosen else ""))
    return {"member": member["id"], "variant": chosen, "path": root / master["path"]}


#: What a refused picture's reasons ask of the next edit (SPEC-0009, CT-0041 option 1).
CORRECTIONS = {
    "subject_moved": "Keep every person exactly where image 1 has them: the same place and the same size in the frame.",
    "identity": "The face must be unmistakably the person in the identity image.",
    "geometry": "Do not change the room: walls, furniture and objects keep their outlines and places.",
    "light": "Keep the light of image 1: its direction, its warmth and its darkness.",
    "detail_lost": "Keep every small detail of image 1: props, tubes, cables, hands.",
    "anatomy": "Anatomy must be right: hands, fingers, eyes and limbs.",
    "frame": "The picture must be exactly the film's frame: widescreen, filling it edge to edge.",
}


def corrections(feedback: dict[str, Any] | None) -> str:
    """The director's refusal, as instructions for the next edit."""

    if not feedback:
        return ""
    lines = [CORRECTIONS[reason] for reason in feedback.get("reasons") or [] if reason in CORRECTIONS]
    if feedback.get("text"):
        lines.append(f"Correction from the director: {feedback['text']}")
    return " ".join(lines)


def plan_picture(root: Path, production: dict[str, Any], scene_id: str, shot_id: str, seed: int = 1,
                 rate: float | None = None, feedback: dict[str, Any] | None = None) -> PicturePlan:
    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        raise ValidationError(f"No scene {scene_id!r}")
    shot = next((item for item in scene["shots"] if item["id"] == shot_id), None)
    if shot is None:
        raise ValidationError(f"{scene_id} has no shot {shot_id!r}")
    derive = shot.get("derive")
    if not derive:
        raise ValidationError(f"{shot_id} does not say what picture it is made from (derive: {{from, with, request}})")
    from .providers import picture_providers

    provider_id, level = picture_provider(production, scene, shot)
    provider = picture_providers()[provider_id]()
    if not derive.get("from") and provider.needs_source:
        raise ValidationError(f"{shot_id} does not say what picture it is made from (derive: {{from, with, request}}); "
                              f"{provider_id} only repaints a picture")
    if not derive.get("request"):
        raise ValidationError(f"{shot_id} does not say what the picture should become (derive: request)")
    source = source_picture(root, scene, derive["from"], shot) if derive.get("from") else None
    if derive.get("from") and source is None:
        camera = location_camera(derive["from"], shot)
        if camera is not None:
            raise ValidationError(
                f"{shot_id} is made from the plate of {camera or 'its camera'} in {scene.get('location') or 'no location'}, "
                f"which has none (location.yaml references: {{path, kind: plate, camera: {camera or '<id>'}}})")
        if str(derive["from"]).lower() == "storyboard":
            raise ValidationError(f"{shot_id} is finished from its storyboard drawing, and it has none yet")
        if str(derive["from"]).lower().startswith("board"):
            raise ValidationError(f"{shot_id} is made from its 3D board, which is not drawn yet "
                                  f"(toast board frames <project> {scene_id} --shot {shot_id})")
        raise ValidationError(f"{shot_id} is derived from {derive['from']!r}, which has no picture yet")
    references = [face_reference(root, production, scene, name) for name in derive.get("with") or []]
    notes = []
    if feedback:
        notes.append("This edit carries the director's corrections from the refused version.")
    if shot.get("picture"):
        notes.append("The picture description is what the video model is told this image shows; "
                     "check the result against it.")
    if str(derive.get("from") or "").lower().startswith("board"):
        from .board import stale

        if stale(root, scene, shot_id, "end" if str(derive["from"]).lower().endswith("end") else "start"):
            notes.append("The 3D board was drawn before the plan last changed: draw it again (toast board frames).")
    # The style in force restyles the picture -- a board, a plate or a photo drawn into it (CT-0049).
    style = scene.get("style") or {}
    styled = f"Render the whole image as {style['prompt']}." if style.get("prompt") and derive.get("style", True) else ""
    if styled:
        notes.append(f"The style {style['name']} ({style['level']}) is asked of the picture; `style: false` on the "
                     "derive keeps the source's look.")
    # What the picture must not show. The edit model takes no negative input: said in the prompt, and the plan
    # says it is said there rather than pretending to a native mechanism (docs/generation.md).
    from .generation import avoidance

    avoid = avoidance(production, scene, [shot])
    avoided = f"Avoid: {'; '.join(item.rstrip('.') for item in avoid)}." if avoid else ""
    if level != "default":
        notes.append(f"Made by {provider_id}, chosen by the {level}.")
    from .continuity import describe, state_at

    continuity = describe(state_at(production, scene_id, shot_id), scene_id)
    return PicturePlan(
        continuity=continuity,
        scene=scene_id, shot=shot_id, stem=picture_stem(work_directory_for(root / scene["file"]), str(shot["number"])),
        source=source,
        references=references, request=derive["request"],
        prompt=provider.prompt(" ".join(filter(None, [derive["request"], styled, avoided, corrections(feedback)])),
                               source=source is not None, references=len(references)),
        seed=seed, size=provider.size(source), estimate_usd=provider.estimate_usd(rate), notes=notes,
        avoid=avoid, avoid_mechanism="in the prompt: the edit model has no negative input" if avoid else "",
        provider=provider_id, provider_level=level, model=provider.model, cost=provider.cost,
    )


def scene_pictures(root: Path, scene: dict[str, Any]) -> list[dict[str, Any]]:
    """Each derived picture of the scene: what it is made from, and every version of it."""

    from .takes import read_provenance

    work = work_directory_for(root / scene["file"])
    found = []
    for shot in scene["shots"]:
        derive = shot.get("derive")
        if not derive:
            continue
        stem = picture_stem(work, str(shot["number"]))
        source = source_picture(root, scene, derive["from"], shot) if derive.get("from") else None
        found.append({
            "shot": shot["id"], "number": shot["number"], "label": shot.get("label", ""), "derive": derive,
            "source": relative(root, source) if source else "",
            "versions": [{"path": relative(root, path), "record": read_provenance(path)}
                         for path in picture_versions(work, stem)],
        })
    return found
