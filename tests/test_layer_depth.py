"""C8 step 7 (CT-0081): depth and segmentation in a shot's layers -- declared, compiled into the one graph (no
second compositor), drawn alike by the reference and GL, every refusal of the records kept on the way.

The scene: a plate (a person, a disc at 3 m, before a wall at 8 m), its depth an estimate aligned to metres, the
person's segmentation; a CG square at 5 m crossing her edge. Truth: she covers the square; the square covers
the wall."""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from cine_toaster import signals
from cine_toaster.compositing.gl import gl_unavailable_reason, renderer_for
from cine_toaster.compositing.layers import compile_layers
from cine_toaster.compositing.reference import evaluate
from cine_toaster.compositing.schema import validate
from cine_toaster.errors import ValidationError
from cine_toaster.state import Actor

sys.path.insert(0, str(Path(__file__).parent))
from heavy import heavy, needs  # noqa: E402
from test_depth_edges import FLAT, _down, _grown, disc  # noqa: E402

TOOL = Actor(id="compositor", kind="system")
W, H, FRAMES = 48, 32, 2
CAM = "shot-cam"
DEPTH = {"quantity": "z", "unit": "m", "near_is_small": True}


def plate() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(the plate, its estimated depth -- soft at her edge, as a model's is --, her segmentation, her coverage)."""

    coverage, hit = disc(radius=10.5)
    wall = np.array([0.30, 0.35, 0.45, 1.0], np.float32)
    skin = np.array([0.80, 0.55, 0.45, 1.0], np.float32)
    picture = coverage[..., None] * skin + (1 - coverage[..., None]) * wall
    rows, cols = np.indices((H, W), dtype=np.float64)
    distance = np.sqrt((cols + 0.5 - 20.3) ** 2 + (rows + 0.5 - 15.7) ** 2)
    depth = (3.0 + 5.0 * np.clip((distance - 7.5) / 6.0, 0, 1)).astype(np.float32)
    return picture.astype(np.float32), depth, hit.astype(np.int32), coverage


def square() -> tuple[np.ndarray, np.ndarray]:
    picture = np.zeros((H, W, 4), np.float32)
    picture[6:26, 24:44] = [0.1, 0.2, 0.9, 1.0]
    return picture, np.where(picture[..., 3] > 0, 5.0, np.inf).astype(np.float32)


LAYERS = [
    {"source": "plate.mkv", "depth": {"signal": "plate-z", "camera": CAM, "estimated": True}},
    {"source": "plate.mkv", "cut": {"signal": "people", "labels": [1]},
     "depth": {"signal": "plate-z", "camera": CAM, "estimated": True, "object": True}},
    {"source": "cg.png", "depth": {"signal": "cg-z", "camera": CAM}},
]


class LayersWithDepth(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\n")
        self.picture, self.depth, self.people, self.coverage = plate()
        self.cg, cg_depth = square()
        signals.record_signal(self.root, signal_id="plate-z", kind="depth", origin="estimated", rate=24, actor=TOOL,
                              frames=[self.depth] * FRAMES, camera=CAM, depth=DEPTH)
        signals.record_signal(self.root, signal_id="people", kind="segmentation", origin="estimated", rate=24,
                              actor=TOOL, frames=[self.people] * FRAMES, labels={0: "nothing", 1: "her"},
                              labels_are="instances")
        signals.record_signal(self.root, signal_id="cg-z", kind="depth", origin="geometric", rate=24, actor=TOOL,
                              frames=[cg_depth] * FRAMES, camera=CAM, depth=DEPTH)

    def graph(self, layers: list) -> tuple[dict, dict]:
        """The layers compiled, their sources given as pictures (each source node a port, read `of` it)."""

        graph, problems = compile_layers(layers)
        self.assertEqual(problems, [])
        sources = {"plate.mkv": self.picture, "cg.png": self.cg}
        inputs, ports = {}, {}
        for name, node in list(graph["nodes"].items()):
            if node["op"] == "generate.source":
                del graph["nodes"][name]
                ports[name] = "picture"
                inputs[name] = np.repeat(sources[node["file"]][None], FRAMES, 0)
        graph["ports"] = ports
        self.assertEqual(validate(graph), [])
        return graph, inputs

    def draw(self, layers: list, renderer=None) -> np.ndarray:
        graph, inputs = self.graph(layers)
        if renderer is not None:
            return renderer.evaluate(graph, inputs, frames=FRAMES, size=(W, H), fps=24, root=self.root)
        return evaluate(graph, inputs, frames=FRAMES, size=(W, H), fps=24, root=self.root)

    def test_the_layers_compile_into_the_one_graph(self) -> None:
        graph, _ = compile_layers(LAYERS)
        ops = [node["op"] for node in graph["nodes"].values()]
        self.assertEqual(ops.count("merge.depth"), 1)  # one merge, no second compositor
        merge = next(node for node in graph["nodes"].values() if node["op"] == "merge.depth")
        self.assertEqual(len(merge["pictures"]), 3)
        self.assertIn("signal.object_depth", ops)
        self.assertIn("matte.label", ops)
        reads = [node for node in graph["nodes"].values() if node["op"] == "signal.read"]
        self.assertTrue(all(node.get("of") for node in reads))  # read where their source shows

    def test_she_covers_the_square_and_the_square_covers_the_wall(self) -> None:
        out = self.draw(LAYERS)[0]
        her = self.people == 1  # her cut: a segmentation is hard, one label a pixel
        square_there = self.cg[..., 3] > 0
        np.testing.assert_allclose(out[her & square_there], self.picture[her & square_there], atol=1e-6)
        wall = (self.coverage == 0) & square_there
        np.testing.assert_allclose(out[wall], self.cg[wall], atol=1e-6)

    def test_per_pixel_her_edge_dissolves_one_depth_keeps_her_whole(self) -> None:
        per_pixel = [dict(layer) for layer in LAYERS]
        per_pixel[1] = {**LAYERS[1], "depth": {k: v for k, v in LAYERS[1]["depth"].items() if k != "object"}}
        her = (self.people == 1) & (self.cg[..., 3] > 0)
        lost = lambda out: int((np.abs(out[0] - self.picture).max(-1)[her] > 1e-4).sum())  # noqa: E731
        self.assertEqual(lost(self.draw(LAYERS)), 0)  # one depth for her: none of her pixels behind the square
        self.assertGreater(lost(self.draw(per_pixel)), 10)  # per pixel her soft-depth edge falls behind it

    @unittest.skipIf(gl_unavailable_reason(), "no GL context here")
    def test_gl_draws_the_layers_alike(self) -> None:
        graph, _ = self.graph(LAYERS)
        renderer = renderer_for(graph)
        self.assertIsNotNone(renderer)
        np.testing.assert_allclose(self.draw(LAYERS, renderer), self.draw(LAYERS), atol=1e-5)

    def test_a_title_without_depth_keeps_its_place_over_them(self) -> None:
        title = np.zeros((H, W, 4), np.float32)
        title[2:5, 2:46] = [1.0, 1.0, 1.0, 1.0]
        layers = LAYERS + [{"source": "title.png"}]
        graph, problems = compile_layers(layers)
        self.assertEqual(problems, [])
        self.assertEqual(graph["nodes"][graph["output"]]["op"], "merge.over")
        self.assertEqual(graph["nodes"][graph["output"]]["front"], "L4")

    def test_the_records_refusals_hold_through_the_layers(self) -> None:
        not_said = [dict(layer) for layer in LAYERS]
        not_said[0] = {**LAYERS[0], "depth": {"signal": "plate-z", "camera": CAM}}
        with self.assertRaisesRegex(ValidationError, "estimated: true"):
            self.draw(not_said)
        # An occlusion its calibration found inverted: refused unless accepted.
        signals.record_signal(self.root, signal_id="raw-z", kind="depth_relative", origin="estimated", rate=24,
                              actor=TOOL, frames=[1.0 / self.depth] * FRAMES,
                              depth={"quantity": "inverse_z", "near_is_small": False})
        signals.record_signal(self.root, signal_id="flagged-z", kind="depth", origin="estimated", rate=24,
                              actor=TOOL, frames=[self.depth] * FRAMES, camera=CAM, depth=DEPTH,
                              derived_from="raw-z", transformation={"name": "align_depth",
                                                                    "occlusions_inverted": {"her/wall": [0]}})
        flagged = [{**LAYERS[0], "depth": {"signal": "flagged-z", "camera": CAM, "estimated": True}}] + LAYERS[1:]
        with self.assertRaisesRegex(ValidationError, "occlusions inverted"):
            self.draw(flagged)
        flagged[0]["depth"]["inversions"] = "accept"
        self.draw(flagged)
        # Unknown where a picture shows: refused unless the layers say what it means.
        lost = self.depth.copy()
        lost[:5] = np.nan
        signals.record_signal(self.root, signal_id="lost-z", kind="depth", origin="estimated", rate=24, actor=TOOL,
                              frames=[np.where(np.isnan(lost), np.inf, lost)] * FRAMES, camera=CAM, depth=DEPTH,
                              unknown=[np.isnan(lost)] * FRAMES)
        unknown = [{**LAYERS[0], "depth": {"signal": "lost-z", "camera": CAM, "estimated": True}}] + LAYERS[1:]
        with self.assertRaisesRegex(ValidationError, "unknown"):
            self.draw(unknown)
        unknown[0]["depth"]["unknown"] = "behind"
        self.draw(unknown)
        # A stale record.
        signals.record_signal(self.root, signal_id="raw-z", kind="depth_relative", origin="estimated", rate=24,
                              actor=TOOL, frames=[2.0 / self.depth] * FRAMES,
                              depth={"quantity": "inverse_z", "near_is_small": False})
        with self.assertRaisesRegex(ValidationError, "stale"):
            self.draw(flagged)

    def test_what_cannot_be_written_is_said(self) -> None:
        cases = {
            "a depth with no camera": [{"source": "a.png", "depth": {"signal": "plate-z"}}],
            "a depth and a move": [{"source": "a.png", "place": {"scale": 0.5},
                                    "depth": {"signal": "plate-z", "camera": CAM}}],
            "a render's depth without a render": [{"source": "a.png", "depth": {"render": True, "camera": CAM}}],
            "a source and a render": [{"source": "a.png", "render": "lamp"}],
            "a cut without labels": [{"source": "a.png", "cut": {"signal": "people"}}],
            "two ways with the unknown": [
                {"source": "a.png", "depth": {"signal": "plate-z", "camera": CAM, "unknown": "behind"}},
                {"source": "b.png", "depth": {"signal": "cg-z", "camera": CAM, "unknown": "front"}}],
            "a depth blending": [{"source": "a.png"}, {"source": "b.png", "mode": "screen",
                                                       "depth": {"signal": "cg-z", "camera": CAM}}],
        }
        for name, layers in cases.items():
            with self.subTest(case=name):
                self.assertTrue(compile_layers(layers)[1], name)
        graph, problems = compile_layers([{"source": "a.png", "depth": {"signal": "plate-z", "camera": CAM}},
                                          {"source": "b.png", "depth": {"signal": "cg-z", "camera": "other"}}])
        self.assertEqual(problems, [])
        self.assertTrue(any("different cameras" in message for _, message in validate(graph)))

    def test_in_a_scene_as_any_shot_and_refused_alike(self) -> None:
        # Layers written in a scene -- as a person or an agent would, through the scene's file -- become its
        # composite; drawn, the same refusals.
        from PIL import Image

        from cine_toaster.project import load_production

        (self.root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
        (self.root / "scenes" / "010").mkdir(parents=True)
        (self.root / "plates").mkdir()
        Image.fromarray((self.picture[..., :3] * 255).astype(np.uint8)).save(self.root / "plates" / "plate.png")
        (self.root / "scenes" / "010" / "scene.yaml").write_text(textwrap.dedent(f"""\
            scene: S1
            shots:
              - n: 1
                duration: 1
                label: Her, before a square.
                layers:
                  - source: plates/plate.png
                    depth: {{signal: plate-z, camera: {CAM}}}
            """))
        shot = load_production(self.root)["scenes"][0]["shots"][0]
        graph = shot["composite"]
        self.assertEqual(validate(graph), [])
        with self.assertRaisesRegex(ValidationError, "estimated: true"):
            evaluate(graph, {}, frames=1, size=(W, H), fps=24, root=self.root)


def _here() -> str:
    from test_estimates import _models_here

    return _models_here()


@heavy("renders with Blender, runs Video Depth Anything and SAM 2")
@unittest.skipIf(_here(), _here())
@needs("OpenEXR")
class SourcesMeetInLayers(unittest.TestCase):
    """Blender and models in one composition, declared as layers: a plate (the stage rendered flat, standing for
    footage) with Video Depth Anything's depth aligned to its floor, the pillar cut out by SAM 2's segmentation
    as "the person", a CG ball from its own render -- its camera stated to be the plate's --, against the whole
    scene rendered at once."""

    K = 4

    @classmethod
    def setUpClass(cls) -> None:
        import json
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
        k = cls.K
        for name, keep, scale in (("whole", None, k), ("stage", ("wall", "floor", "pillar"), k), ("ball", ("ball",), 1)):
            recipe = {**dolly, "objects": [item for item in dolly["objects"] if keep is None or item["name"] in keep]}
            (root / "scenes" / f"{name}.json").write_text(json.dumps(recipe))
            renders.render_passes(root, render_id=name, camera="cam", first=1, last=8, fps=24, samples=16,
                                  size=(320 * scale, 180 * scale), recipe=f"scenes/{name}.json", filter_size=1.0,
                                  actor=TOOL, camera_id="shot-cam" if name == "ball" else None)
        stage = renders.RenderReader(root, "stage")
        frames = []
        for index in range(8):
            rgb = np.clip(_down(stage.picture(index), k)[..., :3], 0, 1)
            frames.append((np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * rgb ** (1 / 2.4) - 0.055) * 255 + 0.5)
                          .astype(np.uint8))
        (root / "plates").mkdir()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "320x180",
                        "-r", "24", "-i", "-", "-c:v", "ffv1", str(root / "plates" / "stage.mkv")],
                       input=np.stack(frames).tobytes(), check=True)
        # What a production would have: a proxy of the floor (geometry of it alone) and the plate's camera.
        labels = signals.load_record(root, "stage-objects")["labels"]
        floor = next(int(n) for n, v in labels.items() if v == "floor")
        objects = [signals.SignalReader(root, "stage-objects").frame(i)[k // 2::k, k // 2::k] for i in range(8)]
        signals.record_signal(root, signal_id="floor-proxy", kind="depth", origin="geometric", rate=24, actor=TOOL,
                              camera="shot-cam", depth={**DEPTH, "empty": "inf"},
                              frames=[np.where(objects[i] == floor, stage.depth.frame(i)[k // 2::k, k // 2::k],
                                               np.inf).astype(np.float32) for i in range(8)])
        for model, name in (("video-depth-anything-small", "vda"),):
            estimates.estimate(root, signal_id=f"plate-{name}", model=model, media="plates/stage.mkv", actor=TOOL,
                               parameters={"input_size": 252} if name == "vda" else None)
            align.align_depth(root, signal_id=f"plate-{name}-z", estimate=f"plate-{name}", reference="floor-proxy",
                              camera="shot-cam", actor=TOOL, objects=None)
        estimates.estimate(root, signal_id="plate-people", model="sam2.1-hiera-tiny", media="plates/stage.mkv",
                           actor=TOOL, objects=[{"name": "pillar", "points": [[176, 100]]}])
        cls.renders = {name: renders.RenderReader(root, name) for name in ("whole", "ball")}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def layers(self, depth: str, *, whole: bool = True, accept: bool = False) -> list:
        said = {"camera": "shot-cam", "estimated": True, **({"inversions": "accept"} if accept else {})}
        return [{"source": "plates/stage.mkv", "depth": {"signal": depth, **said}},
                {"source": "plates/stage.mkv", "cut": {"signal": "plate-people", "labels": [1]},
                 "depth": {"signal": depth, **said, **({"object": True} if whole else {})}},
                {"render": "ball", "depth": {"render": True, "camera": "shot-cam"}}]

    def draw(self, layers: list, renderer=None) -> np.ndarray:
        graph, problems = compile_layers(layers)
        self.assertEqual(problems, [])
        self.assertEqual(validate(graph), [])
        if renderer is not None:
            return renderer.evaluate(graph, {}, frames=8, size=(320, 180), fps=24, root=self.root)
        return evaluate(graph, {}, frames=8, size=(320, 180), fps=24, root=self.root)

    def contact_error(self, out: np.ndarray) -> float:
        k, names = self.K, self.renders["whole"].manifest["objects"]
        ball = next(int(n) for n, v in names.items() if v == "ball")
        pillar = next(int(n) for n, v in names.items() if v == "pillar")
        errors = []
        for index in range(8):
            objects = signals.SignalReader(self.root, "whole-objects").frame(index)[k // 2::k, k // 2::k]
            meeting = _grown(objects == ball, 2) & _grown(objects == pillar, 3)
            if meeting.any():
                truth = _down(self.renders["whole"].picture(index), k)
                errors.append(float(np.abs(out[index][..., :3] - truth[..., :3]).mean(-1)[meeting].mean()))
        self.assertTrue(errors, "the ball never met the pillar")
        return float(np.mean(errors))

    def test_blender_and_the_models_meet_in_one_composition(self) -> None:
        whole = self.draw(self.layers("plate-vda-z"))
        per_pixel = self.draw(self.layers("plate-vda-z", whole=False))
        measured = (self.contact_error(whole), self.contact_error(per_pixel))
        self.assertLess(measured[0], measured[1] / 2, measured)
        # Every source of it is a record with its history: the render's camera stated, the models pinned.
        self.assertEqual(self.renders["ball"].camera, "shot-cam")
        self.assertIn("stated_by", self.renders["ball"].manifest["camera"])
        for signal_id, maker in (("plate-people", "sam2.1-hiera-tiny"), ("plate-vda", "video-depth-anything-small")):
            self.assertEqual(signals.load_record(self.root, signal_id)["provenance"][-1]["maker"]["name"], maker)
        self.assertEqual(signals.status(self.root, "plate-vda-z")["transformations"], ["align_depth"])

    @unittest.skipIf(gl_unavailable_reason(), "no GL context here")
    def test_gl_draws_it_alike(self) -> None:
        layers = self.layers("plate-vda-z")
        graph, _ = compile_layers(layers)
        np.testing.assert_allclose(self.draw(layers, renderer_for(graph)), self.draw(layers), atol=1e-4)


if __name__ == "__main__":
    unittest.main()
