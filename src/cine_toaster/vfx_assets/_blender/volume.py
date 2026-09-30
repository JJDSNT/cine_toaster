"""Runs inside Blender: an OpenVDB volume rendered as a VFX element (CT-0047).

    blender --background --factory-startup --python volume.py -- spec.json

The spec's `volume` is a `.vdb` file (or a `%04d` sequence of them, one per
frame). It is imported, centred and scaled to fill the frame, shaded with a
Principled Volume — its `density` grid as density and, when it has one, its
`temperature` grid as blackbody emission (fire) — lit by a sun, and turned
slowly about its vertical axis (`spin`, degrees over the shot). Cycles on the
CPU, transparent background, scene-linear EXR with alpha.
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
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = int(params.get("samples", 16))
scene.cycles.use_denoising = False
scene.cycles.volume_step_rate = float(params.get("step_rate", 4.0))  # coarser steps: much faster, still smooth
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = width, height, 100
scene.render.fps = fps
scene.render.film_transparent = True
scene.frame_start, scene.frame_end = 1, frames
scene.view_settings.view_transform = "Standard"
scene.world = bpy.data.worlds.new("World")
scene.world.color = (0.02, 0.02, 0.025)

source = spec["volume"]
sequence = "%" in source
first = source % 1 if sequence else source
bpy.ops.object.volume_import(filepath=first)
volume = bpy.context.active_object
if sequence:
    volume.data.is_sequence = True
    volume.data.frame_duration = frames
volume.data.grids.load()
grids = {grid.name for grid in volume.data.grids}

# Centre it and scale it to about 4 units across.
corners = [volume.matrix_world @ Vector(corner) for corner in volume.bound_box]
centre = sum(corners, Vector()) / 8
size = max(max(c[i] for c in corners) - min(c[i] for c in corners) for i in range(3)) or 1.0
pivot = bpy.data.objects.new("pivot", None)
scene.collection.objects.link(pivot)
volume.parent = pivot
volume.location = -centre
scale = float(params.get("size", 4.0)) / size
pivot.scale = (scale, scale, scale)

material = bpy.data.materials.new("vdb")
material.use_nodes = True
nodes = material.node_tree.nodes
principled = nodes.get("Principled BSDF")
if principled:
    nodes.remove(principled)
shader = nodes.new("ShaderNodeVolumePrincipled")
shader.inputs["Density"].default_value = float(params.get("density", 2.0))
shader.inputs["Density Attribute"].default_value = "density"
colour = str(params.get("smoke_color") or "#8a8a8a").lstrip("#")
shader.inputs["Color"].default_value = (*(int(colour[i:i + 2], 16) / 255 for i in (0, 2, 4)), 1.0)
if "temperature" in grids and float(params.get("fire", 1.0)) > 0:
    # Simulations store temperature in their own units (often about 0 to 2): scaled to kelvin here.
    shader.inputs["Blackbody Intensity"].default_value = float(params.get("fire", 1.0))
    shader.inputs["Temperature Attribute"].default_value = ""
    attribute = nodes.new("ShaderNodeAttribute")
    attribute.attribute_name = "temperature"
    kelvin = nodes.new("ShaderNodeMath")
    kelvin.operation = "MULTIPLY"
    kelvin.inputs[1].default_value = float(params.get("temperature", 2400.0))
    material.node_tree.links.new(attribute.outputs["Fac"], kelvin.inputs[0])
    material.node_tree.links.new(kelvin.outputs[0], shader.inputs["Temperature"])
material.node_tree.links.new(shader.outputs["Volume"], nodes["Material Output"].inputs["Volume"])
volume.data.materials.append(material)

sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = float(params.get("light", 4.0))
sun.rotation_euler = (math.radians(50), math.radians(20), math.radians(35))
scene.collection.objects.link(sun)

camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.collection.objects.link(camera)
camera.location = (0, -11, 0.5)
camera.rotation_euler = (math.radians(88), 0, 0)
camera.data.lens = 35
scene.camera = camera

spin = math.radians(float(params.get("spin", 30.0)))
pivot.rotation_euler = (0, 0, 0)
pivot.keyframe_insert("rotation_euler", frame=1)
pivot.rotation_euler = (0, 0, spin)
pivot.keyframe_insert("rotation_euler", frame=frames)

settings = scene.render.image_settings
settings.file_format, settings.color_depth, settings.color_mode, settings.exr_codec = "OPEN_EXR", "16", "RGBA", "ZIP"
bpy.ops.wm.save_as_mainfile(filepath=str(Path(spec["output"]) / "volume.blend"))
for frame in range(1, frames + 1):
    scene.frame_set(frame)
    scene.render.filepath = str(out / f"f_{frame:04d}.exr")
    bpy.ops.render.render(write_still=True)
