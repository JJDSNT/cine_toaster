"""C8 step 2 (CT-0081): a Blender scene's passes as production records -- rendered apart, read by the graph.

A scene of known geometry (a wall, a ball and a box at known places; the camera dollying in) is rendered, and
every pass is checked against it by number: each pixel's depth, taken back through the recorded camera of its
frame, lands on the surface its object index names."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from cine_toaster import renders, signals
from cine_toaster.color import exr_layers
from cine_toaster.compositing.reference import _fill_from_neighbours, evaluate
from cine_toaster.errors import ValidationError
from cine_toaster.state import Actor
from cine_toaster.titles import blender_binary

sys.path.insert(0, str(Path(__file__).parent))
from heavy import heavy  # noqa: E402

TOOL = Actor(id="renderer", kind="system")
W, H = 96, 54
WALL_Y, BALL, RADIUS, BOX, HALF = 10.0, np.array([-1.5, 4.0, 0.0]), 0.8, np.array([1.6, 6.0, 0.3]), 0.5
POST, POST_HALF = np.array([1.0, 2.6, -0.5]), 0.15
DRONE, DRONE_RADIUS = np.array([[6.0, 8.0, 1.2], [0.5, 8.0, 1.2]]), 0.3


def drone_at(index: int) -> np.ndarray:
    return DRONE[0] + (DRONE[1] - DRONE[0]) * index / 2
RECIPE = {
    "objects": [
        {"name": "wall", "type": "plane", "size": [8, 24], "location": [0, WALL_Y, 0], "rotation": [90, 0, 0],
         "colour": [0.6, 0.6, 0.65]},
        {"name": "ball", "type": "sphere", "radius": RADIUS, "location": BALL.tolist(), "colour": [0.8, 0.2, 0.1]},
        {"name": "box", "type": "cube", "size": 2 * HALF, "location": BOX.tolist(), "colour": [0.1, 0.4, 0.8]},
        # Seen only in the first frame: the dolly passes it.
        {"name": "post", "type": "cube", "size": 2 * POST_HALF, "location": POST.tolist(), "colour": [0.9, 0.9, 0.1]},
        # Out of the frame at first, flying in.
        {"name": "drone", "type": "sphere", "radius": DRONE_RADIUS, "location": DRONE[0].tolist(),
         "colour": [0.2, 0.8, 0.3], "keys": [{"frame": 1, "location": DRONE[0].tolist()},
                                              {"frame": 3, "location": DRONE[1].tolist()}]}],
    # The camera dollies 2 m toward the wall over three frames, looking down +Y with +Z up.
    "camera": {"name": "cam", "lens": 35, "sensor_width": 36,
               "keys": [{"frame": 1, "location": [0, 0, 0], "rotation": [90, 0, 0]},
                        {"frame": 3, "location": [0, 2, 0], "rotation": [90, 0, 0]}]},
}


def production(root: Path) -> None:
    (root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
    (root / "scenes").mkdir()
    (root / "scenes" / "room.json").write_text(json.dumps(RECIPE))


def unproject(depth: np.ndarray, camera: dict) -> np.ndarray:
    """Every pixel's point in the world, its depth taken as z along the camera's axis (the recorded camera:
    intrinsics in pixels, rows down; looking down its -Z, +Y up; its matrix camera to world)."""

    k = camera["intrinsics"]
    rows, cols = np.indices(depth.shape, dtype=np.float64) + 0.5
    x = (cols - k["cx"]) / k["fx"] * depth
    y = -(rows - k["cy"]) / k["fy"] * depth
    points = np.stack([x, y, -depth.astype(np.float64), np.ones_like(x)], axis=-1)
    return (points @ np.asarray(camera["matrix_world"]).T)[..., :3]


class Refusals(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        production(self.root)

    def test_without_blender_it_says_what_to_install(self) -> None:
        with mock.patch("cine_toaster.titles.blender_binary", return_value=None):
            with self.assertRaisesRegex(ValidationError, "blender.org"):
                renders.render_passes(self.root, render_id="room", camera="cam", first=1, last=3, size=(W, H),
                                      fps=24, recipe="scenes/room.json", actor=TOOL)

    def test_a_scene_outside_the_production_is_refused(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json") as outside:
            with self.assertRaisesRegex(ValidationError, "outside the production"):
                renders.render_passes(self.root, render_id="room", camera="cam", first=1, last=3, size=(W, H),
                                      fps=24, recipe=outside.name, actor=TOOL, blender="/bin/false")

    def test_a_graph_never_renders(self) -> None:
        # Without a render's record the reference refuses generate.render, naming how to make one.
        graph = {"output": "r", "nodes": {"r": {"op": "generate.render", "renderer": "blender", "camera": "c"}}}
        with self.assertRaisesRegex(ValidationError, "render_passes"):
            evaluate(graph, {}, frames=1, size=(W, H), fps=24, root=self.root)

    def test_every_part_of_a_multipart_exr_is_read(self) -> None:
        import OpenEXR

        path = self.root / "parts.exr"
        combined = np.random.default_rng(1).random((4, 6, 4)).astype(np.float32)
        depth = np.full((4, 6), 7.0, np.float32)
        header = lambda name: {"type": OpenEXR.scanlineimage, "compression": OpenEXR.ZIP_COMPRESSION, "name": name}
        # As Blender 5 writes a multilayer EXR: one part a pass.
        OpenEXR.File([OpenEXR.Part(header("ViewLayer.Combined"), {"ViewLayer.Combined": combined}, "ViewLayer.Combined"),
                      OpenEXR.Part(header("ViewLayer.Depth"), {"ViewLayer.Depth.Z": depth}, "ViewLayer.Depth")]
                     ).write(str(path))
        layers = exr_layers(path)
        np.testing.assert_array_equal(layers["Depth"], depth)
        np.testing.assert_array_equal(layers["Combined"], combined)
        from cine_toaster.color import read_exr

        np.testing.assert_array_equal(read_exr(path), combined)  # a multilayer file's picture is its Combined


class ExrFiles(unittest.TestCase):
    """Plain and multilayer EXRs, one part or one a pass, read by name and never by guess; special depths."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        production(self.root)
        import OpenEXR

        self.exr = OpenEXR
        self.depth = np.full((9, 16), 4.0, np.float32)
        self.depth[:, 8:] = np.inf  # nothing hit on the right
        self.header = {"type": OpenEXR.scanlineimage, "compression": OpenEXR.ZIP_COMPRESSION}

    def write(self, name: str, channels: dict) -> Path:
        path = self.root / name
        self.exr.File(self.header, {key: np.ascontiguousarray(value, np.float32) for key, value in channels.items()}
                      ).write(str(path))
        return path

    def read(self, name: str, size=(16, 9), **node) -> np.ndarray:
        graph = {"output": "out", "nodes": {
            "z": {"op": "signal.read", "file": name, "kind": "depth", "camera": "c", **node},
            "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
            "black": {"op": "generate.solid", "colour": [0, 0, 0, 1]},
            "m": {"op": "matte.from_signal", "signal": "z", "low": 0.0, "high": 8.0},
            "out": {"op": "merge.over", "front": "white", "back": "black", "matte": "m"}}}
        return evaluate(graph, {}, frames=1, size=size, fps=24, root=self.root)[0]

    def test_a_plain_exr_of_one_channel_is_its_depth(self) -> None:
        self.write("z.exr", {"Z": self.depth})
        out = self.read("z.exr")
        np.testing.assert_allclose(out[:, :8, 0], 0.5)  # 4 m of 0..8
        np.testing.assert_allclose(out[:, 8:, 0], 1.0)  # +inf: as far as can be, never nan

    def test_a_plain_rgba_exr_is_not_a_depth_by_its_red(self) -> None:
        self.write("rgba.exr", {"R": self.depth, "G": self.depth, "B": self.depth, "A": np.ones_like(self.depth)})
        with self.assertRaisesRegex(ValidationError, "4 channels"):
            self.read("rgba.exr")

    def test_a_multilayer_exr_in_one_part_is_read_by_layer(self) -> None:
        # As Blender 4 writes it: every pass in one part.
        self.write("one.exr", {**{f"ViewLayer.Combined.{c}": np.zeros_like(self.depth) for c in "RGBA"},
                               "ViewLayer.Depth.Z": self.depth,
                               **{f"ViewLayer.Normal.{c}": np.ones_like(self.depth) for c in "XYZ"}})
        layers = exr_layers(self.root / "one.exr")
        self.assertEqual({name: layer.shape for name, layer in layers.items()},
                         {"Combined": (9, 16, 4), "Depth": (9, 16), "Normal": (9, 16, 3)})
        with self.assertRaisesRegex(ValidationError, "Combined, Depth, Normal"):
            self.read("one.exr")  # several layers, none named: refused, not the first
        np.testing.assert_allclose(self.read("one.exr", layer="Depth")[:, :8, 0], 0.5)
        with self.assertRaisesRegex(ValidationError, "no layer"):
            self.read("one.exr", layer="Mist")
        with self.assertRaisesRegex(ValidationError, "3 channels"):
            self.read("one.exr", layer="Normal")

    def test_two_layers_of_one_name_are_refused(self) -> None:
        self.write("two.exr", {"ViewLayer.Depth.Z": self.depth, "Other.Depth.Z": self.depth + 1})
        with self.assertRaisesRegex(ValidationError, "two layers"):
            exr_layers(self.root / "two.exr")

    def test_infinity_survives_a_resize_and_nan_is_never_recorded(self) -> None:
        self.write("z.exr", {"Z": self.depth})
        out = self.read("z.exr", size=(32, 18))  # depths resized to the nearest: no blend of 4 m and +inf
        self.assertFalse(np.isnan(out).any())
        self.assertEqual(set(np.unique(out[..., 0]).round(4)), {0.5, 1.0})
        for bad in (np.nan, -np.inf):
            frame = self.depth.copy()
            frame[0, 0] = bad
            with self.assertRaises(ValidationError):
                signals.record_signal(self.root, signal_id="z", kind="depth", origin="geometric", frames=[frame],
                                      rate=24, actor=TOOL, camera="c", depth={"quantity": "z", "unit": "m"})
        signals.record_signal(self.root, signal_id="z", kind="depth", origin="geometric", frames=[self.depth],
                              rate=24, actor=TOOL, camera="c", depth={"quantity": "z", "unit": "m"})
        self.assertTrue(np.isinf(signals.frame(self.root, "z", 0)[:, 8:]).all())


