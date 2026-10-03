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
else:
    dot.hide_render = False


def body_from_params():
    """The thing an effect acts on: the word in `text`, or a box."""

    text = str(params.get("text") or "")
    if text:
        bpy.ops.object.text_add(location=(0, 0, 0))
        body = bpy.context.active_object
        body.data.body = text
        body.data.align_x, body.data.align_y = "CENTER", "CENTER"
        body.data.size = float(params.get("text_size", 1.6))
        body.data.extrude = float(params.get("depth", 0.05))
        body.rotation_euler = (math.pi / 2, 0, 0)
        bpy.ops.object.convert(target="MESH")
    else:
        bpy.ops.mesh.primitive_cube_add(size=2.5, location=(0, 0, 0))
        body = bpy.context.active_object
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.subdivide(number_cuts=int(params.get("cuts", {"shatter": 1, "melt": 8}.get(effect, 6))))
    bpy.ops.object.mode_set(mode="OBJECT")
    body.data.materials.append(emissive("body", hex_colour(params.get("body_color"), "#E6E6E6"), 2.0))
    return body


def sky_emitter(name):
    """A wide plane above the frame, raining particles down through it."""

    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 1, 4.5))
    emitter = bpy.context.active_object
    emitter.name = name
    emitter.scale = (18, 12, 1)
    emitter.rotation_euler = (math.pi, 0, 0)  # its normal points down
    emitter.show_instancer_for_render = False
    return emitter


start = max(1, int(frames * float(params.get("begin", 0.25))))
if effect == "disintegrate":
    body = body_from_params()
    span = max(4, int(frames * 0.5))
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
elif effect == "shatter":
    body = body_from_params()
    system = body.modifiers.new("shards", "PARTICLE_SYSTEM").particle_system.settings
    system.count = len(body.data.polygons)
    system.frame_start = system.frame_end = start
    system.lifetime = frames * 2
    system.emit_from = "FACE"
    system.use_emit_random = False
    system.normal_factor = float(params.get("force", 2.5))
    system.factor_random = float(params.get("scatter", 1.5))
    system.effector_weights.gravity = float(params.get("gravity", 0.6))
    system.render_type = "NONE"
    system.use_rotations, system.angular_velocity_mode, system.angular_velocity_factor = True, "RAND", 6.0
    thick = body.modifiers.new("thickness", "SOLIDIFY")
    thick.thickness = 0.06
    explode = body.modifiers.new("explode", "EXPLODE")
    explode.use_edge_cut = True
    explode.show_unborn, explode.show_alive, explode.show_dead = True, True, True
elif effect == "melt":
    body = body_from_params()
    texture = bpy.data.textures.new("drip", "CLOUDS")
    # Thin, contrasted noise: some columns drip far, others hardly move.
    texture.noise_scale = float(params.get("drip_scale", 0.25))
    texture.contrast = float(params.get("contrast", 2.5))
    texture.use_clamp = True  # values held in 0..1: everything moves down, nothing up
    drip = body.modifiers.new("drip", "DISPLACE")
    # Down in the world: a word is turned to face the camera, so its local "down" is -Y; a box's is -Z.
    downward = "Y" if params.get("text") else "Z"
    drip.texture, drip.direction, drip.texture_coords, drip.mid_level = texture, downward, "GLOBAL", 0.0
    drip.strength = 0.0
    drip.keyframe_insert("strength", frame=start)
    drip.strength = -float(params.get("amount", 1.8))
    drip.keyframe_insert("strength", frame=frames)
    soften = body.modifiers.new("soften", "SMOOTH")
    soften.iterations = 4
    soften.factor = 0.0
    soften.keyframe_insert("factor", frame=start)
    soften.factor = 0.6
    soften.keyframe_insert("factor", frame=frames)
elif effect in ("rain", "snow"):
    emitter = sky_emitter(effect)
    system = emitter.modifiers.new(effect, "PARTICLE_SYSTEM").particle_system.settings
    rain = effect == "rain"
    system.count = int(params.get("count", 2500 if rain else 900))
    # Started before the shot, so the sky is already full on its first frame.
    system.frame_start, system.frame_end = -frames * (2 if rain else 8), frames
    system.lifetime = frames * (3 if rain else 10)
    system.normal_factor = float(params.get("speed", 9.0 if rain else 1.2))
    system.factor_random = 0.2 if rain else 0.6
    system.effector_weights.gravity = float(params.get("gravity", 1.0 if rain else 0.02))
    if not rain:
        system.brownian_factor = float(params.get("drift", 0.25))
    streak = dot
    if rain:
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=1, depth=1, location=(0, 0, -100))
        streak = bpy.context.active_object
        streak.scale = (0.01, 0.01, 0.35)  # a streak of motion, not a drop
        streak.data.materials.append(emissive("rain", hex_colour(params.get("color"), "#BFD6E6"), 1.2))
    else:
        dot.data.materials.clear()
        dot.data.materials.append(emissive("snow", hex_colour(params.get("color"), "#F4F7FA"), 1.5))
    system.render_type = "OBJECT"
    system.instance_object = streak
    system.particle_size = float(params.get("size", 1.0 if rain else 0.03))
    system.size_random = 0.4
