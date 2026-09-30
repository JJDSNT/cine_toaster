"""Runs inside Blender, on a production's own .blend: render it as a VFX element (CT-0047).

    blender --background --factory-startup project.blend --python project.py -- spec.json

The project keeps its own scene, animation and materials; only what makes it
an element is set here: the frame size, the frame range (from frame 1),
a transparent background, and scene-linear EXR with alpha.
"""

import json
import sys
from pathlib import Path

import bpy

spec = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
scene = bpy.context.scene
out = Path(spec["output"]) / "exr"
out.mkdir(parents=True, exist_ok=True)
scene.render.resolution_x, scene.render.resolution_y = int(spec["width"]), int(spec["height"])
scene.render.resolution_percentage = 100
scene.render.fps = int(spec.get("fps", 24))
scene.render.film_transparent = True
settings = scene.render.image_settings
settings.file_format, settings.color_depth, settings.color_mode, settings.exr_codec = "OPEN_EXR", "16", "RGBA", "ZIP"
start = scene.frame_start
for index in range(1, int(spec["frames"]) + 1):
    scene.frame_set(start + index - 1)
    scene.render.filepath = str(out / f"f_{index:04d}.exr")
    bpy.ops.render.render(write_still=True)
