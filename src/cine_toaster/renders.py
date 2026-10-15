"""A 3D scene's passes as production records (C8 step 2, CT-0081): Blender renders, the graph reads.

Rendering and reading are apart. `render_passes` runs Blender -- a command, with an actor and an event, never
during a graph's evaluation -- on a scene (a .blend, or a recipe of simple objects and a camera's keys) and
keeps what it made:

    renders/passes/<id>/render.json      how it was made and how to read it: Blender's version, the engine and
                                         its samples, the working colour space, the pixel filter, the scene file
                                         and every file it reaches (by hash), the script that rendered it, the
                                         clock, the resolution, the camera at every frame (projection,
                                         intrinsics in pixels, its matrix in the world, clipping, conventions),
                                         the table of objects, and each frame's hash
    renders/passes/<id>/rgba/f_NNNN.exr  the picture, Combined: RGBA, premultiplied, scene-linear

and records its two signals through `signals.record_signal`, the one way every signal is kept (ADR 0024):

- `<id>-depth`: geometric depth from the camera `<id>/<camera>`, in metres, **z along the camera's axis**
  (Cycles' and EEVEE's Z pass is planar: measured in CT-0081 on a wall square to the camera, 10.0000 at its
  centre and its corners, where the distance would be 11.5016); nothing hit is +inf;
- `<id>-objects`: a segmentation, each object's stable pass index (meshes sorted by name, from 1; 0 is
  nothing) with its table of names.

Both describe the render's `render.json` (their medium, pinned by hash) and depend on the scene's files: a
scene changed since is a stale render and stale signals, refused, until rendered again.

The limits of the passes, as Blender makes them: Z and the object index are **not anti-aliased** -- each
pixel holds one surface's value while Combined's edge is a filtered mix of two, so at a silhouette the
picture's alpha and colour are soft where the depth and the label are hard; and a transparent or
alpha-blended surface writes its own Z and index, not what shows through it. Depth compositing at edges is
C8 step 5's subject.

No Blender in the Core: this module runs Blender as a program and reads files; the graph's `generate.render`
reads the records through `RenderReader`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .errors import ValidationError
from .state import Actor

PASSES_DIRECTORY = Path("renders") / "passes"
SCRIPT = Path(__file__).with_name("vfx_assets") / "_blender" / "passes.py"
#: What Blender leaves where a ray hits nothing in its Z pass (1e10); kept as +inf: farther than anything.
EMPTY_Z = 1e9
#: What each engine's Z pass measures, as measured here -- never assumed of a renderer not measured: Cycles' Z
#: is planar (CT-0081). Another engine is refused until its Z is measured the same way (`tests/test_renders.py`).
Z_MEASURED = {"CYCLES": "z"}
DEPTH_CONVENTIONS = {"unit": "m", "near_is_small": True, "empty": "inf",
                     "edges": "not anti-aliased: one surface per pixel"}


def directory(root: Path, render_id: str) -> Path:
    from .signals import directory as signal_directory

    signal_directory(root, render_id)  # the same rule for an id
    return Path(root) / PASSES_DIRECTORY / render_id


def _file_hash(path: Path) -> str:
    from .compositing.identity import file_hash

    return file_hash(path)


def intrinsics(camera: dict[str, Any], width: int, height: int) -> dict[str, float]:
    """A perspective camera's intrinsics in pixels (focal lengths, principal point; rows down), from Blender's
    lens, sensor, sensor fit and shift. Square pixels only."""

    if camera["type"] != "PERSP":
        raise ValidationError(f"A {camera['type']} camera's passes are not read yet: only a perspective camera "
                              "(CT-0081)")
    fit = camera["sensor_fit"]
    if fit == "AUTO":
        fit = "HORIZONTAL" if width >= height else "VERTICAL"
    sensor_width, sensor_height = camera["sensor_mm"]
    if fit == "HORIZONTAL":
        focal, along = camera["lens_mm"] / sensor_width * width, width
    else:
        focal, along = camera["lens_mm"] / sensor_height * height, height
    shift_x, shift_y = camera["shift"]
    return {"fx": focal, "fy": focal, "cx": width / 2 - shift_x * along, "cy": height / 2 + shift_y * along}


def _relative(root: Path, given: str | Path, what: str) -> str:
    path = Path(given)
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    if not path.is_file():
        raise ValidationError(f"The {what} {given} is not there")
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        raise ValidationError(f"The {what} {given} is outside the production: keep it in the production, so a "
                              "change to it is seen") from None


def render_passes(root: Path, *, render_id: str, camera: str, first: int, last: int, size: tuple[int, int],
                  fps: Any, actor: Actor, blend: str | Path | None = None, recipe: str | Path | None = None,
                  engine: str = "CYCLES", samples: int = 16, filter_size: float | None = None,
                  camera_id: str | None = None, blender: str | None = None,
                  run: Callable[[list[str]], Any] | None = None) -> dict[str, Any]:
    """Render a scene's passes with Blender (frames `first`..`last` of the scene, at `size`, `fps`) and record
    them: the picture and `render.json` under `renders/passes/<id>/`, the signals `<id>-depth` and
    `<id>-objects`. The scene is a .blend or a recipe (JSON), in the production. `camera_id` states which camera
    of the production this render's camera is -- a shot's, matched by a solve or by hand -- so its depth is
    compared with that camera's other depths (CT-0081 step 7); left out, the render's own `<id>/<camera>`."""

    from . import timebase
    from .color import exr_layers
    from .signals import record_signal
    from .titles import blender_binary

    root = Path(root).expanduser().resolve()
    folder = directory(root, render_id)
    if (blend is None) == (recipe is None):
        raise ValidationError("A render's scene is a .blend or a recipe: give one")
    scene_key = "blend" if blend is not None else "recipe"
    scene_file = _relative(root, blend if blend is not None else recipe, "scene")
    if int(last) < int(first):
        raise ValidationError(f"A render's frames run forward: {first} to {last}")
    rate = timebase.rate(fps)
    if engine not in Z_MEASURED:
        raise ValidationError(f"What {engine}'s Z pass measures (z along the axis, or the distance along the ray) "
                              f"has not been measured here; render with {', '.join(Z_MEASURED)}, or measure it "
                              "first (CT-0081)")
    depth_meaning = {"quantity": Z_MEASURED[engine], **DEPTH_CONVENTIONS}
    blender = blender or blender_binary()
    if not blender:
        raise ValidationError("Blender is needed to render a scene's passes: https://www.blender.org/download/ "
                              "(4.2 LTS or newer), unpacked in ~/.local/opt, or set CINE_TOASTER_BLENDER "
                              "(`toast doctor`)")
    run = run or (lambda command: subprocess.run(command, check=True, capture_output=True, text=True))
    with tempfile.TemporaryDirectory(prefix="ct-passes-") as work:
        work = Path(work)
        spec = {scene_key: str(root / scene_file), "camera": camera, "first": int(first), "last": int(last),
                "width": int(size[0]), "height": int(size[1]), "engine": engine, "samples": int(samples),
                "filter_size": filter_size,
                "output": str(work / "out")}
        (work / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
        try:
            run([blender, "--background", "--factory-startup", "--python", str(SCRIPT), "--", str(work / "spec.json")])
        except subprocess.CalledProcessError as error:
            tail = "\n".join(((error.stderr or "") + (error.stdout or "")).strip().splitlines()[-8:])
            raise ValidationError(f"Blender could not render {scene_file}'s passes:\n{tail}") from None
        made = json.loads((work / "out" / "passes.json").read_text(encoding="utf-8"))
        width, height = made["resolution"]
        if made["pixel_aspect"][0] != made["pixel_aspect"][1]:
            raise ValidationError("A render's pixels are square here: its pixel aspect is "
                                  f"{made['pixel_aspect'][0]}:{made['pixel_aspect'][1]}")
        metres = float(made["unit"]["scale_length"] or 1.0)
        pictures, depths, labels = [], [], []
        for index in range(int(last) - int(first) + 1):
            layers = exr_layers(work / "out" / f"f_{index + 1:04d}.exr")
            missing = [name for name in ("Combined", "Depth", "Object Index") if name not in layers]
            if missing:
                raise ValidationError(f"Blender's frame {index + 1} has no {', '.join(missing)} pass")
            pictures.append(layers["Combined"])
            z = layers["Depth"].astype(np.float32)
            depths.append(np.where(z >= EMPTY_Z, np.float32(np.inf), z * np.float32(metres)).astype(np.float32))
            labels.append(np.rint(layers["Object Index"]).astype(np.int32))

    dependencies = []
    for path in made.get("dependencies") or []:
        try:
            dependencies.append(_relative(root, path, "file the scene reaches"))
        except ValidationError as problem:
            raise ValidationError(f"{scene_file}: {problem}") from None
    import OpenEXR

    staged = folder.with_name(f".{render_id}.part")
    shutil.rmtree(staged, ignore_errors=True)
    (staged / "rgba").mkdir(parents=True)
    hashes = []
    for index, picture in enumerate(pictures):
        path = staged / "rgba" / f"f_{index + 1:04d}.exr"
        OpenEXR.File({"type": OpenEXR.scanlineimage, "compression": OpenEXR.ZIP_COMPRESSION},
                     {"RGBA": np.ascontiguousarray(picture, np.float32)}).write(str(path))
        hashes.append(_file_hash(path))
    cameras = [{**item, "intrinsics": intrinsics(item, width, height)} for item in made["cameras"]]
    manifest = {
        "schema_version": 1, "id": render_id,
        "renderer": {"name": "blender", "version": made["blender"], "engine": made["engine"],
                     "samples": made["samples"], "script": SCRIPT.name, "script_hash": _file_hash(SCRIPT)},
        "scene": {scene_key: scene_file, "hash": _file_hash(root / scene_file),
                  "dependencies": [{"file": item, "hash": _file_hash(root / item)} for item in dependencies]},
        "clock": {"rate": timebase.ffmpeg_rate(rate), "origin": timebase.to_record(Fraction(0)),
                  "scene_frames": [int(first), int(last)]},
        "resolution": [width, height], "working_space": made["working_space"], "filter_size": made["filter_size"],
        "picture": {"frames": "rgba/f_NNNN.exr", "alpha": "premultiplied", "colorspace": made["working_space"],
                    "hashes": hashes},
        "camera": {"name": camera, "id": camera_id or f"{render_id}/{camera}",
                   **({"stated_by": actor.public_dict()} if camera_id else {}), "conventions": made["conventions"],
                   "matrix": "camera to world, rows", "unit": {"metres_per_unit": metres}, "frames": cameras},
        "objects": {str(key): name for key, name in made["objects"].items()},
        "depth": {**depth_meaning, "measured": "CT-0081: a wall square to the camera reads its distance down the "
                                              "axis at every pixel"},
        "signals": {"depth": f"{render_id}-depth", "objects": f"{render_id}-objects"},
        "made_at": datetime.now(UTC).isoformat(), "by": actor.public_dict(),
    }
    (staged / "render.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    if folder.exists():
        shutil.rmtree(folder)
    staged.replace(folder)

    media = (folder / "render.json").relative_to(root).as_posix()
    inputs = [{"file": scene_file}] + [{"file": item} for item in dependencies]
    maker = {"kind": "renderer", "name": "blender", "version": made["blender"], "engine": made["engine"],
             "samples": made["samples"]}
    record_signal(root, signal_id=f"{render_id}-depth", kind="depth", origin="geometric", frames=depths, rate=rate,
                  media=media, camera=manifest["camera"]["id"], depth=depth_meaning,
                  maker={**maker, "pass": "Depth"}, inputs=inputs, actor=actor,
                  rationale=f"Blender's Z pass of {scene_file}")
    record_signal(root, signal_id=f"{render_id}-objects", kind="segmentation", origin="geometric", frames=labels,
                  rate=rate, media=media, camera=manifest["camera"]["id"],
                  labels={0: "nothing", **{int(key): name for key, name in manifest["objects"].items()}},
                  labels_are="instances",
                  maker={**maker, "pass": "Object Index"}, inputs=inputs, actor=actor,
                  rationale=f"Blender's object index pass of {scene_file}")
    return {"render": render_id, "frames": len(pictures), "manifest": media,
            "signals": [f"{render_id}-depth", f"{render_id}-objects"], "blender": made["blender"]}


def load_render(root: Path, render_id: str) -> dict[str, Any]:
    path = directory(Path(root), render_id) / "render.json"
    if not path.is_file():
        raise ValidationError(f"There is no render {render_id} (render its passes first: `render_passes`)")
    return json.loads(path.read_text(encoding="utf-8"))


def status(root: Path, render_id: str) -> dict[str, Any]:
    """Whether a render still follows from what made it: `stale` lists every reason it does not -- its scene or
    a file the scene reaches changed, its pictures changed outside its commands, the script that renders
    passes changed, or one of its signals is stale."""

    from .signals import status as signal_status

    root = Path(root).expanduser().resolve()
    manifest = load_render(root, render_id)
    folder = directory(root, render_id)
    stale = []
    scene = manifest["scene"]
    for item in [{"file": scene.get("blend") or scene.get("recipe"), "hash": scene["hash"]}, *scene["dependencies"]]:
        path = root / item["file"]
        if not path.is_file():
            stale.append(f"its scene's file {item['file']} is not there")
        elif _file_hash(path) != item["hash"]:
            stale.append(f"its scene's file {item['file']} has changed since")
    for index, expected in enumerate(manifest["picture"]["hashes"]):
        path = folder / "rgba" / f"f_{index + 1:04d}.exr"
        if not path.is_file() or _file_hash(path) != expected:
            stale.append(f"its picture's frame {index + 1} has been changed outside its commands")
    if _file_hash(SCRIPT) != manifest["renderer"]["script_hash"]:
        stale.append("the script that renders passes has changed since")
    for name in manifest["signals"].values():
        try:
            reasons = signal_status(root, name)["stale"]
        except ValidationError:
            reasons = ["it is gone"]
        stale.extend(f"its signal {name}: {reason}" for reason in reasons)
    return {"id": render_id, "stale": stale, "renderer": manifest["renderer"], "frames": len(manifest["picture"]["hashes"])}


class RenderReader:
    """A render as a graph reads it, never running Blender: checked once (refused when stale), then -- by the
    render's clock -- its picture, its depth and its alpha at an instant, all three of the same frame."""

    def __init__(self, root: Path, render_id: str) -> None:
        from . import timebase
        from .signals import SignalReader

        self.root = Path(root).expanduser().resolve()
        state = status(self.root, render_id)
        if state["stale"]:
            raise ValidationError(f"The render {render_id} is stale: {'; '.join(state['stale'])} -- render its "
                                  "passes again")
        self.id, self.manifest = render_id, load_render(self.root, render_id)
        self.folder = directory(self.root, render_id)
        self.rate = timebase.rate(self.manifest["clock"]["rate"])
        self.origin = timebase.from_record(self.manifest["clock"]["origin"])
        self.frames = len(self.manifest["picture"]["hashes"])
        self.depth = SignalReader(self.root, self.manifest["signals"]["depth"])
        self.camera = self.manifest["camera"]["id"]

    def index(self, seconds: Any) -> int:
        from .compositing.semantics import remap_samples

        position = seconds - self.origin if isinstance(seconds, Fraction) else float(seconds) - float(self.origin)
        return int(np.clip(remap_samples(position, self.rate, "nearest", clamp=False)[0][0], 0, self.frames - 1))

    def picture(self, index: int) -> np.ndarray:
        from .color import read_exr

        return read_exr(self.folder / "rgba" / f"f_{int(np.clip(index, 0, self.frames - 1)) + 1:04d}.exr")