@heavy("renders a scene's passes with Blender")
@unittest.skipUnless(blender_binary(), "Blender is not installed")
class BlenderPasses(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        production(cls.root)
        cls.made = renders.render_passes(cls.root, render_id="room", camera="cam", first=1, last=3, size=(W, H),
                                         fps=24, recipe="scenes/room.json", samples=4, actor=TOOL)
        cls.manifest = renders.load_render(cls.root, "room")
        cls.depth = signals.SignalReader(cls.root, "room-depth")
        cls.objects = signals.SignalReader(cls.root, "room-objects")
        cls.table = {name: int(number) for number, name in cls.manifest["objects"].items()}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def test_the_records_say_what_made_them(self) -> None:
        import subprocess

        made = subprocess.run([blender_binary(), "--version"], capture_output=True, text=True).stdout
        self.assertIn(self.manifest["renderer"]["version"], made)
        self.assertEqual(self.manifest["renderer"]["engine"], "CYCLES")
        self.assertEqual(self.manifest["renderer"]["samples"], 4)
        self.assertEqual(self.manifest["resolution"], [W, H])
        self.assertEqual(len(self.manifest["camera"]["frames"]), 3)
        record = signals.load_record(self.root, "room-depth")
        self.assertEqual((record["kind"], record["origin"], record["camera"]), ("depth", "geometric", "room/cam"))
        self.assertEqual((record["depth"]["quantity"], record["depth"]["unit"]), ("z", "m"))
        maker = record["provenance"][-1]["maker"]
        self.assertEqual((maker["name"], maker["pass"], maker["version"]), ("blender", "Depth",
                                                                             self.manifest["renderer"]["version"]))
        self.assertEqual(signals.status(self.root, "room-depth")["quality"], "unknown")  # nothing invented

    def test_the_object_table_is_stable(self) -> None:
        names = {"1": "ball", "2": "box", "3": "drone", "4": "post", "5": "wall"}  # by name, from 1
        self.assertEqual(self.manifest["objects"], names)
        self.assertEqual(signals.load_record(self.root, "room-objects")["labels"],
                         {0: "nothing", **{int(key): name for key, name in names.items()}})

    def test_an_object_keeps_its_number_entering_and_leaving_the_frame(self) -> None:
        present = [set(np.unique(self.objects.frame(index)).tolist()) for index in range(3)]
        post, drone = self.table["post"], self.table["drone"]
        counts = lambda number: [int((self.objects.frame(index) == number).sum()) for index in range(3)]
        seen = counts(post)
        self.assertTrue(seen[0] > seen[1] > 0 and seen[2] == 0, seen)  # leaving as the dolly passes it
        seen = counts(drone)
        self.assertTrue(seen[0] == 0 and 0 < seen[1] < seen[2], seen)  # flying in
        # Whoever is in a frame, the numbers mean the same objects: each label's pixels lie on its own object
        # (the surfaces test below), and every frame uses only the table's numbers.
        for labels in present:
            self.assertLessEqual(labels, {0, *map(int, self.manifest["objects"])})

    def test_depth_is_z_along_the_axis_and_lands_on_the_surfaces_every_frame(self) -> None:
        for index in range(3):
            camera = self.manifest["camera"]["frames"][index]
            self.assertAlmostEqual(camera["matrix_world"][1][3], float(index), places=5)  # the dolly
            depth, labels = self.depth.frame(index), self.objects.frame(index)
            wall, ball, box = (labels == self.table[name] for name in ("wall", "ball", "box"))
            # The wall is square to the camera: z is its distance down the axis everywhere, corners included
            # (a distance along each ray would grow toward the corners).
            np.testing.assert_allclose(depth[wall], WALL_Y - index, atol=1e-4)
            points = unproject(np.where(np.isfinite(depth), depth, 0.0), camera)
            np.testing.assert_allclose(points[wall][:, 1], WALL_Y, atol=1e-3)
            # Away from silhouettes (the passes are not anti-aliased: one surface a pixel, sampled anywhere in
            # it), each object's points are on its surface.
            inner = lambda mask: mask & np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1)
            on_ball = np.linalg.norm(points[inner(ball)] - BALL, axis=1)
            np.testing.assert_allclose(on_ball, RADIUS, atol=0.02)
            on_box = np.abs(points[inner(box)] - BOX).max(axis=1)
            np.testing.assert_allclose(on_box, HALF, atol=0.02)
            self.assertGreater(int(inner(ball).sum()), 20)
            post, drone = labels == self.table["post"], labels == self.table["drone"]
            np.testing.assert_allclose(np.abs(points[inner(post)] - POST).max(axis=1), POST_HALF, atol=0.02)
            np.testing.assert_allclose(np.linalg.norm(points[inner(drone)] - drone_at(index), axis=1),
                                       DRONE_RADIUS, atol=0.02)
            # Nothing hit: no object, and farther than anything.
            empty = labels == 0
            self.assertTrue(empty.any())
            self.assertTrue(np.isinf(depth[empty]).all() and np.isfinite(depth[~empty]).all())

    def test_the_ball_shows_where_the_camera_projects_it(self) -> None:
        seen = 0
        for index in range(3):
            k = self.manifest["camera"]["frames"][index]["intrinsics"]
            z = BALL[1] - index
            col, row = k["cx"] + k["fx"] * BALL[0] / z, k["cy"] - k["fy"] * BALL[2] / z
            if 0 <= col < W and 0 <= row < H:  # by the last frame the dolly has passed it out of the frame
                self.assertEqual(int(self.objects.frame(index)[int(row), int(col)]), self.table["ball"])
                seen += 1
        self.assertEqual(seen, 2)

    def test_the_graph_reads_the_render_and_its_signals(self) -> None:
        signals.record_signal(self.root, signal_id="card-z", kind="depth", origin="authored", rate=24, actor=TOOL,
                              frames=[np.full((H, W), 7.0, np.float32)] * 3, camera="room/cam",
                              depth={"quantity": "z", "unit": "m", "near_is_small": True})
        graph = {"output": "out", "nodes": {
            "r": {"op": "generate.render", "render": "room", "camera": "room/cam"},
            "card": {"op": "generate.solid", "colour": [0, 1, 0, 1]},
            "cz": {"op": "signal.read", "signal": "card-z", "kind": "depth", "camera": "room/cam"},
            "out": {"op": "merge.depth", "pictures": ["r", "card"], "depths": ["r.depth", "cz"]}}}
        out = evaluate(graph, {}, frames=3, size=(W, H), fps=24, root=self.root)
        soft = kept = 0
        for index in range(3):
            labels, picture = self.objects.frame(index), renders.RenderReader(self.root, "room").picture(index)
            depth = self.depth.frame(index)
            alpha = picture[..., 3:]
            # The render's depth carried into the pixels its picture covers where its one sample missed (CT-0081
            # step 5): a silhouette's soft edge stays with its object instead of falling behind the card.
            missed = (alpha[..., 0] > 0) & np.isinf(depth)
            covered = _fill_from_neighbours(depth, missed, 2)
            nearer = covered < 7.0
            # In front of the card at 7 m: the render, over the card by its alpha; behind it: the card.
            np.testing.assert_allclose(out[index][nearer], (picture + (1 - alpha) * [0, 1, 0, 1])[nearer], atol=1e-6)
            # Behind, the background included: nothing hit and nothing covering is +inf, farther than the card.
            self.assertTrue(np.isinf(depth[labels == 0]).all())
            self.assertLess(float(np.abs(out[index][~nearer] - [0, 1, 0, 1]).max()), 1e-6)
            self.assertFalse(np.isnan(out[index]).any())
            soft += int(((alpha[..., 0] > 0) & (alpha[..., 0] < 1) & nearer).sum())
            kept += int((missed & nearer).sum())
        self.assertGreater(soft, 0)  # such edges were there to test
        self.assertGreater(kept, 0)  # edge pixels whose sample missed, kept with their object: no halo
        # Its alpha and depth come with the picture, of the same frame.
        graph = {"output": "out", "nodes": {"r": {"op": "generate.render", "render": "room"},
                                           "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
                                           "black": {"op": "generate.solid", "colour": [0, 0, 0, 1]},
                                           "out": {"op": "merge.over", "front": "white", "back": "black",
                                                   "matte": "r.alpha"}}}
        out = evaluate(graph, {}, frames=3, size=(W, H), fps=24, root=self.root)
        for index in range(3):
            np.testing.assert_allclose(out[index][..., 0], renders.RenderReader(self.root, "room").picture(index)[..., 3],
                                       atol=1e-6)
        # A depth read as from another camera is refused.
        graph = {"output": "r", "nodes": {"r": {"op": "generate.render", "render": "room", "camera": "other"}}}
        with self.assertRaises(ValidationError):
            evaluate(graph, {}, frames=1, size=(W, H), fps=24, root=self.root)


