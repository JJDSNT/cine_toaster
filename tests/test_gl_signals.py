"""C8 step 6 (CT-0081): the signal ops on GL, checked against the reference -- never the reverse.

The same graph, drawn by both: partial alpha at edges, the three states of a depth (known, nothing there,
unknown), several layers with ties, chained merges, an object's depth, labels; the same refusals, word for
word; and a graph GL cannot draw whole goes to the reference, said so."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cine_toaster import signals
from cine_toaster.compositing import reference
from cine_toaster.compositing.gl import gl_unavailable_reason, renderer_for
from cine_toaster.errors import ValidationError
from cine_toaster.state import Actor
from cine_toaster.titles import blender_binary

sys.path.insert(0, str(Path(__file__).parent))
from heavy import heavy  # noqa: E402
from test_depth_edges import disc  # noqa: E402

TOOL = Actor(id="compositor", kind="system")
W, H, FRAMES = 48, 32, 3
DEPTH = {"quantity": "z", "unit": "m", "near_is_small": True}


def layer(seed: int, alpha: np.ndarray) -> np.ndarray:
    rng = np.random.default_rng(seed)
    colour = rng.uniform(0.1, 0.9, 3).astype(np.float32)
    return np.dstack([alpha[..., None] * colour, alpha]).astype(np.float32)


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class SignalConformance(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\n")

    def record(self, signal_id: str, frames: list[np.ndarray], **more) -> None:
        unknown = [np.isnan(frame) for frame in frames] if any(np.isnan(f).any() for f in frames) else None
        signals.record_signal(self.root, signal_id=signal_id, kind=more.pop("kind", "depth"),
                              origin=more.pop("origin", "authored"), rate=24, actor=TOOL,
                              frames=[np.where(np.isnan(f), np.inf, f).astype(np.float32) for f in frames]
                              if unknown else frames, camera="cam", unknown=unknown,
                              **({"depth": DEPTH} if "labels" not in more else {}), **more)

    def both(self, graph: dict, inputs: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
        inputs = inputs or {}
        renderer = renderer_for(graph)
        self.assertIsNotNone(renderer, "GL should draw this graph whole")
        made = reference.evaluate(graph, inputs, frames=FRAMES, size=(W, H), fps=24, root=self.root)
        drawn = renderer.evaluate(graph, inputs, frames=FRAMES, size=(W, H), fps=24, root=self.root)
        return made, drawn

    def same(self, graph: dict, inputs: dict | None = None, tolerance: float = 1e-6) -> np.ndarray:
        made, drawn = self.both(graph, inputs)
        self.assertFalse(np.isnan(drawn).any())
        np.testing.assert_allclose(drawn, made, atol=tolerance)
        return drawn

    def same_refusal(self, graph: dict, inputs: dict | None = None) -> str:
        inputs = inputs or {}
        with self.assertRaises(ValidationError) as by_reference:
            reference.evaluate(graph, inputs, frames=FRAMES, size=(W, H), fps=24, root=self.root)
        with self.assertRaises(ValidationError) as by_gl:
            renderer_for(graph).evaluate(graph, inputs, frames=FRAMES, size=(W, H), fps=24, root=self.root)
        self.assertEqual(str(by_gl.exception), str(by_reference.exception))
        return str(by_reference.exception)

    def disc_and_card(self) -> dict:
        coverage, hit = disc()
        self.record("disc-z", [np.where(hit, 3.0, np.inf).astype(np.float32)] * FRAMES)
        self.record("card-z", [np.full((H, W), 5.0, np.float32)] * FRAMES)
        self.inputs = {"disc": np.repeat(layer(1, coverage)[None], FRAMES, 0),
                       "card": np.repeat(layer(2, np.ones((H, W), np.float32))[None], FRAMES, 0)}
        return {"dz": {"op": "signal.read", "signal": "disc-z", "kind": "depth", "camera": "cam"},
                "cz": {"op": "signal.read", "signal": "card-z", "kind": "depth", "camera": "cam"}}

    def test_partial_alpha_at_an_edge_with_coverage_and_without(self) -> None:
        nodes = self.disc_and_card()
        for edges in ("coverage", "hard"):
            graph = {"ports": {"disc": "picture", "card": "picture"}, "output": "out", "nodes": {
                **nodes, "out": {"op": "merge.depth", "pictures": ["disc", "card"], "depths": ["dz", "cz"],
                                 "edges": edges, "reach": 2}}}
            self.same(graph, self.inputs)

    def test_three_states_through_a_chain_of_merges(self) -> None:
        nodes = self.disc_and_card()
        guess = np.full((H, W), 4.0, np.float32)
        guess[:8] = np.nan  # unknown at the top
        guess[:, :6] = np.inf  # nothing there at the left
        self.record("guess-z", [guess] * FRAMES)
        half = np.zeros((H, W), np.float32)
        half[:, W // 3:] = 1.0
        self.inputs["guess"] = np.repeat(layer(3, half)[None], FRAMES, 0)
        nodes["gz"] = {"op": "signal.read", "signal": "guess-z", "kind": "depth", "camera": "cam"}
        for policy in ("behind", "front"):
            graph = {"ports": {"disc": "picture", "card": "picture", "guess": "picture"}, "output": "out",
                     "nodes": {**nodes,
                               "first": {"op": "merge.depth", "pictures": ["guess", "card"], "depths": ["gz", "cz"],
                                         "unknown": policy},
                               "out": {"op": "merge.depth", "pictures": ["disc", "first"],
                                       "depths": ["dz", "first.depth"], "unknown": policy}}}
            self.same(graph, self.inputs)
        # Unknown where a picture shows, no policy said: the same refusal, word for word.
        graph["nodes"]["first"].pop("unknown")
        self.assertIn("unknown", self.same_refusal(graph, self.inputs))
        # An unknown depth into anything but a merge: the same refusal too.
        graph = {"ports": {"card": "picture"}, "output": "out", "nodes": {
            **nodes, "m": {"op": "matte.from_signal", "signal": "gz", "low": 0, "high": 10},
            "out": {"op": "merge.over", "front": "card", "back": "card", "matte": "m"}}}
        self.assertIn("only merge.depth decides", self.same_refusal(graph, self.inputs))

    def test_a_merged_depth_known_and_nothing_there_reaches_a_matte_alike(self) -> None:
        nodes = self.disc_and_card()
        empty = np.zeros((H, W), np.float32)
        graph = {"ports": {"disc": "picture", "none": "picture"}, "output": "out", "nodes": {
            **nodes, "first": {"op": "merge.depth", "pictures": ["disc", "none"], "depths": ["dz", "cz"]},
            "m": {"op": "matte.from_signal", "signal": "first.depth", "low": 0, "high": 10},
            "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
            "black": {"op": "generate.solid", "colour": [0, 0, 0, 1]},
            "out": {"op": "merge.over", "front": "white", "back": "black", "matte": "m"}}}
        out = self.same(graph, {**self.inputs, "none": np.repeat(layer(4, empty)[None], FRAMES, 0)}, tolerance=1e-5)
        self.assertTrue(np.allclose(out[0][0, 0], [1, 1, 1, 1]))  # nothing there: +inf, matte 1, not NaN

    def test_many_layers_with_ties_and_far_is_small(self) -> None:
        rng = np.random.default_rng(7)
        nodes, inputs, pictures, depths = {}, {}, [], []
        for index in range(5):
            alpha = np.clip(rng.uniform(-0.5, 1.5, (H, W)), 0, 1).astype(np.float32)
            depth = np.round(rng.uniform(1, 4, (H, W)), 0).astype(np.float32)  # many ties
            depth[rng.uniform(size=(H, W)) < 0.1] = np.inf
            self.record(f"z{index}", [depth] * FRAMES)
            inputs[f"p{index}"] = np.repeat(layer(10 + index, alpha)[None], FRAMES, 0)
            nodes[f"z{index}"] = {"op": "signal.read", "signal": f"z{index}", "kind": "depth", "camera": "cam"}
            pictures.append(f"p{index}")
            depths.append(f"z{index}")
        for near_is_small in (True, False):
            graph = {"ports": {name: "picture" for name in pictures}, "output": "out", "nodes": {
                **nodes, "out": {"op": "merge.depth", "pictures": pictures, "depths": depths,
                                 "near_is_small": near_is_small}}}
            self.same(graph, inputs)

    def test_an_objects_depth(self) -> None:
        nodes = self.disc_and_card()
        coverage, _ = disc()
        soft = np.full((H, W), 8.0, np.float32)
        soft[coverage > 0] = 3.0 + 4.0 * (1 - coverage[coverage > 0])  # soft at the edge, as an estimate is
        self.record("soft-z", [soft] * FRAMES)
        unknown = np.where(coverage > 0, np.nan, 8.0).astype(np.float32)
        self.record("lost-z", [unknown] * FRAMES)
        nodes.update({"sz": {"op": "signal.read", "signal": "soft-z", "kind": "depth", "camera": "cam"},
                      "alpha": {"op": "signal.channel", "picture": "disc", "channel": "alpha"},
                      "matte": {"op": "matte.from_signal", "signal": "alpha"},
                      "whole": {"op": "signal.object_depth", "signal": "sz", "matte": "matte", "camera": "cam"}})
        graph = {"ports": {"disc": "picture", "card": "picture"}, "output": "out", "nodes": {
            **nodes, "out": {"op": "merge.depth", "pictures": ["disc", "card"], "depths": ["whole", "cz"]}}}
        self.same(graph, self.inputs)
        # An object whose depth is not known: unknown in both, refused alike unless a policy is said.
        graph["nodes"]["lz"] = {"op": "signal.read", "signal": "lost-z", "kind": "depth", "camera": "cam"}
        graph["nodes"]["whole"]["signal"] = "lz"
        self.same_refusal(graph, self.inputs)
        graph["nodes"]["out"]["unknown"] = "behind"
        self.same(graph, self.inputs)

    def test_labels(self) -> None:
        labels = (np.indices((H, W)).sum(axis=0) % 5).astype(np.int32)
        self.record("people", [labels] * FRAMES, kind="segmentation", origin="authored",
                    labels={i: f"l{i}" for i in range(5)}, labels_are="instances")
        graph = {"ports": {"a": "picture"}, "output": "out", "nodes": {
            "s": {"op": "signal.read", "signal": "people", "kind": "segmentation"},
            "m": {"op": "matte.label", "signal": "s", "labels": [1, 3]},
            "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
            "out": {"op": "merge.over", "front": "white", "back": "a", "matte": "m"}}}
        self.same(graph, {"a": np.repeat(layer(5, np.ones((H, W), np.float32))[None], FRAMES, 0)})

    def test_what_gl_cannot_draw_whole_goes_to_the_reference(self) -> None:
        self.disc_and_card()
        signals.record_signal(self.root, signal_id="card-rel", kind="depth_relative", origin="estimated", rate=24,
                              actor=TOOL, frames=[np.full((H, W), 0.5, np.float32)] * FRAMES,
                              depth={"quantity": "inverse_z", "near_is_small": False})
        aligned = {"ports": {"card": "picture"}, "output": "out", "nodes": {
            "rel": {"op": "signal.read", "signal": "card-rel", "kind": "depth_relative"},
            "z": {"op": "signal.align_depth", "signal": "rel", "method": "manual", "scale": 1, "shift": 0},
            "m": {"op": "matte.from_signal", "signal": "z", "low": 0, "high": 10},
            "out": {"op": "merge.over", "front": "card", "back": "card", "matte": "m"}}}
        self.assertIsNone(renderer_for(aligned))
        surface = {"ports": {"card": "picture"}, "output": "out", "nodes": {
            "s": {"op": "warp.surface", "in": "card", "shape": "sphere", "camera": "cam"},
            "out": {"op": "merge.depth", "pictures": ["s", "card"], "depths": ["s.depth", "cz"]},
            "cz": {"op": "signal.read", "signal": "card-z", "kind": "depth", "camera": "cam"}}}
        self.assertIsNone(renderer_for(surface))  # a surface's depth is the reference's alone yet
        many = {"ports": {f"p{i}": "picture" for i in range(9)}, "output": "out", "nodes": {
            "cz": {"op": "signal.read", "signal": "card-z", "kind": "depth", "camera": "cam"},
            "out": {"op": "merge.depth", "pictures": [f"p{i}" for i in range(9)], "depths": ["cz"] * 9}}}
        self.assertIsNone(renderer_for(many))  # more layers than GL's texture units hold
        # Which renderer drew is part of the result's identity, never silent.
        _, identity, _ = reference.render(aligned, self.inputs, frames=1, size=(W, H), fps=24, root=self.root,
                                          cache=Path(self.root / "cache"), renderer=renderer_for(aligned))
        self.assertTrue(identity)

    def test_states_survive_the_way_to_the_gpu_and_back(self) -> None:
        renderer = renderer_for({"nodes": {}})
        depth = np.array([[1.5, np.inf], [np.nan, 0.25]], np.float32)
        with renderer.context:
            back = renderer.download_depth(renderer.upload_depth(depth))
        np.testing.assert_array_equal(np.isnan(back), np.isnan(depth))
        np.testing.assert_array_equal(np.isposinf(back), np.isposinf(depth))
        np.testing.assert_array_equal(back[np.isfinite(depth)], depth[np.isfinite(depth)])


@heavy("renders a scene with Blender")
@unittest.skipIf(gl_unavailable_reason() or not blender_binary(), "needs GL and Blender")
class RenderConformance(unittest.TestCase):
    def test_a_render_its_depth_and_its_objects_drawn_alike(self) -> None:
        import json

        from cine_toaster import renders
        from test_renders import RECIPE, production

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            production(root)
            renders.render_passes(root, render_id="room", camera="cam", first=1, last=3, size=(W * 2, H * 2),
                                  fps=24, recipe="scenes/room.json", samples=4, actor=TOOL)
            signals.record_signal(root, signal_id="card-z", kind="depth", origin="authored", rate=24, actor=TOOL,
                                  frames=[np.full((H * 2, W * 2), 7.0, np.float32)] * 3, camera="room/cam",
                                  depth=DEPTH)
            graph = {"output": "out", "nodes": {
                "r": {"op": "generate.render", "render": "room", "camera": "room/cam"},
                "o": {"op": "signal.read", "signal": "room-objects", "kind": "segmentation"},
                "ball": {"op": "matte.label", "signal": "o", "labels": [1]},
                "card": {"op": "generate.solid", "colour": [0, 1, 0, 1]},
                "cz": {"op": "signal.read", "signal": "card-z", "kind": "depth", "camera": "room/cam"},
                "merged": {"op": "merge.depth", "pictures": ["r", "card"], "depths": ["r.depth", "cz"]},
                "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
                "out": {"op": "merge.over", "front": "white", "back": "merged", "matte": "ball", "mix": 0.5}}}
            for size in ((W * 2, H * 2), (W, H)):  # its own size, and resized to the frame
                made = reference.evaluate(graph, {}, frames=3, size=size, fps=24, root=root)
                drawn = renderer_for(graph).evaluate(graph, {}, frames=3, size=size, fps=24, root=root)
                np.testing.assert_allclose(drawn, made, atol=1e-5)
            del json


if __name__ == "__main__":
    unittest.main()
