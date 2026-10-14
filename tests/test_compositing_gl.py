"""The GL renderer checked against the reference (ADR 0022 §5): never the reverse."""

from __future__ import annotations

import unittest

import numpy as np

from cine_toaster.compositing import reference
from cine_toaster.shader_render import gl_unavailable_reason

W, H, FPS, FRAMES = 96, 54, 12, 6


def textured(seed: int, alpha: float = 1.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = np.repeat(np.repeat(rng.uniform(0.05, 0.95, (H // 6, W // 6, 3)), 6, 0), 6, 1).astype(np.float32)
    return np.dstack([base * alpha, np.full((H, W), alpha, np.float32)])


GRAPHS = {
    "over with a key": {"ports": {"a": "picture", "b": "picture"},
                        "nodes": {"k": {"op": "matte.key", "picture": "a", "by": "luminance", "low": 0.2, "high": 0.6},
                                  "out": {"op": "merge.over", "front": "a", "back": "b", "matte": "k", "mix": 0.8}},
                        "output": "out"},
    "luma wipe": {"ports": {"from": "picture", "to": "picture", "progress": "curve", "texture": "picture"},
                  "nodes": {"order": {"op": "signal.luma", "picture": "texture"},
                            "shape": {"op": "matte.from_signal", "signal": "order"},
                            "reveal": {"op": "matte.threshold", "matte": "shape", "progress": "progress",
                                       "softness": 0.1},
                            "out": {"op": "merge.over", "front": "to", "back": "from", "matte": "reveal"}},
                  "output": "out"},
    "blends and grade": {"ports": {"a": "picture", "b": "picture"},
                         "nodes": {"s": {"op": "merge.blend", "a": "a", "b": "b", "mode": "screen", "mix": 0.7},
                                   "g": {"op": "colour.grade", "in": "s", "gain": 1.3, "saturation": 0.6},
                                   "out": {"op": "merge.porter_duff", "a": "g", "b": "b", "how": "atop"}},
                         "output": "out"},
    "blur": {"ports": {"a": "picture"}, "nodes": {"out": {"op": "filter.blur", "in": "a", "radius": 3}},
             "output": "out"},
    "flat transform": {"ports": {"a": "picture"},
                       "nodes": {"out": {"op": "warp.transform", "in": "a", "scale": [0.6, 0.6],
                                         "translate": [0.1, -0.05], "rotate": 12}}, "output": "out"},
    "turn in perspective": {"ports": {"a": "picture"},
                            "nodes": {"out": {"op": "warp.transform", "in": "a", "rotate": [0, 35, 0],
                                              "perspective": 40, "scale": [0.8, 0.8]}}, "output": "out"},
}


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class ConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from cine_toaster.compositing.gl import GLRenderer

        cls.gl = GLRenderer()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.gl.release()

    def compare(self, graph: dict, inputs: dict, mean: float, worst: float) -> None:
        options = {"frames": FRAMES, "size": (W, H), "fps": FPS}
        expected = reference.evaluate(graph, dict(inputs), **options)
        drawn = self.gl.evaluate(graph, dict(inputs), **options)
        difference = np.abs(expected - drawn)
        self.assertLess(float(difference.mean()), mean)
        self.assertLess(float(np.quantile(difference, 0.99)), worst)

    def test_each_graph_agrees_with_the_reference(self) -> None:
        inputs = {"a": textured(1), "b": textured(2, 0.8), "from": textured(3), "to": textured(4),
                  "texture": textured(5)}
        for name, graph in GRAPHS.items():
            with self.subTest(graph=name):
                ports = {key: inputs[key] for key in graph.get("ports", {}) if key in inputs}
                warped = name in ("flat transform", "turn in perspective", "blur")
                self.compare(graph, ports, 0.01 if warped else 1e-3, 0.2 if warped else 5e-3)

    def test_the_warp_wipes_agree_with_the_reference(self) -> None:
        from cine_toaster.transitions import list_transitions

        catalog = {item["id"]: item for item in list_transitions()}
        for name in ("warp-ball", "warp-roll", "page-turn"):
            with self.subTest(recipe=name):
                self.compare(catalog[name]["graph"], {"from": textured(6), "to": textured(7)}, 0.02, 0.5)

    def test_an_op_it_does_not_draw_is_refused_by_name(self) -> None:
        from cine_toaster.errors import ValidationError

        with self.assertRaisesRegex(ValidationError, "time.echo"):
            self.gl.evaluate({"ports": {"a": "picture"}, "nodes": {"out": {"op": "time.echo", "in": "a", "count": 2}},
                              "output": "out"}, {"a": textured(1)}, frames=2, size=(W, H), fps=FPS)


if __name__ == "__main__":
    unittest.main()