BUILD_BLEND = """
import bpy, sys
path, texture = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 5, 0), rotation=(1.5708, 0, 0))
plane = bpy.context.active_object
plane.name = "card"
material = bpy.data.materials.new("card")
material.use_nodes = True
image = material.node_tree.nodes.new("ShaderNodeTexImage")
image.image = bpy.data.images.load(texture)
material.node_tree.links.new(image.outputs["Color"], material.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
plane.data.materials.append(material)
data = bpy.data.cameras.new("cam")
camera = bpy.data.objects.new("cam", data)
camera.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.collection.objects.link(camera)
bpy.ops.wm.save_as_mainfile(filepath=path, relative_remap=True)
"""


def png(path: Path, value: int) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), (value, value, value)).save(path)


@heavy("renders scenes with Blender, several times")
@unittest.skipUnless(blender_binary(), "Blender is not installed")
class Invalidation(unittest.TestCase):
    def render(self, root: Path, **scene) -> None:
        renders.render_passes(root, render_id="room", camera="cam", first=1, last=1, size=(32, 18), fps=24,
                              samples=1, actor=TOOL, **(scene or {"recipe": "scenes/room.json"}))

    def stale_everywhere(self, root: Path, what: str) -> None:
        stale = renders.status(root, "room")["stale"]
        self.assertTrue(any(what in reason for reason in stale), stale)
        for name in ("room-depth", "room-objects"):
            self.assertTrue(any(what in reason for reason in signals.status(root, name)["stale"]), name)

    def test_a_changed_camera_makes_render_and_signals_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            production(root)
            self.render(root)
            moved = json.loads(json.dumps(RECIPE))
            moved["camera"]["lens"] = 50
            (root / "scenes" / "room.json").write_text(json.dumps(moved))
            self.stale_everywhere(root, "scenes/room.json")

    def test_a_file_the_scene_reaches_is_pinned_and_its_change_seen(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            production(root)
            png(root / "textures" / "card.png", 200)
            script = root / "build.py"
            script.write_text(BUILD_BLEND)
            subprocess.run([blender_binary(), "--background", "--factory-startup", "--python", str(script), "--",
                            str(root / "scenes" / "card.blend"), str(root / "textures" / "card.png")],
                           check=True, capture_output=True)
            self.render(root, blend="scenes/card.blend")
            manifest = renders.load_render(root, "room")
            self.assertEqual([item["file"] for item in manifest["scene"]["dependencies"]], ["textures/card.png"])
            self.assertEqual(manifest["objects"], {"1": "card"})
            self.assertEqual(renders.status(root, "room")["stale"], [])
            png(root / "textures" / "card.png", 40)
            self.stale_everywhere(root, "textures/card.png")
            # A file outside the production cannot be pinned: refused, not ignored.
            with tempfile.TemporaryDirectory() as elsewhere:
                png(Path(elsewhere) / "card.png", 200)
                subprocess.run([blender_binary(), "--background", "--factory-startup", "--python", str(script), "--",
                                str(root / "scenes" / "far.blend"), str(Path(elsewhere) / "card.png")],
                               check=True, capture_output=True)
                with self.assertRaisesRegex(ValidationError, "outside the production"):
                    renders.render_passes(root, render_id="far", camera="cam", first=1, last=1, size=(32, 18),
                                          fps=24, samples=1, actor=TOOL, blend="scenes/far.blend")

    def test_a_changed_passes_script_makes_the_render_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            production(root)
            self.render(root)
            other = root / "passes.py"
            other.write_text(renders.SCRIPT.read_text() + "\n# changed\n")
            with mock.patch.object(renders, "SCRIPT", other):
                self.assertTrue(any("script" in reason for reason in renders.status(root, "room")["stale"]))

    def test_an_engine_whose_z_was_not_measured_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            production(root)
            with self.assertRaisesRegex(ValidationError, "measured"):
                renders.render_passes(root, render_id="room", camera="cam", first=1, last=1, size=(32, 18), fps=24,
                                      recipe="scenes/room.json", engine="BLENDER_EEVEE", actor=TOOL)

    def test_a_changed_scene_makes_the_render_and_its_signals_stale_until_rendered_again(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            production(root)
            renders.render_passes(root, render_id="room", camera="cam", first=1, last=1, size=(32, 18), fps=24,
                                  recipe="scenes/room.json", samples=1, actor=TOOL)
            self.assertEqual(renders.status(root, "room")["stale"], [])
            moved = json.loads(json.dumps(RECIPE))
            moved["objects"][1]["location"] = [-1.5, 3.0, 0.0]
            (root / "scenes" / "room.json").write_text(json.dumps(moved))
            stale = renders.status(root, "room")["stale"]
            self.assertTrue(any("scenes/room.json" in reason for reason in stale))
            self.assertTrue(signals.status(root, "room-depth")["stale"])
            graph = {"output": "r", "nodes": {"r": {"op": "generate.render", "render": "room"}}}
            with self.assertRaisesRegex(ValidationError, "stale"):
                evaluate(graph, {}, frames=1, size=(32, 18), fps=24, root=root)
            renders.render_passes(root, render_id="room", camera="cam", first=1, last=1, size=(32, 18), fps=24,
                                  recipe="scenes/room.json", samples=1, actor=TOOL)
            self.assertEqual(renders.status(root, "room")["stale"], [])
            self.assertEqual(renders.load_render(root, "room")["objects"],
                             {"1": "ball", "2": "box", "3": "drone", "4": "post", "5": "wall"})  # rendered again, the same
            self.assertEqual(evaluate(graph, {}, frames=1, size=(32, 18), fps=24, root=root).shape, (1, 18, 32, 4))


if __name__ == "__main__":
    unittest.main()
