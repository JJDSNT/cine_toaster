"""Runs inside Blender: a title's letters as 3D objects, rendered with a transparent background.

    blender --background --factory-startup --python title.py -- spec.json

The spec gives the effect, the parameters (text, size, colour, spaced,
enter_at, fade_in, fade_out), the font, the frame size, the frame count and
the output directory. Frames are written as `f_0001.png` ... with alpha, for
FFmpeg to lay over the picture. The `.blend` is kept beside them so the
title can be opened and changed by hand.

Effects:
- `letters-turn-in`: every letter turns on its own vertical axis, from edge-on
  to facing the camera, together;
- `letters-rise`: the letters rise into place one after another.

Workbench renders flat colour quickly, on the CPU, with no GPU needed.
"""

import json
import math
import sys
from pathlib import Path

import bpy

spec = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
params = spec["params"]
width, height, fps, frames = int(spec["width"]), int(spec["height"]), int(spec["fps"]), int(spec["frames"])
out = Path(spec["output"])
out.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "FLAT"
scene.display.shading.color_type = "OBJECT"
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = width, height, 100
scene.render.fps = fps
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "Standard"
scene.frame_start, scene.frame_end = 1, frames

camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.collection.objects.link(camera)
camera.location = (0, 0, 10)
camera.data.type = "ORTHO"
camera.data.ortho_scale = 10  # the frame is 10 units wide
scene.camera = camera

colour = str(params.get("color") or "#E6E6E6").lstrip("#")
rgb = tuple(int(colour[index:index + 2], 16) / 255 for index in (0, 2, 4)) if len(colour) == 6 else (0.9, 0.9, 0.9)
font = bpy.data.fonts.load(spec["font"])
# The size is in pixels of a 720-line frame; the frame is 10 units wide.
units = float(params.get("size") or 40) / 720 * (10 * height / width) * 1.35
gap = units * (0.45 if params.get("spaced") else 0.12)

letters = []
for index, char in enumerate(str(params.get("text") or "")):
    if char == " ":
        letters.append(None)
        continue
    curve = bpy.data.curves.new(f"letter_{index}", type="FONT")
    curve.body, curve.font, curve.size, curve.extrude = char, font, units, units * 0.04
    obj = bpy.data.objects.new(curve.name, curve)
    scene.collection.objects.link(obj)
    obj.color = (*rgb, 1.0)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    obj.select_set(False)
    letters.append(obj)
bpy.context.view_layer.update()

space = units * 0.5
total = sum(obj.dimensions.x if obj else space for obj in letters) + gap * max(0, len(letters) - 1)
cursor = -total / 2
offset_y = {"centre": 0.0, "bottom": -10 * height / width * 0.36, "top": 10 * height / width * 0.3}.get(
    params.get("position"), 0.0)
enter = max(1, round(float(params.get("enter_at") or 0) * fps) + 1)
arrive = max(enter + 1, enter + round(float(params.get("fade_in") or 1.0) * fps))
leave = max(arrive, frames - round(float(params.get("fade_out") or 1.0) * fps))
placed = [obj for obj in letters if obj]
for obj in letters:
    width_now = obj.dimensions.x if obj else space
    if obj:
        obj.location = (cursor + width_now / 2, offset_y, 0)
    cursor += width_now + gap

for order, obj in enumerate(placed):
    if spec["effect"] == "letters-rise":
        start = enter + round(order * (arrive - enter) / max(1, len(placed)))
        end = start + max(4, round((arrive - enter) / 2))
        home = obj.location.y
        obj.scale = (0.001, 0.001, 0.001)  # not there until its turn
        obj.keyframe_insert("scale", frame=max(1, start - 1))
        obj.scale = (1, 1, 1)
        obj.keyframe_insert("scale", frame=start)
        obj.location.y = home - units * 1.2
        obj.keyframe_insert("location", frame=start)
        obj.location.y = home
        obj.keyframe_insert("location", frame=end)
    else:  # letters-turn-in
        obj.rotation_euler = (0, math.pi / 2, 0)
        obj.keyframe_insert("rotation_euler", frame=enter)
        obj.rotation_euler = (0, 0, 0)
        obj.keyframe_insert("rotation_euler", frame=arrive)
    # Leaving: the letters sink out of sight by scaling to nothing.
    obj.keyframe_insert("scale", frame=leave)
    obj.scale = (0.001, 0.001, 0.001)
    obj.keyframe_insert("scale", frame=frames)
    obj.scale = (1, 1, 1)

bpy.ops.wm.save_as_mainfile(filepath=str(out / "title.blend"))
for frame in range(1, frames + 1):
    scene.frame_set(frame)
    scene.render.filepath = str(out / f"f_{frame:04d}.png")
    bpy.ops.render.render(write_still=True)