elif effect == "lightning":
    import random

    random.seed(int(params.get("seed", 7)))

    def bolt(top, bottom, roughness, depth):
        points = [top, bottom]
        for _ in range(depth):
            refined = [points[0]]
            for a, b in zip(points, points[1:]):
                mid = [(a[i] + b[i]) / 2 for i in range(3)]
                span = math.dist(a, b)
                mid[0] += random.uniform(-1, 1) * span * roughness
                mid[1] += random.uniform(-0.3, 0.3) * span * roughness
                refined += [mid, b]
            points = refined
        return points

    trunk = bolt((random.uniform(-1, 1), 0, 4.2), (random.uniform(-2, 2), 0, -3.5), 0.35, 6)
    paths = [trunk]
    for _ in range(int(params.get("branches", 3))):
        root = trunk[random.randint(len(trunk) // 5, len(trunk) * 3 // 5)]
        end = (root[0] + random.uniform(-2.5, 2.5), 0, root[2] - random.uniform(1.5, 3.5))
        paths.append(bolt(root, end, 0.4, 5))
    curve = bpy.data.curves.new("bolt", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = float(params.get("thickness", 0.025))
    for index, path in enumerate(paths):
        spline = curve.splines.new("POLY")
        spline.points.add(len(path) - 1)
        for point, co in zip(spline.points, path):
            point.co = (*co, 1)
            point.radius = 1.0 if index == 0 else 0.55
    strike = bpy.data.objects.new("lightning", curve)
    scene.collection.objects.link(strike)
    glow = emissive("bolt", hex_colour(params.get("color"), "#CFE3FF"), float(params.get("glow", 25)))
    curve.materials.append(glow)
    # A real strike: a flash, a gap, a re-strike, then gone.
    strength = glow.node_tree.nodes["Emission"].inputs["Strength"]
    for frame, visible, level in ((start - 1, False, 0), (start, True, 1.0), (start + 1, True, 0.8),
                                  (start + 2, False, 0), (start + 3, True, 0.9), (start + 5, True, 0.35),
                                  (start + 7, False, 0)):
        strike.hide_render = not visible
        strike.keyframe_insert("hide_render", frame=max(1, frame))
        strength.default_value = float(params.get("glow", 25)) * level
        strength.keyframe_insert("default_value", frame=max(1, frame))
elif effect == "liquid-splash":
    # A falling mass of water in a small Mantaflow domain, splashing on an invisible floor.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    domain = bpy.context.active_object
    domain.scale = (6, 3, 6)
    fluid = domain.modifiers.new("fluid", "FLUID")
    fluid.fluid_type = "DOMAIN"
    settings = fluid.domain_settings
    settings.domain_type = "LIQUID"
    settings.resolution_max = int(params.get("resolution", 40))
    settings.use_mesh = True
    settings.cache_type = "ALL"
    settings.cache_directory = str(out / "fluid-cache")
    settings.cache_frame_start, settings.cache_frame_end = 1, frames
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.9, location=(0, 0, 1.6))
    source = bpy.context.active_object
    flow = source.modifiers.new("fluid", "FLUID")
    flow.fluid_type = "FLOW"
    flow.flow_settings.flow_type, flow.flow_settings.flow_behavior = "LIQUID", "GEOMETRY"
    flow.flow_settings.use_initial_velocity = True
    flow.flow_settings.velocity_coord = (float(params.get("push", 0.0)), 0, -3.0)
    source.hide_render = True
    water = bpy.data.materials.new("water")
    water.use_nodes = True
    bsdf = water.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*hex_colour(params.get("color"), "#9CC7E0"), 1.0)
    bsdf.inputs["Roughness"].default_value = 0.05
    bsdf.inputs["Transmission Weight"].default_value = float(params.get("clarity", 0.85))
    domain.data.materials.append(water)
    light = bpy.data.objects.new("key", bpy.data.lights.new("key", "SUN"))
    light.data.energy = 3.0
    light.rotation_euler = (math.radians(40), math.radians(20), math.radians(30))
    scene.collection.objects.link(light)
    scene.world.color = (0.4, 0.42, 0.45)
    bpy.context.view_layer.objects.active = domain
    bpy.ops.fluid.bake_all()

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
