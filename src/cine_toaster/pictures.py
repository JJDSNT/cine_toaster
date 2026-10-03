"""Master pictures made by editing another picture with cast references (CT-0037, plan step 9).

SINGULAR's method, measured on its scenes: the room is designed once in 3D
and rendered per camera; the people are then painted into that render by an
image editor that is told to keep the geometry, given each character's
sheet for identity. A shot declares it as `derive: {from, with, request}`.

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
from .providers.qwen_edit import HOURLY_RATE_USD, edit_prompt, size_like
from .takes import shot_key, work_directory_for

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
#: A warm edit took under a minute in SINGULAR; the estimate assumes a cold worker.
EXECUTION_SECONDS = 45.0
COLD_START_SECONDS = 90.0


def relative(root: Path, path: Path) -> str:
    """A project-relative path, however either side was spelled."""

    return path.resolve().relative_to(root.resolve()).as_posix()


def estimate(rate: float = HOURLY_RATE_USD) -> float:
    return round((EXECUTION_SECONDS + COLD_START_SECONDS) * rate / 3600, 3)


@dataclass(slots=True)
class PicturePlan:
    scene: str
    shot: str
    stem: str
    source: Path
    references: list[dict[str, Any]]
    request: str
    prompt: str
    seed: int
    size: tuple[int, int]
    estimate_usd: float
    notes: list[str] = field(default_factory=list)

    def public_dict(self, root: Path) -> dict[str, Any]:
        return {
            "scene": self.scene, "shot": self.shot, "model": "qwen-image-edit",
            "source": {"path": relative(root, self.source), "digest": _digest(self.source)},
            "references": [{**ref, "path": relative(root, ref["path"]), "digest": _digest(ref["path"])}
                           for ref in self.references],
            "request": self.request, "prompt": self.prompt, "seed": self.seed,
            "width": self.size[0], "height": self.size[1], "estimate_usd": self.estimate_usd, "notes": self.notes,
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
                 rate: float = HOURLY_RATE_USD, feedback: dict[str, Any] | None = None) -> PicturePlan:
    scene = next((item for item in production["scenes"] if item["id"] == scene_id), None)
    if scene is None:
        raise ValidationError(f"No scene {scene_id!r}")
    shot = next((item for item in scene["shots"] if item["id"] == shot_id), None)
    if shot is None:
        raise ValidationError(f"{scene_id} has no shot {shot_id!r}")
    derive = shot.get("derive")
    if not derive or not derive.get("from"):
        raise ValidationError(f"{shot_id} does not say what picture it is made from (derive: {{from, with, request}})")
    if not derive.get("request"):
        raise ValidationError(f"{shot_id} does not say what the picture should become (derive: request)")
    source = source_picture(root, scene, derive["from"], shot)
    if source is None:
        camera = location_camera(derive["from"], shot)
        if camera is not None:
            raise ValidationError(
                f"{shot_id} is made from the plate of {camera or 'its camera'} in {scene.get('location') or 'no location'}, "
                f"which has none (location.yaml references: {{path, kind: plate, camera: {camera or '<id>'}}})")
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
    if str(derive["from"]).lower().startswith("board"):
        from .board import stale

        if stale(root, scene, shot_id, "end" if str(derive["from"]).lower().endswith("end") else "start"):
            notes.append("The 3D board was drawn before the plan last changed: draw it again (toast board frames).")
    # The style in force restyles the picture -- a board, a plate or a photo drawn into it (CT-0049).
    style = scene.get("style") or {}
    styled = f"Render the whole image as {style['prompt']}." if style.get("prompt") and derive.get("style", True) else ""
    if styled:
        notes.append(f"The style {style['name']} ({style['level']}) is asked of the picture; `style: false` on the "
                     "derive keeps the source's look.")
    return PicturePlan(
        scene=scene_id, shot=shot_id, stem=picture_stem(work_directory_for(root / scene["file"]), str(shot["number"])),
        source=source,
        references=references, request=derive["request"],
        prompt=edit_prompt(" ".join(filter(None, [derive["request"], styled, corrections(feedback)])),
                           bool(references)),
        seed=seed, size=size_like(source), estimate_usd=estimate(rate), notes=notes,
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
        source = source_picture(root, scene, derive.get("from", ""), shot)
        found.append({
            "shot": shot["id"], "number": shot["number"], "label": shot.get("label", ""), "derive": derive,
            "source": relative(root, source) if source else "",
            "versions": [{"path": relative(root, path), "record": read_provenance(path)}
                         for path in picture_versions(work, stem)],
        })
    return found
