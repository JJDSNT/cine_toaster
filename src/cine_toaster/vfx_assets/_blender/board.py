"""Runs inside Blender: 3D storyboard boards and a 3D animatic from a scene's USD stage (CT-0049).

    blender --background --factory-startup --python board.py -- spec.json

The stage is the plan exported by `toast usd export` (room, set pieces,
mannequins, one camera per shot). Rendered with Workbench in a board's look
-- studio light, shadows, cavity, outlines, the plan's colours -- on the
CPU in a fraction of a second a frame:

- `stills`: [{name, camera, frame}] -> `<name>.png`, and `<name>.exr` with
  the depth (a multilayer EXR, the `Depth.Z` pass in metres);
- `animatic`: {shots: [{camera, first, frames}], step} -> `animatic/f_%04d.png`,
  every `step` frames, each through its shot's camera.
"""

import json
import sys
from pathlib import Path

import bpy

spec = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
out = Path(spec["output"])
out.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=spec["usd"])
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x, scene.render.resolution_y = int(spec["width"]), int(spec["height"])
scene.render.resolution_percentage = 100
shading = scene.display.shading
shading.light = "STUDIO"
if spec.get("look", "clay") == "clay":
    # One grey for everything, as a sculpted maquette: form and light, nothing else to decide yet.
    shading.color_type = "SINGLE"
    shading.single_color = (0.72, 0.72, 0.7)
else:
    shading.color_type = "VERTEX"
shading.show_shadows, shading.show_cavity, shading.show_object_outline = True, True, True
shading.shadow_intensity = 0.35
shading.cavity_type = "BOTH"
shading.object_outline_color = (0.08, 0.09, 0.1)
scene.display.shadow_focus = 0.2
scene.view_settings.view_transform = "Standard"
scene.world = scene.world or bpy.data.worlds.new("World")
scene.world.color = (0.55, 0.56, 0.57) if spec.get("look", "clay") == "clay" else (0.82, 0.83, 0.84)
for obj in bpy.data.objects:
    if obj.type == "MESH":
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
cameras = {obj.name: obj for obj in bpy.data.objects if obj.type == "CAMERA"}
settings = scene.render.image_settings
scene.view_layers[0].use_pass_z = True


def still_format(multilayer: bool) -> None:
    # Blender 5 chooses a single or multilayer image with media_type, then the format.
    if hasattr(settings, "media_type"):
        settings.media_type = "MULTI_LAYER_IMAGE" if multilayer else "IMAGE"
    settings.file_format = "OPEN_EXR_MULTILAYER" if multilayer else "PNG"
    if not multilayer:
        settings.color_mode = "RGB"


for still in spec.get("stills") or []:
    scene.camera = cameras[still["camera"]]
    scene.frame_set(int(still["frame"]))
    still_format(False)
    scene.render.filepath = str(out / f"{still['name']}.png")
    bpy.ops.render.render(write_still=True)
    still_format(True)
    scene.render.filepath = str(out / f"{still['name']}.exr")
    bpy.ops.render.render(write_still=True)

animatic = spec.get("animatic")
if animatic:
    still_format(False)
    folder = out / "animatic"
    folder.mkdir(exist_ok=True)
    index = 0
    for shot in animatic["shots"]:
        scene.camera = cameras[shot["camera"]]
        for frame in range(int(shot["first"]), int(shot["first"]) + int(shot["frames"]), int(animatic.get("step", 1))):
            index += 1
            scene.frame_set(frame)
            scene.render.filepath = str(folder / f"f_{index:04d}.png")
            bpy.ops.render.render(write_still=True)
