"""Runs inside Blender: an OpenUSD scene rendered as a VFX element or a plate (CT-0047).

    blender --background --factory-startup --python usd.py -- spec.json

The spec's `usd` is a `.usd/.usda/.usdc/.usdz` stage. It is imported with
its materials (UsdPreviewSurface). With `camera` (a camera prim's name in
the stage) it is rendered through that camera over its own time range;
otherwise a camera frames the whole stage and turns about it by `spin`
degrees over the shot. Cycles on the CPU, a soft sky and a sun, transparent
background, scene-linear EXR with alpha.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

spec = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
params = spec.get("params") or {}
width, height, fps, frames = int(spec["width"]), int(spec["height"]), int(spec.get("fps", 24)), int(spec["frames"])
out = Path(spec["output"]) / "exr"
out.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=spec["usd"])
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = int(params.get("samples", 16))
scene.cycles.use_denoising = False
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = width, height, 100
scene.render.fps = fps
scene.render.film_transparent = bool(params.get("transparent", True))
scene.view_settings.view_transform = "Standard"
if not scene.world:
    scene.world = bpy.data.worlds.new("World")
scene.world.color = (0.35, 0.37, 0.4)
if not any(obj.type == "LIGHT" for obj in bpy.data.objects):
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = float(params.get("light", 3.0))
    sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(30))
    scene.collection.objects.link(sun)

named = str(params.get("camera") or "")
cameras = {obj.name: obj for obj in bpy.data.objects if obj.type == "CAMERA"}
start = scene.frame_start
if named:
    if named not in cameras:
        raise SystemExit(f"The stage has no camera {named!r}; it has {sorted(cameras)}")
    scene.camera = cameras[named]
    turntable = False
else:
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    corners = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    low = Vector([min(c[i] for c in corners) for i in range(3)])
    high = Vector([max(c[i] for c in corners) for i in range(3)])
    centre, radius = (low + high) / 2, max((high - low).length / 2, 1e-3)
    pivot = bpy.data.objects.new("pivot", None)
    pivot.location = centre
    scene.collection.objects.link(pivot)
    camera = bpy.data.objects.new("turntable", bpy.data.cameras.new("turntable"))
    camera.data.lens = 50
    distance = radius / math.tan(math.atan(36 / (2 * 50)) * 0.8)
    camera.location = centre + Vector((0, -distance, distance * 0.35))
    camera.parent = pivot
    camera.location = Vector((0, -distance, distance * 0.35))
    look = camera.constraints.new("TRACK_TO")
    look.target, look.track_axis, look.up_axis = pivot, "TRACK_NEGATIVE_Z", "UP_Y"
    camera.data.clip_end = distance * 10
    scene.collection.objects.link(camera)
    scene.camera = camera
    spin = math.radians(float(params.get("spin", 30.0)))
    pivot.keyframe_insert("rotation_euler", frame=1)
    pivot.rotation_euler = (0, 0, spin)
    pivot.keyframe_insert("rotation_euler", frame=frames)
    start = 1

settings = scene.render.image_settings
settings.file_format, settings.color_depth, settings.color_mode, settings.exr_codec = "OPEN_EXR", "16", "RGBA", "ZIP"
bpy.ops.wm.save_as_mainfile(filepath=str(Path(spec["output"]) / "usd.blend"))
for index in range(1, frames + 1):
    scene.frame_set(start + index - 1)
    scene.render.filepath = str(out / f"f_{index:04d}.exr")
    bpy.ops.render.render(write_still=True)
