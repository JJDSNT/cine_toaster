"""C8 step 5 (CT-0081): depth compositing at edges -- three states kept apart (a depth known, nothing there,
unknown), each layer's depth carried into the pixels its picture covers, measured against a truth.

Synthetic first, where the truth is exact (a disc supersampled 16 times a pixel); then, heavy, a rendered
scene: a ball, a pillar and a room rendered apart and together, flat-shaded so only edges differ."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cine_toaster import signals
from cine_toaster.compositing.reference import evaluate, merge_by_depth
from cine_toaster.compositing.schema import validate
from cine_toaster.errors import ValidationError
from cine_toaster.state import Actor
from cine_toaster.titles import blender_binary

sys.path.insert(0, str(Path(__file__).parent))
from heavy import heavy, needs  # noqa: E402

TOOL = Actor(id="compositor", kind="system")
W, H, S = 48, 32, 16
RED, GREEN = np.array([1.0, 0.0, 0.0, 1.0], np.float32), np.array([0.0, 1.0, 0.0, 1.0], np.float32)


def disc(centre: tuple[float, float] = (20.3, 15.7), radius: float = 9.2) -> tuple[np.ndarray, np.ndarray]:
    """A disc's coverage (supersampled S x S a pixel) and its one-sample depth mask (the pixel's centre)."""

    rows, cols = np.indices((H * S, W * S), dtype=np.float64)
    inside = ((cols + 0.5) / S - centre[0]) ** 2 + ((rows + 0.5) / S - centre[1]) ** 2 < radius ** 2
    coverage = inside.reshape(H, S, W, S).mean(axis=(1, 3)).astype(np.float32)
    rows, cols = np.indices((H, W), dtype=np.float64)
    centre_hit = (cols + 0.5 - centre[0]) ** 2 + (rows + 0.5 - centre[1]) ** 2 < radius ** 2
    return coverage, centre_hit


def layers(near: float = 3.0, far: float = 5.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    coverage, hit = disc()
    front = coverage[..., None] * RED  # premultiplied
    card = np.broadcast_to(GREEN, (H, W, 4)).copy()
    pictures = np.stack([front, card])
    depths = np.stack([np.where(hit, near, np.inf), np.full((H, W), far)]).astype(np.float32)
    truth = front + (1 - coverage[..., None]) * card
    return pictures, depths, truth


class Edges(unittest.TestCase):
    def test_a_layer_keeps_its_soft_edge_where_its_one_depth_sample_missed(self) -> None:
        pictures, depths, truth = layers()
        hard, _ = merge_by_depth("m", 0, pictures, depths, ["a", "b"], edges="hard")
        covered, _ = merge_by_depth("m", 0, pictures, depths, ["a", "b"])
        edge = (pictures[0][..., 3] > 0) & (pictures[0][..., 3] < 1)
        hard_error = float(np.abs(hard - truth)[edge].mean())
        covered_error = float(np.abs(covered - truth)[edge].mean())
        self.assertGreater(hard_error, 0.05)  # the halo: the card drawn over the disc's soft edge
        self.assertLess(covered_error, 1e-6)  # exact: the disc in front, over the card by its coverage

    def test_coverage_never_puts_a_layer_in_front_of_what_is_nearer(self) -> None:
        # The disc behind the card: carrying its depth into its edge changes nothing -- the card covers it.
        pictures, depths, _ = layers(near=6.0, far=5.0)
        covered, _ = merge_by_depth("m", 0, pictures, depths, ["a", "b"])
        np.testing.assert_allclose(covered, np.broadcast_to(GREEN, (H, W, 4)))

    def test_the_merged_depth_keeps_three_states(self) -> None:
        coverage, hit = disc()
        front = coverage[..., None] * RED
        back = np.zeros((H, W, 4), np.float32)
        back[:, W // 2:] = GREEN  # the right half only: nothing at all on the left, outside the disc
        unknown = np.zeros((H, W), bool)
        unknown[H // 2:, W // 2:] = True  # the bottom right: its picture shows, its depth is not known
        depths = np.stack([np.where(hit, 3.0, np.inf), np.where(unknown, np.nan, 5.0)]).astype(np.float32)
        _, merged = merge_by_depth("m", 0, np.stack([front, back]), depths, ["a", "b"], unknown="behind")
        self.assertTrue((merged[hit] == 3.0).all())  # known: the nearest layer's
        nothing = (coverage == 0) & (np.arange(W)[None, :] < W // 2)
        self.assertTrue(np.isposinf(merged[nothing]).all())  # nothing there: +inf
        unknown_shown = unknown & (coverage == 0)
        self.assertTrue(np.isnan(merged[unknown_shown]).all())  # unknown stays unknown, not far, not 5
        known_back = ~unknown & (coverage == 0) & (np.arange(W)[None, :] >= W // 2)
        self.assertTrue((merged[known_back] == 5.0).all())

    def test_coverage_does_not_turn_an_unknown_depth_into_a_known_one(self) -> None:
        coverage, hit = disc()
        depth = np.where(hit, 3.0, np.inf).astype(np.float32)
        depth[hit & (np.arange(W)[None, :] > 22)] = np.nan  # half the disc unknown
        pictures = np.stack([coverage[..., None] * RED, np.broadcast_to(GREEN, (H, W, 4))])
        depths = np.stack([depth, np.full((H, W), 5.0, np.float32)])
        with self.assertRaisesRegex(ValidationError, "unknown"):
            merge_by_depth("m", 0, pictures, depths, ["a", "b"])
        _, merged = merge_by_depth("m", 0, pictures, depths, ["a", "b"], unknown="front")
        self.assertTrue(np.isnan(merged[np.isnan(depth)]).all())


class ByObject(unittest.TestCase):
    """A person cut from a plate by a soft matte, its estimated depth soft at the silhouette (as a model's
    is), and a CG square at 5 m crossing that silhouette: the person is wholly in front (3 m)."""

    def setUp(self) -> None:
        coverage, _ = disc(radius=10.5)
        rows, cols = np.indices((H, W), dtype=np.float64)
        distance = np.sqrt((cols + 0.5 - 20.3) ** 2 + (rows + 0.5 - 15.7) ** 2)
        # The estimate: 3 m inside, 8 m outside, ramping over 6 pixels round the silhouette.
        self.person_depth = (3.0 + 5.0 * np.clip((distance - 7.5) / 6.0, 0, 1)).astype(np.float32)
        self.person = coverage[..., None] * np.array([0.9, 0.7, 0.6, 1.0], np.float32)
        self.matte = coverage
        self.square = np.zeros((H, W, 4), np.float32)
        self.square[6:26, 24:44] = [0.1, 0.2, 0.9, 1.0]
        self.square_depth = np.where(self.square[..., 3] > 0, 5.0, np.inf).astype(np.float32)
        self.truth = self.person + (1 - coverage[..., None]) * self.square

    def merged(self, person_depth: np.ndarray) -> np.ndarray:
        out, _ = merge_by_depth("m", 0, np.stack([self.person, self.square]),
                                np.stack([np.where(self.matte > 0, person_depth, np.inf), self.square_depth]),
                                ["person", "square"])
        return out

    def test_one_depth_for_the_whole_object_keeps_it_whole_where_it_meets_another(self) -> None:
        from cine_toaster.compositing.reference import object_depth

        meeting = (self.matte > 0) & (self.square[..., 3] > 0)
        per_pixel = float(np.abs(self.merged(self.person_depth) - self.truth)[meeting].mean())
        whole = object_depth("d", self.person_depth, self.matte)
        per_object = float(np.abs(self.merged(whole) - self.truth)[meeting].mean())
        self.assertGreater(per_pixel, 0.05)  # the person dissolves behind the square at its edge
        self.assertLess(per_object, 1e-6)
        self.assertAlmostEqual(float(whole[10, 20]), 3.0)
        self.assertTrue(np.isposinf(whole[self.matte == 0]).all())

    def test_an_object_whose_depth_is_not_known_is_unknown(self) -> None:
        from cine_toaster.compositing.reference import object_depth

        unknown = np.where(self.matte > 0.5, np.nan, self.person_depth).astype(np.float32)
        whole = object_depth("d", unknown, self.matte)
        self.assertTrue(np.isnan(whole[self.matte > 0]).all())


class InTheGraph(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\n")
        depth = {"quantity": "z", "unit": "m", "near_is_small": True}
        coverage, hit = disc()
        signals.record_signal(self.root, signal_id="disc-z", kind="depth", origin="geometric", rate=24, actor=TOOL,
                              frames=[np.where(hit, 3.0, np.inf).astype(np.float32)], camera="cam", depth=depth)
        signals.record_signal(self.root, signal_id="card-z", kind="depth", origin="authored", rate=24, actor=TOOL,
                              frames=[np.full((H, W), 5.0, np.float32)], camera="cam", depth=depth)
        unknown = np.zeros((H, W), bool)
        unknown[:4] = True
        signals.record_signal(self.root, signal_id="guess-z", kind="depth", origin="authored", rate=24, actor=TOOL,
                              frames=[np.full((H, W), 4.0, np.float32)], camera="cam", depth=depth,
                              unknown=[unknown], unknown_means="not measured")
        self.coverage = coverage

    def nodes(self) -> dict:
        return {"dz": {"op": "signal.read", "signal": "disc-z", "kind": "depth", "camera": "cam"},
                "cz": {"op": "signal.read", "signal": "card-z", "kind": "depth", "camera": "cam"},
                "gz": {"op": "signal.read", "signal": "guess-z", "kind": "depth", "camera": "cam"},
                "card": {"op": "generate.solid", "colour": [0, 1, 0, 1]},
                "blue": {"op": "generate.solid", "colour": [0, 0, 1, 1]}}

    def disc(self) -> dict:
        return {"disc": (self.coverage[..., None] * RED)[None]}

    def test_a_merge_gives_its_depth_to_the_next(self) -> None:
        nodes = {**self.nodes(),
                 "first": {"op": "merge.depth", "pictures": ["card", "blue"], "depths": ["cz", "gz"],
                           "unknown": "behind"},
                 "out": {"op": "merge.depth", "pictures": ["disc", "first"], "depths": ["dz", "first.depth"],
                         "unknown": "behind"}}
        graph = {"ports": {"disc": "picture"}, "output": "out", "nodes": nodes}
        self.assertEqual(validate(graph), [])
        out = evaluate(graph, self.disc(), frames=1, size=(W, H), fps=24, root=self.root)[0]
        self.assertTrue(np.allclose(out[10:20, 15:25], [1, 0, 0, 1]))  # the disc, nearest
        self.assertTrue(np.allclose(out[0, 0], [0, 1, 0, 1]))  # the guess unknown there: behind the card
        self.assertTrue(np.allclose(out[H - 1, W - 1], [0, 0, 1, 1]))  # the guess known (4 m) before the card

    def test_an_unknown_depth_reaches_no_other_operation(self) -> None:
        nodes = {**self.nodes(), "m": {"op": "matte.from_signal", "signal": "gz", "low": 0, "high": 10},
                 "out": {"op": "merge.over", "front": "card", "back": "blue", "matte": "m"}}
        with self.assertRaisesRegex(ValidationError, "only merge.depth decides"):
            evaluate({"output": "out", "nodes": nodes}, {}, frames=1, size=(W, H), fps=24, root=self.root)

    def test_an_object_depth_in_the_graph(self) -> None:
        nodes = {**self.nodes(),
                 "matte": {"op": "matte.from_signal", "signal": "alpha"},
                 "alpha": {"op": "signal.channel", "picture": "disc", "channel": "alpha"},
                 "whole": {"op": "signal.object_depth", "signal": "gz", "matte": "matte", "camera": "cam"},
                 "out": {"op": "merge.depth", "pictures": ["disc", "card"], "depths": ["whole", "cz"]}}
        graph = {"ports": {"disc": "picture"}, "output": "out", "nodes": nodes}
        self.assertEqual(validate(graph), [])
        out = evaluate(graph, self.disc(), frames=1, size=(W, H), fps=24, root=self.root)[0]
        # The guess knows the disc's interior (4 m, before the card), not its top rows: the whole disc at 4 m.
        self.assertTrue(np.allclose(out[15, 20], [1, 0, 0, 1]))

    def test_hard_edges_are_still_there_when_asked_for(self) -> None:
        nodes = {**self.nodes(), "out": {"op": "merge.depth", "pictures": ["disc", "card"], "depths": ["dz", "cz"],
                                         "edges": "hard"}}
        graph = {"ports": {"disc": "picture"}, "output": "out", "nodes": nodes}
        hard = evaluate(graph, self.disc(), frames=1, size=(W, H), fps=24, root=self.root)[0]
        nodes["out"]["edges"] = "coverage"
        covered = evaluate(graph, self.disc(), frames=1, size=(W, H), fps=24, root=self.root)[0]
        soft = (self.coverage > 0) & (self.coverage < 1)
        self.assertGreater(float(np.abs(hard - covered)[soft].max()), 0.1)  # the halo, kept as asked


FLAT = {
    "objects": [
        {"name": "wall", "type": "plane", "size": [30, 20], "location": [0, 12, 0], "rotation": [90, 0, 0],
         "colour": [0.55, 0.5, 0.45], "shader": "emission"},
        {"name": "floor", "type": "plane", "size": [30, 30], "location": [0, 6, -1.2], "colour": [0.3, 0.35, 0.3],
         "shader": "emission"},
        {"name": "pillar", "type": "cube", "size": 1.0, "location": [0.3, 6, 0], "colour": [0.2, 0.3, 0.7],
         "shader": "emission"},
        {"name": "ball", "type": "sphere", "radius": 0.5, "location": [-1.2, 8, -0.3], "colour": [0.85, 0.25, 0.1],
         "shader": "emission",
         "keys": [{"frame": 1, "location": [-1.2, 8, -0.3]}, {"frame": 3, "location": [1.0, 8, -0.3]}]}],
    "camera": {"name": "cam", "lens": 35, "sensor_width": 36,
               "keys": [{"frame": 1, "location": [0, 0, 0.2], "rotation": [90, 0, 0]},
                        {"frame": 3, "location": [0, 1.0, 0.2], "rotation": [90, 0, 0]}]},
}


@heavy("renders four scenes with Blender at four times the size")
@unittest.skipUnless(blender_binary(), "Blender is not installed")
@needs("OpenEXR")
class AgainstARenderedTruth(unittest.TestCase):
    """Flat-shaded, so layers composite exactly but for their edges: the whole scene (at 4x, averaged down) is
    the truth; the ball, the pillar and the room are layers, each depth one sample a pixel."""

    K, SIZE = 4, (120, 68)

    @classmethod
    def setUpClass(cls) -> None:
        from cine_toaster import renders

        cls.directory = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.directory.name)
        (root / "project.yaml").write_text("id: t\ntitle: T\n")
        (root / "scenes").mkdir()
        parts = {"whole": None, "ball": ("ball",), "pillar": ("pillar",), "room": ("wall", "floor"),
                 "stage": ("wall", "floor", "pillar")}
        cls.layers = {}
        for name, keep in parts.items():
            recipe = {**FLAT, "objects": [item for item in FLAT["objects"] if keep is None or item["name"] in keep]}
            (root / "scenes" / f"{name}.json").write_text(json.dumps(recipe))
            renders.render_passes(root, render_id=name, camera="cam", first=1, last=3, fps=24, samples=16,
                                  size=(cls.SIZE[0] * cls.K, cls.SIZE[1] * cls.K), recipe=f"scenes/{name}.json",
                                  filter_size=1.0, actor=TOOL)
            reader = renders.RenderReader(root, name)
            k = cls.K
            cls.layers[name] = [(_down(reader.picture(i), k), reader.depth.frame(i)[k // 2::k, k // 2::k],
                                 signals.SignalReader(root, f"{name}-objects").frame(i)[k // 2::k, k // 2::k])
                                for i in range(3)]
        cls.ball_label = int(next(k for k, v in renders.load_render(root, "whole")["objects"].items() if v == "ball"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def error(self, names: list[str], edges: str) -> float:
        errors = []
        for index in range(3):
            truth, _, objects = self.layers["whole"][index]
            pictures = np.stack([self.layers[name][index][0] for name in names])
            depths = np.stack([self.layers[name][index][1] for name in names])
            out, _ = merge_by_depth("m", index, pictures, depths, names, edges=edges)
            ball = objects == self.ball_label
            band = _grown(ball, 2) & _grown(~ball, 2)
            errors.append(float(np.abs(out[..., :3] - truth[..., :3]).mean(-1)[band].mean()))
        return float(np.mean(errors))

    def test_carrying_depth_into_coverage_removes_the_halo(self) -> None:
        opaque_hard, opaque_covered = self.error(["ball", "stage"], "hard"), self.error(["ball", "stage"], "coverage")
        layered_hard, layered_covered = (self.error(["ball", "pillar", "room"], "hard"),
                                         self.error(["ball", "pillar", "room"], "coverage"))
        measured = (opaque_hard, opaque_covered, layered_hard, layered_covered)
        # Over an opaque background the halo goes; the pillar's own edge inside it cannot be mended.
        self.assertLess(opaque_covered, opaque_hard / 1.5, measured)
        # Every occluder its own layer: the merge is near exact.
        self.assertLess(layered_covered, layered_hard / 10, measured)
        self.assertLess(layered_covered, 0.002, measured)


def _models_and_blender() -> str:
    from test_estimates import _models_here

    return _models_here()


@heavy("renders four scenes with Blender at 4x, runs Video Depth Anything on a plate of one")
@unittest.skipIf(_models_and_blender(), _models_and_blender())
@needs("OpenEXR")
class OnAnEstimatedPlate(unittest.TestCase):
    """The done-when film's shape: a plate (the stage rendered flat, standing in for footage) whose depth is
    estimated by Video Depth Anything and aligned to its floor alone (a proxy), a person (the pillar) cut out
    by a soft matte, and a CG ball crossing behind it; the truth is the whole scene rendered at once."""

    K = 4

    @classmethod
    def setUpClass(cls) -> None:
        import subprocess

        from cine_toaster import align, estimates, renders

        cls.directory = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.directory.name)
        (root / "project.yaml").write_text("id: t\ntitle: T\n")
        (root / "scenes").mkdir()
        dolly = {**FLAT, "camera": {**FLAT["camera"], "keys": [
            {"frame": 1, "location": [0, 0, 0.2], "rotation": [90, 0, 0]},
            {"frame": 8, "location": [0, 2.5, 0.2], "rotation": [90, 0, 0]}]},
            "objects": [{**item, "keys": [{"frame": 1, "location": [-3.0, 8, -0.3]},
                                          {"frame": 8, "location": [3.0, 8, -0.3]}]} if item["name"] == "ball" else item
                        for item in FLAT["objects"]]}
        parts = {"whole": None, "ball": ("ball",), "pillar": ("pillar",), "stage": ("wall", "floor", "pillar")}
        cls.renders = {}
        for name, keep in parts.items():
            recipe = {**dolly, "objects": [item for item in dolly["objects"] if keep is None or item["name"] in keep]}
            (root / "scenes" / f"{name}.json").write_text(json.dumps(recipe))
            renders.render_passes(root, render_id=name, camera="cam", first=1, last=8, fps=24, samples=16,
                                  size=(320 * cls.K, 180 * cls.K), recipe=f"scenes/{name}.json", filter_size=1.0,
                                  actor=TOOL)
            cls.renders[name] = renders.RenderReader(root, name)
        k = cls.K
        stage = cls.renders["stage"]
        frames = []
        for index in range(8):
            rgb = np.clip(_down(stage.picture(index), k)[..., :3], 0, 1)
            frames.append((np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * rgb ** (1 / 2.4) - 0.055) * 255 + 0.5)
                          .astype(np.uint8))
        (root / "plates").mkdir()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "320x180",
                        "-r", "24", "-i", "-", "-c:v", "ffv1", str(root / "plates" / "stage.mkv")],
                       input=np.stack(frames).tobytes(), check=True)
        depth = {"quantity": "z", "unit": "m", "near_is_small": True, "empty": "inf"}
        cls.labels = signals.load_record(root, "stage-objects")["labels"]
        signals.record_signal(root, signal_id="plate-geometry", kind="depth", origin="geometric", rate=24,
                              actor=TOOL, camera="cam", depth=depth,
                              frames=[stage.depth.frame(i)[k // 2::k, k // 2::k] for i in range(8)])
        signals.record_signal(root, signal_id="plate-objects", kind="segmentation", origin="geometric", rate=24,
                              actor=TOOL, camera="cam", labels=cls.labels, labels_are="instances",
                              frames=[signals.SignalReader(root, "stage-objects").frame(i)[k // 2::k, k // 2::k]
                                      .astype(np.int32) for i in range(8)])
        estimates.estimate(root, signal_id="plate-vda", model="video-depth-anything-small", media="plates/stage.mkv",
                           actor=TOOL, parameters={"input_size": 252})
        floor = next(int(number) for number, name in cls.labels.items() if name == "floor")
        cls.aligned = align.align_depth(root, signal_id="plate-z", estimate="plate-vda", reference="plate-geometry",
                                        camera="cam", actor=TOOL, region="plate-objects", keep_labels=[floor],
                                        objects="plate-objects")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def test_the_person_cut_out_keeps_its_depth_whole_where_the_ball_passes_behind(self) -> None:
        from cine_toaster.compositing.reference import object_depth

        k, estimate = self.K, signals.SignalReader(self.root, "plate-z")
        whole_names = {int(n): v for n, v in __import__("cine_toaster.renders").renders.load_render(
            self.root, "whole")["objects"].items()}
        ball_id = next(n for n, v in whole_names.items() if v == "ball")
        pillar_id = next(n for n, v in whole_names.items() if v == "pillar")
        errors = {"per pixel": [], "per object": []}
        for index in range(8):
            truth = _down(self.renders["whole"].picture(index), k)
            objects = signals.SignalReader(self.root, "whole-objects").frame(index)[k // 2::k, k // 2::k]
            ball = objects == ball_id
            meeting = _grown(ball, 2) & _grown(~ball, 2) & _grown(objects == pillar_id, 3)
            if not meeting.any():
                continue
            plate = _down(self.renders["stage"].picture(index), k)
            cg = _down(self.renders["ball"].picture(index), k)
            cg_depth = self.renders["ball"].depth.frame(index)[k // 2::k, k // 2::k]
            matte = _down(self.renders["pillar"].picture(index), k)[..., 3]
            z = estimate.frame(index)
            for name, person_depth in (("per pixel", np.where(matte > 0, z, np.inf)),
                                       ("per object", object_depth("d", z, matte))):
                out, _ = merge_by_depth("m", index, np.stack([cg, plate * matte[..., None], plate]),
                                        np.stack([cg_depth, person_depth, z]).astype(np.float32),
                                        ["ball", "person", "plate"], unknown="behind")
                errors[name].append(float(np.abs(out[..., :3] - truth[..., :3]).mean(-1)[meeting].mean()))
        per_pixel, per_object = float(np.mean(errors["per pixel"])), float(np.mean(errors["per object"]))
        self.assertTrue(errors["per pixel"], "the ball never met the person")
        self.assertEqual(self.aligned["occlusions_inverted"], {})
        self.assertLess(per_object, per_pixel / 3, (per_pixel, per_object))


def _down(picture: np.ndarray, k: int) -> np.ndarray:
    h, w = picture.shape[0] // k, picture.shape[1] // k
    return picture.reshape(h, k, w, k, picture.shape[2]).mean(axis=(1, 3))


def _grown(mask: np.ndarray, pixels: int) -> np.ndarray:
    grown = mask.copy()
    for _ in range(pixels):
        step = grown.copy()
        step[1:] |= grown[:-1]
        step[:-1] |= grown[1:]
        step[:, 1:] |= grown[:, :-1]
        step[:, :-1] |= grown[:, 1:]
        grown = step
    return grown


if __name__ == "__main__":
    unittest.main()
