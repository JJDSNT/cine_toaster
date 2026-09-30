"""A scene's plan as an OpenUSD stage: the bridge to Blender, Unreal and Unity (CT-0047).

`toast usd export <project> <scene>` writes what the plan says -- the room
(or the open ground, outdoors), the set pieces, the subjects, and one camera
per shot with its lens and its move -- as a USD stage those tools import:

- Z up, metres (`metersPerUnit = 1`), 24 time codes per second;
- the shots laid end to end on the stage's timeline, each camera animated
  over its own shot with the poses the blocking frame draws (the same
  easing and arcs, sampled every few frames), subjects moved the same way;
- a full-frame 36 mm sensor, as the frame assumes;
- each prim carries its Cine Toaster ids in `customData`.

The stage is derived, like the blocking frame: exported on request, never
the record. It needs the optional `usd-core` package (Pixar's USD, the
`usd` extra).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .errors import ValidationError

FPS = 24
SENSOR_WIDTH_MM, SENSOR_HEIGHT_MM = 36.0, 20.25
SAMPLE_EVERY = 4  # frames between the camera's samples; USD interpolates linearly between them
DEFAULT_CAMERA_HEIGHT, DEFAULT_EYE_HEIGHT = 1.5, 1.6


def available() -> str:
    try:
        import pxr  # noqa: F401
    except ImportError:
        return "Pixar's USD is not installed (make install-usd)"
    return ""


def _name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(value))
    return cleaned if cleaned and not cleaned[0].isdigit() else f"_{cleaned}"


def _look_at(eye: tuple[float, float, float], aim: tuple[float, float, float]):
    """A camera's transform: USD cameras look down their -Z, with +Y up."""

    from pxr import Gf

    forward = Gf.Vec3d(*aim) - Gf.Vec3d(*eye)
    forward = forward.GetNormalized() if forward.GetLength() > 1e-9 else Gf.Vec3d(0, 1, 0)
    up = Gf.Vec3d(0, 0, 1)
    right = Gf.Cross(forward, up)
    if right.GetLength() < 1e-6:  # looking straight down or up: north is the frame's top
        right = Gf.Cross(forward, Gf.Vec3d(0, 1, 0))
    right = right.GetNormalized()
    true_up = Gf.Cross(right, forward).GetNormalized()
    back = -forward
    return Gf.Matrix4d(right[0], right[1], right[2], 0,
                       true_up[0], true_up[1], true_up[2], 0,
                       back[0], back[1], back[2], 0,
                       eye[0], eye[1], eye[2], 1)


def _aim_height(pose: dict[str, Any], subjects: dict[str, dict[str, Any]], camera_height: float) -> float:
    """How high the camera aims: declared, else its subject's eyes, else level (as the blocking frame)."""

    if pose.get("aim_height") is not None:
        return float(pose["aim_height"])
    target = subjects.get(pose.get("target_ref") or "")
    if target:
        return float(target.get("eye_height") or DEFAULT_EYE_HEIGHT)
    return camera_height


