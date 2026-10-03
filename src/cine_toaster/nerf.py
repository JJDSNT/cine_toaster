"""A shot's camera as a nerfstudio camera path: NeRF renders of a captured set (CT-0047).

NeRFs are rendered where nerfstudio runs -- a CUDA GPU, often a remote one --
so Cine Toaster's part is the camera: `camera_path(...)` writes the
`camera_path.json` that `ns-render camera-path` reads, from the same poses
the blocking frame draws, placed in the NeRF's world through the location's
`nerf:` transform:

    # locations/<id>/location.yaml
    nerf:
      config: outputs/station/nerfacto/config.yml   # what ns-render loads (on the GPU machine)
      position: [0.0, 0.0, 0.0]   # where the plan's origin sits in the NeRF's world
      rotation: [0, 0, 0]         # Euler degrees XYZ, the plan turned into the NeRF's world
      scale: 0.25                 # NeRF units per metre

The render comes back as an image sequence or a video, which is a plate or
an element like any other.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .errors import ValidationError

SENSOR_WIDTH_MM = 36.0


def _rotation(degrees: Any) -> list[list[float]]:
    """A rotation matrix from Euler degrees applied X, then Y, then Z."""

    x, y, z = (math.radians(float(value)) for value in (list(degrees or [0, 0, 0]) + [0, 0, 0])[:3])
    rx = [[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]]
    ry = [[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]]
    rz = [[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]]

    def times(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    return times(rz, times(ry, rx))


def _apply(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(matrix[i][k] * vector[k] for k in range(3)) for i in range(3)]


def _normal(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / length for value in vector]


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def camera_to_world(eye: list[float], aim: list[float], up: list[float]) -> list[float]:
    """An OpenGL camera (looking down -Z, +Y up) as a row-major 4×4, flattened."""

    forward = _normal([aim[i] - eye[i] for i in range(3)])
    right = _cross(forward, up)
    if math.sqrt(sum(value * value for value in right)) < 1e-6:  # straight down: any horizontal right
        right = _cross(forward, [0.0, 1.0, 0.0])
    right = _normal(right)
    true_up = _cross(right, forward)
    back = [-value for value in forward]
    return [right[0], true_up[0], back[0], eye[0],
            right[1], true_up[1], back[1], eye[1],
            right[2], true_up[2], back[2], eye[2],
            0.0, 0.0, 0.0, 1.0]


def vertical_fov(lens_mm: float, width: int, height: int) -> float:
    horizontal = 2 * math.atan(SENSOR_WIDTH_MM / (2 * lens_mm))
    return math.degrees(2 * math.atan(math.tan(horizontal / 2) * height / width))


def camera_path(scene: dict[str, Any], shot: dict[str, Any], *, frames: int = 24, width: int = 1280,
                height: int = 720, transform: dict[str, Any] | None = None) -> dict[str, Any]:
    """The shot's move as nerfstudio's camera path, in the NeRF's world."""

    from .blocking import DEFAULT_CAMERA_HEIGHT, DEFAULT_EYE_HEIGHT, state_at

    motion = shot.get("motion") or {}
    if not (motion.get("start") or {}).get("camera"):
        raise ValidationError(f"{shot.get('id')} has no camera pose to export")
    transform = transform or {}
    rotation = _rotation(transform.get("rotation"))
    scale = float(transform.get("scale") or 1.0)
    origin = [float(value) for value in (transform.get("position") or [0, 0, 0])]

    def placed(point: list[float]) -> list[float]:
        return [value * scale + origin[i] for i, value in enumerate(_apply(rotation, point))]

    up = _apply(rotation, [0.0, 0.0, 1.0])  # the plan is Z up
    subjects = {item["id"]: item for item in (scene.get("geometry") or {}).get("subjects", [])}
    duration = float(shot.get("duration_seconds") or 3.0)
    keyframes = []
    for index in range(frames):
        t = index / max(1, frames - 1)
        pose = state_at(motion, t)["camera"]
        camera_height = float(pose.get("height") or DEFAULT_CAMERA_HEIGHT)
        aim_height = pose.get("aim_height")
        if aim_height is None:
            target = subjects.get(pose.get("target_ref") or "")
            aim_height = (target.get("eye_height") or DEFAULT_EYE_HEIGHT) if target else camera_height
        eye = placed([pose["position"][0], pose["position"][1], camera_height])
        aim = placed([pose["target"][0], pose["target"][1], float(aim_height)])
        keyframes.append({"camera_to_world": camera_to_world(eye, aim, up),
                          "fov": round(vertical_fov(float(pose["lens_mm"]), width, height), 4),
                          "aspect": width / height})
    return {"camera_type": "perspective", "render_height": height, "render_width": width,
            "fps": frames / duration, "seconds": duration, "camera_path": keyframes,
            "cine_toaster": {"scene": scene.get("id"), "shot": shot.get("id"),
                             "camera": motion.get("camera_id", ""), "frames": frames}}


def location_nerf(root: Path, location_id: str) -> dict[str, Any] | None:
    from .locations import FILE, _read, load_locations

    location = load_locations(root).get(str(location_id).strip().upper())
    if location is None:
        return None
    raw = _read(root / location["directory"] / FILE).get("nerf")
    return dict(raw) if isinstance(raw, dict) else None


def export(root: Path, scene: dict[str, Any], shot: dict[str, Any], output: Path, *, frames: int = 24,
           width: int = 1280, height: int = 720) -> dict[str, Any]:
    """Write the shot's camera path; returns where, and the command that renders it."""

    declared = location_nerf(root, scene.get("location") or "") if scene.get("location") else None
    path = camera_path(scene, shot, frames=frames, width=width, height=height, transform=declared or {})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(path, indent=2), encoding="utf-8")
    config = (declared or {}).get("config") or "<the NeRF's config.yml>"
    command = (f"ns-render camera-path --load-config {config} --camera-path-filename {output.name} "
               f"--output-path {output.stem}.mp4")
    return {"path": str(output), "frames": frames, "placed": bool(declared), "command": command}
