"""Runs inside Blender: a VFX element rendered with a transparent background (CT-0047).

    blender --background --factory-startup --python element.py -- spec.json

The spec gives the effect, its parameters, the frame size and count, and
where and how to write: `exr` (scene-linear, half float, RGBA — what a
compositor wants), `png` (display-encoded RGBA) or both. The `.blend` is
kept beside the frames so the element can be reopened and changed.

Effects:
- `sparks-burst`: hot sparks thrown from a point, falling under gravity;
- `disintegrate`: a word (or a box) coming apart into drifting particles
  while its faces vanish — for titles and objects.

Cycles on the CPU at a low sample count: emission only, so it converges
quickly, and it needs no GPU.
"""

import json
import math
import sys
from pathlib import Path

import bpy

spec = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
params = spec.get("params") or {}
width, height, fps, frames = int(spec["width"]), int(spec["height"]), int(spec.get("fps", 24)), int(spec["frames"])
out = Path(spec["output"])
out.mkdir(parents=True, exist_ok=True)
effect = spec["effect"]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = int(params.get("samples", 12))
scene.cycles.use_denoising = False
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = width, height, 100
scene.render.fps = fps
scene.render.film_transparent = True
scene.frame_start, scene.frame_end = 1, frames
scene.view_settings.view_transform = "Standard"
scene.world = bpy.data.worlds.new("World")
scene.world.color = (0, 0, 0)

camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.collection.objects.link(camera)
camera.location = (0, -12, 0)
camera.rotation_euler = (math.pi / 2, 0, 0)
camera.data.lens = 35
scene.camera = camera


def emissive(name, colour, strength):
    material = bpy.data.materials.new(name)
    if hasattr(material, "use_nodes") and not material.node_tree:
        material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*colour, 1.0)
    emission.inputs["Strength"].default_value = strength
    output = nodes.new("ShaderNodeOutputMaterial")
    material.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
    return material


def hex_colour(value, default):
    text = str(value or default).lstrip("#")
    return tuple(int(text[index:index + 2], 16) / 255 for index in (0, 2, 4))


# The particle itself: a small emissive sphere, instanced.
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=8, ring_count=6, location=(0, 0, -100))
dot = bpy.context.active_object
dot.name = "particle"
colour = hex_colour(params.get("color"), "#FFB347" if effect == "sparks-burst" else "#9FD8FF")
dot.data.materials.append(emissive("glow", colour, float(params.get("glow", 12 if effect == "sparks-burst" else 6))))

if effect == "sparks-burst":
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.15, subdivisions=1, location=(0, 0, float(params.get("height", 0.5))))
    emitter = bpy.context.active_object
    system = emitter.modifiers.new("sparks", "PARTICLE_SYSTEM").particle_system.settings
    emitter.show_instancer_for_render = False  # hiding the emitter itself would hide its particles too
    system.count = int(params.get("count", 400))
    system.frame_start, system.frame_end = 1, max(2, int(frames * 0.25))
    system.lifetime = frames
    system.normal_factor = float(params.get("speed", 6.0))
    system.factor_random = 3.0
    system.effector_weights.gravity = float(params.get("gravity", 1.0))
    system.render_type = "OBJECT"
    system.instance_object = dot
    system.particle_size = float(params.get("size", 0.035))
    system.size_random = 0.6
else:  # disintegrate
    text = str(params.get("text") or "")
    if text:
        bpy.ops.object.text_add(location=(0, 0, 0))
        body = bpy.context.active_object
        body.data.body = text
        body.data.align_x, body.data.align_y = "CENTER", "CENTER"
        body.data.size = float(params.get("text_size", 1.6))
        body.data.extrude = 0.05
        body.rotation_euler = (math.pi / 2, 0, 0)
        bpy.ops.object.convert(target="MESH")
    else:
        bpy.ops.mesh.primitive_cube_add(size=2.5, location=(0, 0, 0))
        body = bpy.context.active_object
    # Enough faces to fall apart finely.
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.subdivide(number_cuts=int(params.get("cuts", 6)))
    bpy.ops.object.mode_set(mode="OBJECT")
    body.data.materials.append(emissive("body", hex_colour(params.get("body_color"), "#E6E6E6"), 2.0))
    start, span = max(1, int(frames * float(params.get("begin", 0.25)))), max(4, int(frames * 0.5))
    build = body.modifiers.new("vanish", "BUILD")
    build.use_reverse, build.use_random_order = True, True
    build.frame_start, build.frame_duration = start, span
    system = body.modifiers.new("dust", "PARTICLE_SYSTEM").particle_system.settings
    system.count = int(params.get("count", 3000))
    system.frame_start, system.frame_end = start, start + span
    system.lifetime = frames
    system.emit_from = "FACE"
    system.normal_factor = 0.3
    system.factor_random = float(params.get("drift", 0.8))
    system.effector_weights.gravity = float(params.get("gravity", -0.15))  # the dust rises a little
    system.render_type = "OBJECT"
    system.instance_object = dot
    system.particle_size = float(params.get("size", 0.02))
    system.size_random = 0.5
    # The particle modifier must read the mesh before it is built away.
    body.modifiers.move(1, 0)

formats = spec.get("formats") or ["exr"]
bpy.ops.wm.save_as_mainfile(filepath=str(out / "element.blend"))
for frame in range(1, frames + 1):
    scene.frame_set(frame)
    for kind in formats:
        settings = scene.render.image_settings
        if kind == "exr":
            settings.file_format, settings.color_depth, settings.color_mode = "OPEN_EXR", "16", "RGBA"
            settings.exr_codec = "ZIP"
            scene.render.filepath = str(out / "exr" / f"f_{frame:04d}.exr")
        else:
            settings.file_format, settings.color_depth, settings.color_mode = "PNG", "8", "RGBA"
            scene.render.filepath = str(out / "png" / f"f_{frame:04d}.png")
        bpy.ops.render.render(write_still=True)
