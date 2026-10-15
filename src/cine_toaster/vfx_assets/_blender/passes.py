"""Runs inside Blender: a scene's passes, frame by frame, for C8's signal records (CT-0081, step 2).

    blender --background --factory-startup --python passes.py -- spec.json

The spec gives the scene -- a .blend file, or a recipe (objects and a camera's keys, built here, so a test's
geometry is known exactly) -- the camera, the frames, the size, the engine and its samples, and the output
folder. Written there:

- `f_####.exr`: one multilayer float EXR a frame -- Combined (RGBA, premultiplied, linear), Depth (Z), and
  IndexOB (each object's pass index);
- `passes.json`: what made them and how to read them -- Blender's version, the engine and samples, the working
  colour space (Combined is scene-linear in it), the pixel filter, the files a .blend depends on, the scene's
  objects by pass index (a stable table: objects sorted by name, numbered from 1; 0 is no object), and the
  camera at every frame: its projection, lens, sensor and fit, shift, clipping, its matrix in the world (the
  camera looks down its -Z, +Y up, +X right; the world is Z up), and the resolution.

Nothing is decided here about what the depth means: the adapter declares it (`renders.py`: z along the camera's
axis, as measured in CT-0081 and held by `tests/test_renders.py`).
"""

import json
import math
import sys
from pathlib import Path

import bpy

spec = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
out = Path(spec["output"])
out.mkdir(parents=True, exist_ok=True)

if spec.get("blend"):
    bpy.ops.wm.open_mainfile(filepath=spec["blend"])
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    recipe = json.loads(Path(spec["recipe"]).read_text(encoding="utf-8"))
    # A recipe's keys are straight lines between them (Blender 5's layered actions hide their curves, so the
    # interpolation is chosen before keys are made).
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    world = bpy.data.worlds.new("World")
    world.color = (0.05, 0.05, 0.05)
    bpy.context.scene.world = world
    for item in recipe["objects"]:
        kind = item["type"]
        if kind == "plane":
            bpy.ops.mesh.primitive_plane_add(size=1.0, location=item["location"])
        elif kind == "sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=item["radius"], location=item["location"], segments=64,
                                                 ring_count=32)
        elif kind == "cube":
            bpy.ops.mesh.primitive_cube_add(size=item["size"], location=item["location"])
        made = bpy.context.active_object
        made.name = item["name"]
        made.rotation_euler = [math.radians(v) for v in item.get("rotation", [0, 0, 0])]
        if kind == "plane":
            made.scale = (item["size"][0], item["size"][1], 1.0)
        material = bpy.data.materials.new(item["name"])
        material.use_nodes = True
        if item.get("shader") == "emission":  # flat: its own colour, no light, no shadow
            nodes = material.node_tree.nodes
            emission = nodes.new("ShaderNodeEmission")
            emission.inputs["Color"].default_value = list(item["colour"]) + [1.0]
            material.node_tree.links.new(emission.outputs["Emission"], nodes["Material Output"].inputs["Surface"])
        else:
            material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = list(item["colour"]) + [1.0]
        made.data.materials.append(material)
        for key in item.get("keys", []):  # an object that moves: into the frame, out of it
            made.location = key["location"]
            made.keyframe_insert("location", frame=key["frame"])
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 3.0
    light = bpy.data.objects.new("Sun", sun)
    light.rotation_euler = (math.radians(50), 0, math.radians(30))
    bpy.context.scene.collection.objects.link(light)
    lens = recipe["camera"]
    data = bpy.data.cameras.new(lens.get("name", "Camera"))
    data.lens, data.sensor_width = lens.get("lens", 35.0), lens.get("sensor_width", 36.0)
    data.sensor_fit = lens.get("sensor_fit", "HORIZONTAL")
    data.clip_start, data.clip_end = lens.get("clip", [0.1, 1000.0])
    camera = bpy.data.objects.new(lens.get("name", "Camera"), data)
    bpy.context.scene.collection.objects.link(camera)
    for key in lens["keys"]:
        camera.location = key["location"]
        camera.rotation_euler = [math.radians(v) for v in key["rotation"]]
        camera.keyframe_insert("location", frame=key["frame"])
        camera.keyframe_insert("rotation_euler", frame=key["frame"])

scene = bpy.context.scene
scene.camera = bpy.data.objects[spec["camera"]]
scene.render.engine = spec.get("engine", "CYCLES")
if scene.render.engine == "CYCLES":
    scene.cycles.samples = int(spec.get("samples", 8))
    scene.cycles.device = "CPU"
    scene.cycles.use_denoising = False
scene.render.resolution_x, scene.render.resolution_y = int(spec["width"]), int(spec["height"])
scene.render.resolution_percentage = 100
if spec.get("filter_size") is not None:  # the pixel filter's width, in pixels
    scene.render.filter_size = float(spec["filter_size"])
scene.render.film_transparent = True
layer = scene.view_layers[0]
layer.use_pass_z = True
layer.use_pass_object_index = True
settings = scene.render.image_settings
if hasattr(settings, "media_type"):  # Blender 5 chooses a multilayer image by its media type first
    settings.media_type = "MULTI_LAYER_IMAGE"
settings.file_format = "OPEN_EXR_MULTILAYER"
settings.color_depth = "32"
settings.exr_codec = "ZIP"

# The object table: every mesh, sorted by name, numbered from 1 -- the same scene gives the same numbers.
meshes = sorted((item for item in scene.objects if item.type == "MESH"), key=lambda item: item.name)
for number, item in enumerate(meshes, 1):
    item.pass_index = number
objects = {str(item.pass_index): item.name for item in meshes}

cameras = []
for frame in range(int(spec["first"]), int(spec["last"]) + 1):
    scene.frame_set(frame)
    scene.render.filepath = str(out / f"f_{frame - int(spec['first']) + 1:04d}")
    bpy.ops.render.render(write_still=True)
    view = scene.camera
    data = view.data
    cameras.append({
        "frame": frame, "type": data.type, "lens_mm": data.lens, "sensor_mm": [data.sensor_width, data.sensor_height],
        "sensor_fit": data.sensor_fit, "shift": [data.shift_x, data.shift_y], "clip": [data.clip_start, data.clip_end],
        "matrix_world": [list(row) for row in view.matrix_world],
    })

# What a .blend reaches outside itself (textures, libraries, caches): the adapter pins them by hash.
dependencies = sorted({str(Path(path)) for path in bpy.utils.blend_paths(absolute=True)}) if spec.get("blend") else []
working = getattr(getattr(bpy.data, "colorspace", None), "working_space", None) or "Linear Rec.709"

(out / "passes.json").write_text(json.dumps({
    "blender": bpy.app.version_string, "engine": scene.render.engine, "working_space": working,
    "filter_size": scene.render.filter_size, "dependencies": dependencies,
    "samples": int(getattr(scene.cycles, "samples", 0)) if scene.render.engine == "CYCLES" else None,
    "resolution": [scene.render.resolution_x, scene.render.resolution_y],
    "pixel_aspect": [scene.render.pixel_aspect_x, scene.render.pixel_aspect_y],
    "unit": {"system": scene.unit_settings.system, "scale_length": scene.unit_settings.scale_length},
    "camera": spec["camera"], "objects": objects, "cameras": cameras,
    "conventions": "camera looks down -Z, +Y up, +X right; world Z up; pixels top-left first, rows down",
}, indent=1), encoding="utf-8")
