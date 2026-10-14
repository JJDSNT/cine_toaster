"""The NumPy reference (ADR 0022 §5, SPEC-0012 §7): float, linear light, premultiplied alpha."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml

from cine_toaster.compositing.reference import IMPLEMENTED, decode_srgb, encode_srgb, evaluate, keys_curve, read
from cine_toaster.compositing.schema import OPS
from cine_toaster.errors import ValidationError

EXAMPLES = Path(__file__).parents[1] / "ai-context" / "specs" / "SPEC-0012-examples"
HAS_FFMPEG = bool(shutil.which("ffmpeg"))
SIZE, FPS, FRAMES = (64, 36), 24, 24


def solid(r: float, g: float, b: float, a: float = 1.0) -> np.ndarray:
    """A picture already in the working space, premultiplied."""

    return np.broadcast_to(np.asarray([r * a, g * a, b * a, a], dtype=np.float32), (SIZE[1], SIZE[0], 4)).copy()


def run(graph: dict, **inputs) -> np.ndarray:
    return evaluate(graph, inputs, frames=FRAMES, size=SIZE, fps=FPS)


class ColourTests(unittest.TestCase):
    def test_srgb_round_trips_and_half_light_is_not_half_code(self) -> None:
        values = np.linspace(0, 1, 101, dtype=np.float32)
        self.assertLess(np.abs(encode_srgb(decode_srgb(values)) - values).max(), 1e-5)
        self.assertAlmostEqual(float(encode_srgb(np.float32(0.5))), 0.7354, places=3)

    def test_a_dissolve_mixes_light_not_code_values(self) -> None:
        graph = {"ports": {"a": "picture", "b": "picture", "progress": "curve"},
                 "nodes": {"out": {"op": "merge.mix", "a": "a", "b": "b", "by": "progress"}}, "output": "out"}
        out = run(graph, a=solid(1, 0, 0), b=solid(0, 1, 0), progress=lambda seconds: 0.5)
        self.assertTrue(np.allclose(out[0, 0, 0], [0.5, 0.5, 0, 1]))
        # In the display encoding that is 0.735 of each, not the 0.5 a mix of code values would give.
        self.assertAlmostEqual(float(encode_srgb(out[0, 0, 0, 0])), 0.7354, places=3)

    def test_a_straight_alpha_picture_is_premultiplied_once_and_lands_over_correctly(self) -> None:
        graph = {"ports": {"front": "picture", "back": "picture"},
                 "nodes": {"out": {"op": "merge.over", "front": "front", "back": "back"}}, "output": "out"}
        out = run(graph, front=solid(1, 0, 0, 0.5), back=solid(0, 0, 1))
        self.assertTrue(np.allclose(out[0, 0, 0], [0.5, 0, 0.5, 1]))


class GraphTests(unittest.TestCase):
    def test_the_luma_wipe_example_reveals_the_centre_first(self) -> None:
        graph = yaml.safe_load((EXAMPLES / "luma-wipe.yaml").read_text())
        ys, xs = np.mgrid[0:SIZE[1], 0:SIZE[0]].astype(np.float32)
        radial = np.hypot((xs + 0.5) / SIZE[0] - 0.5, (ys + 0.5) / SIZE[1] - 0.5) / np.hypot(0.5, 0.5)
        # The texture is an encoded picture whose code values are the order: decode it into the working space.
        texture = np.dstack([decode_srgb(radial)] * 3 + [np.ones_like(radial)])
        out = run(graph, **{"from": solid(1, 0, 0), "to": solid(0, 0, 1), "texture": texture})
        middle = out[FRAMES // 2]
        self.assertGreater(middle[18, 32, 2], 0.99)  # centre: already the incoming picture
        self.assertGreater(middle[0, 0, 0], 0.99)    # corner: still the outgoing one
        self.assertGreater(out[0, 18, 32, 0], 0.99)  # the first frame is the outgoing picture...
        self.assertGreater(out[-1, 0, 0, 2], 0.99)   # ...the last the incoming one

    def test_a_shape_has_coverage_at_its_edge_and_follows_a_curve(self) -> None:
        graph = {"ports": {"a": "picture", "b": "picture"},
                 "nodes": {"grow": {"op": "curve.keys", "keys": [[0, 0.2], [1, 1.0]]},
                           "box": {"op": "matte.shape", "shape": "rectangle", "points": [[0.25, 0.25], [0.75, 0.75]],
                                   "size": {"curve": "grow"}},
                           "out": {"op": "merge.over", "front": "b", "back": "a", "matte": "box"}}, "output": "out"}
        out = run(graph, a=solid(0, 0, 0), b=solid(1, 1, 1))
        first, last = out[0, ..., 0], out[-1, ..., 0]
        self.assertLess(first.sum(), last.sum())  # the box grows
        edges = last[(last > 0.02) & (last < 0.98)]
        self.assertGreater(edges.size, 0)  # coverage, not a staircase

    def test_a_transform_moves_the_picture_and_leaves_transparency_behind(self) -> None:
        graph = {"ports": {"a": "picture"},
                 "nodes": {"out": {"op": "warp.transform", "in": "a", "translate": [0.5, 0.0]}}, "output": "out"}
        out = run(graph, a=solid(1, 1, 1))
        self.assertLess(out[0, 18, 10, 3], 0.01)   # the left half is now empty
        self.assertGreater(out[0, 18, 50, 3], 0.99)

    def test_curves_hold_outside_their_keys_and_ease_between(self) -> None:
        curve = keys_curve([{"t": 0, "value": 0, "ease": "in"}, [1, 10]])
        self.assertEqual(float(curve(-1)), 0.0)
        self.assertEqual(float(curve(2)), 10.0)
        self.assertAlmostEqual(float(curve(0.5)), 2.5)  # ease in: x squared

    def test_an_op_the_reference_lacks_or_an_invalid_graph_is_refused_by_name(self) -> None:
        with self.assertRaisesRegex(ValidationError, "signal.estimate.*recorded"):
            run({"ports": {"a": "picture"},
                 "nodes": {"d": {"op": "signal.estimate", "picture": "a", "kind": "depth_relative", "model": "m"},
                           "out": {"op": "warp.displace", "in": "a", "map": "d"}}, "output": "out"}, a=solid(1, 1, 1))
        with self.assertRaisesRegex(ValidationError, "not valid"):
            run({"nodes": {"out": {"op": "merge.over"}}, "output": "out"})

    def test_every_op_it_claims_is_a_spec_op(self) -> None:
        self.assertLessEqual(IMPLEMENTED, set(OPS))
        self.assertFalse(any("op" in op.params for op in OPS.values()))  # a parameter may not shadow the node's op


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class FileTests(unittest.TestCase):
    def test_a_file_is_read_into_the_working_space(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "grey.png"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=0x808080:s=64x36",
                            "-frames:v", "1", str(path)], check=True)
            picture = read(path, 2, SIZE, FPS)
            self.assertEqual(picture.shape, (2, 36, 64, 4))
            # Code 128 is about 0.216 of the light, not half.
            self.assertAlmostEqual(float(picture[0, 0, 0, 0]), float(decode_srgb(np.float32(128 / 255))), places=2)


if __name__ == "__main__":
    unittest.main()