def export(scene: dict[str, Any], output: Path) -> dict[str, Any]:
    """Write the scene's plan as a USD stage; returns a summary (shots, frames, prims)."""

    missing = available()
    if missing:
        raise ValidationError(missing)
    from pxr import Gf, Usd, UsdGeom, Vt

    from .blocking import state_at

    geometry = scene.get("geometry") or {}
    if not geometry.get("room") and not geometry.get("cameras"):
        raise ValidationError(f"{scene.get('id')} has no plan (geography) to export")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(output))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetTimeCodesPerSecond(FPS)
    stage.SetFramesPerSecond(FPS)
    root = UsdGeom.Xform.Define(stage, "/Scene")
    stage.SetDefaultPrim(root.GetPrim())
    root.GetPrim().SetCustomDataByKey("cine_toaster:scene", str(scene.get("id") or ""))

    def box(path: str, centre, size, colour, rotation_deg: float = 0.0):
        cube = UsdGeom.Cube.Define(stage, path)
        cube.CreateSizeAttr(1.0)
        cube.CreateDisplayColorAttr([Gf.Vec3f(*colour)])
        xform = UsdGeom.XformCommonAPI(cube)
        xform.SetTranslate(Gf.Vec3d(*centre))
        xform.SetRotate(Gf.Vec3f(0, 0, rotation_deg))
        xform.SetScale(Gf.Vec3f(*size))
        return cube

    room = geometry.get("room") or {}
    prims = 0
    if room:
        width, depth, height = float(room["width"]), float(room["depth"]), float(room.get("height") or 2.7)
        UsdGeom.Xform.Define(stage, "/Scene/Room")
        box("/Scene/Room/Floor", (width / 2, depth / 2, -0.01), (width, depth, 0.02), (0.18, 0.2, 0.21))
        prims += 1
        if not room.get("exterior"):
            thickness = 0.05
            for name, centre, size in (
                    ("Wall_south", (width / 2, -thickness / 2, height / 2), (width, thickness, height)),
                    ("Wall_north", (width / 2, depth + thickness / 2, height / 2), (width, thickness, height)),
                    ("Wall_west", (-thickness / 2, depth / 2, height / 2), (thickness, depth, height)),
                    ("Wall_east", (width + thickness / 2, depth / 2, height / 2), (thickness, depth, height))):
                box(f"/Scene/Room/{name}", centre, size, (0.28, 0.3, 0.32))
                prims += 1

    UsdGeom.Xform.Define(stage, "/Scene/SetPieces")
    for piece in geometry.get("set_pieces") or []:
        (x, y), h = piece["position"], float(piece["height"])
        cube = box(f"/Scene/SetPieces/{_name(piece['id'])}", (x, y, h / 2), (piece["width"], piece["depth"], h),
                   (0.35, 0.39, 0.42), float(piece.get("rotation_deg") or 0))
        cube.GetPrim().SetCustomDataByKey("cine_toaster:id", piece["id"])
        prims += 1

    subjects = {item["id"]: item for item in geometry.get("subjects") or []}
    subject_prims = {}
    UsdGeom.Xform.Define(stage, "/Scene/Subjects")
    # Each subject is its own shape, moved directly (an Xform holding a single child is merged
    # away by some importers, Blender's among them, and its animation lost with it).
    for subject_id, subject in subjects.items():
        path = f"/Scene/Subjects/{_name(subject_id)}"
        if subject.get("kind") == "object":
            side = float(subject.get("width") or 0.6)
            tall = float(subject.get("height") or subject.get("eye_height") or 1.0)
            shape = UsdGeom.Cube.Define(stage, path)
            shape.CreateSizeAttr(1.0)
            shape.CreateDisplayColorAttr([Gf.Vec3f(0.43, 0.72, 0.85)])
            UsdGeom.XformCommonAPI(shape).SetScale(Gf.Vec3f(side, side, tall))
        else:
            tall = float(subject.get("eye_height") or DEFAULT_EYE_HEIGHT) + 0.12
            shape = UsdGeom.Capsule.Define(stage, path)
            shape.CreateAxisAttr("Z")
            shape.CreateRadiusAttr(0.2)
            shape.CreateHeightAttr(max(0.1, tall - 0.4))
            shape.CreateDisplayColorAttr([Gf.Vec3f(0.91, 0.72, 0.36)])
        shape.GetPrim().SetCustomDataByKey("cine_toaster:id", subject_id)
        shape.GetPrim().SetCustomDataByKey("cine_toaster:label", subject.get("label") or subject_id)
        mover = UsdGeom.XformCommonAPI(shape)
        mover.SetTranslate(Gf.Vec3d(*subject["position"], tall / 2))
        subject_prims[subject_id] = (mover, tall / 2)
        prims += 1

    UsdGeom.Xform.Define(stage, "/Scene/Cameras")
    frame, shots = 0, []
    for shot in scene.get("shots") or []:
        motion = shot.get("motion") or {}
        if not (motion.get("start") or {}).get("camera") or not (motion.get("end") or {}).get("camera"):
            continue
        length = max(1, round(float(shot.get("duration_seconds") or 3.0) * FPS))
        camera = UsdGeom.Camera.Define(stage, f"/Scene/Cameras/{_name(shot['id'])}")
        prim = camera.GetPrim()
        for key, value in (("cine_toaster:shot", shot["id"]), ("cine_toaster:camera", motion.get("camera_id") or ""),
                           ("cine_toaster:move", (shot.get("move") or {}).get("id") or motion.get("kind") or ""),
                           ("cine_toaster:first_frame", frame), ("cine_toaster:frames", length)):
            prim.SetCustomDataByKey(key, value)
        # USD measures lens and aperture in tenths of a stage unit: with metres, 50 mm is 0.5.
        tenths = 1.0 / (100.0 * UsdGeom.GetStageMetersPerUnit(stage) * 10.0) * 10.0
        camera.CreateHorizontalApertureAttr(SENSOR_WIDTH_MM * tenths)
        camera.CreateVerticalApertureAttr(SENSOR_HEIGHT_MM * tenths)
        camera.CreateClippingRangeAttr(Gf.Vec2f(0.05, 10000.0))
        transform = camera.MakeMatrixXform()
        focal = camera.CreateFocalLengthAttr()
        samples = sorted(set(list(range(0, length, SAMPLE_EVERY)) + [length]))
        for offset in samples:
            state = state_at(motion, offset / length)
            pose = state["camera"]
            height = float(pose.get("height") or DEFAULT_CAMERA_HEIGHT)
            eye = (pose["position"][0], pose["position"][1], height)
            aim = (pose["target"][0], pose["target"][1], _aim_height(pose, subjects, height))
            time = Usd.TimeCode(frame + offset)
            transform.Set(_look_at(eye, aim), time)
            focal.Set(float(pose["lens_mm"]) * tenths, time)
            for subject_id, position in (state.get("subjects") or {}).items():
                if subject_id in subject_prims:
                    mover, lift = subject_prims[subject_id]
                    mover.SetTranslate(Gf.Vec3d(position[0], position[1], lift), time)
        shots.append({"shot": shot["id"], "first_frame": frame, "frames": length})
        frame += length
    stage.SetStartTimeCode(0)
    stage.SetEndTimeCode(max(0, frame))
    stage.GetRootLayer().customLayerData = {"cine_toaster:shots": Vt.StringArray(
        [f"{item['shot']}@{item['first_frame']}+{item['frames']}" for item in shots])}
    stage.GetRootLayer().Save()
    return {"output": str(output), "shots": shots, "frames": frame, "prims": prims + len(shots)}
