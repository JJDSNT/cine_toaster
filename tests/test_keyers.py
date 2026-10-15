"""Keyers as matte generators (C4, CT-0075): luma, colour and difference, the same in the reference and on GL."""

from __future__ import annotations

import unittest

import numpy as np

from cine_toaster.compositing.gl import gl_unavailable_reason
from cine_toaster.compositing.reference import decode_srgb, evaluate

W, H = 64, 36


def picture(rgb_encoded: tuple[float, float, float]) -> np.ndarray:
    """A solid picture from display-encoded colour, as a file would give it (linear, premultiplied, opaque)."""

    out = np.ones((H, W, 4), np.float32)
    out[..., :3] = decode_srgb(np.asarray(rgb_encoded, np.float32))
    return out


GREEN = (0.10, 0.70, 0.25)


def screen_with_actor() -> np.ndarray:
    """A green screen, lit a little less on its left half, an actor in grey and skin in the middle."""

    out = picture(GREEN)
    out[:, : W // 2, :3] *= 0.8  # the same green, a fifth darker in linear light
    out[10:26, 24:40, :3] = decode_srgb(np.asarray((0.55, 0.55, 0.55), np.float32))  # a grey shirt
    out[12:18, 28:36, :3] = decode_srgb(np.asarray((0.85, 0.62, 0.50), np.float32))  # a face
    return out


def key_graph(**key) -> dict:
    ports = {"a": "picture", **({"plate": "picture"} if key.get("by") == "difference" else {})}
    node = {"op": "matte.key", "picture": "a", **key}
    if key.get("by") == "difference":
        node["reference"] = "plate"
    # Shown as white over black, so the graph ends in a picture; channel 0 is the matte.
    return {"ports": ports, "nodes": {"key": node, "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
                                      "black": {"op": "generate.solid", "colour": [0, 0, 0, 1]},
                                      "out": {"op": "merge.over", "front": "white", "back": "black", "matte": "key"}},
            "output": "out"}


def matte_of(graph: dict, inputs: dict) -> np.ndarray:
    return evaluate(graph, inputs, frames=1, size=(W, H), fps=12)[0, ..., 0]


SCREEN = decode_srgb(np.asarray(GREEN, np.float32))
COLOUR = key_graph(by="colour", colour=SCREEN.tolist(), tolerance=0.25, softness=0.05)


class ColourKeyTests(unittest.TestCase):
    """By colour difference (CT-0075): how much the screen's channel exceeds the others, against the screen's own."""

    def test_the_screen_goes_and_the_actor_stays(self) -> None:
        matte = matte_of(COLOUR, {"a": screen_with_actor()})
        self.assertLess(float(matte[2:8, 44:60].max()), 0.01)  # the lit screen
        # A screen a fifth darker has a fifth less excess: it keys within a tolerance of 0.25. A deep shadow
        # needs more tolerance, or a clean plate and the difference key.
        self.assertLess(float(matte[2:8, 4:20].max()), 0.01)
        self.assertGreater(float(matte[20:24, 26:38].min()), 0.99)  # the grey shirt
        self.assertGreater(float(matte[13:17, 29:35].min()), 0.99)  # the face

    @staticmethod
    def unmixed(subject: np.ndarray, share: float) -> np.ndarray:
        """A strand over the screen, both mixed in light (C = share F + (1 - share) S), keyed and despilled."""

        edge = np.ones((H, W, 4), np.float32)
        edge[..., :3] = share * subject + (1 - share) * SCREEN
        graph = {"ports": {"a": "picture"},
                 "nodes": {"key": {"op": "matte.key", "picture": "a", "by": "colour", "colour": SCREEN.tolist(),
                                   "tolerance": 0.0, "softness": 1.0},
                           "out": {"op": "colour.despill", "in": "a", "matte": "key", "colour": SCREEN.tolist()}},
                 "output": "out"}
        return evaluate(graph, {"a": edge}, frames=1, size=(W, H), fps=12)[0, 5, 5]

    def test_an_edge_pixel_gets_the_subjects_share_and_the_screen_is_taken_out(self) -> None:
        """For a subject with no excess of the screen's channel (grey, white), exact: the matte is its share and
        what is left is that share of it, with no green."""

        grey = decode_srgb(np.asarray((0.6, 0.6, 0.6), np.float32))
        out = self.unmixed(grey, 0.4)
        self.assertAlmostEqual(float(out[3]), 0.4, places=4)
        np.testing.assert_allclose(out[:3], 0.4 * grey, atol=1e-4)

    def test_a_coloured_strand_is_close_and_left_with_no_green(self) -> None:
        """Brown hair has less green than red: its share is read a little high (the larger of the other channels
        changes across the mix), and no green above red is left on it."""

        hair = decode_srgb(np.asarray((0.45, 0.28, 0.15), np.float32))
        out = self.unmixed(hair, 0.4)
        self.assertAlmostEqual(float(out[3]), 0.4, delta=0.05)
        self.assertLessEqual(float(out[1]), float(max(out[0], out[2])) + 1e-6)

    def test_the_light_a_screen_throws_on_the_subject_is_held_back(self) -> None:
        """Spill on an opaque subject: its green above its other channels is held to the larger of them."""

        spilled = picture((0.55, 0.62, 0.5))  # a grey shirt with a green cast
        graph = {"ports": {"a": "picture"},
                 "nodes": {"out": {"op": "colour.despill", "in": "a", "colour": SCREEN.tolist()}}, "output": "out"}
        out = evaluate(graph, {"a": spilled}, frames=1, size=(W, H), fps=12)[0, 5, 5]
        self.assertAlmostEqual(float(out[1]), float(out[0]), places=5)  # green no higher than red
        self.assertAlmostEqual(float(out[2]), float(spilled[0, 0, 2]), places=5)  # blue untouched
        skin = picture((0.85, 0.62, 0.50))
        np.testing.assert_allclose(evaluate(graph, {"a": skin}, frames=1, size=(W, H), fps=12)[0], skin, atol=1e-6)


class DifferenceKeyTests(unittest.TestCase):
    def test_what_differs_from_the_clean_plate_is_kept(self) -> None:
        plate = picture((0.6, 0.6, 0.62))
        shot = plate.copy()
        shot[10:26, 24:40, :3] = decode_srgb(np.asarray((0.2, 0.3, 0.5), np.float32))
        matte = matte_of(key_graph(by="difference", tolerance=0.05, softness=0.05), {"a": shot, "plate": plate})
        self.assertEqual(float(matte[0:8].max()), 0.0)
        self.assertEqual(float(matte[12:24, 26:38].min()), 1.0)


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class KeyConformanceTests(unittest.TestCase):
    def test_gl_keys_as_the_reference_does(self) -> None:
        from cine_toaster.compositing.gl import renderer_for

        plate = picture((0.6, 0.6, 0.62))
        edge = np.ones((H, W, 4), np.float32)
        edge[..., :3] = np.linspace(0, 1, W)[None, :, None] * SCREEN + (1 - np.linspace(0, 1, W)[None, :, None]) * 0.3
        despilled = {"ports": {"a": "picture"},
                     "nodes": {"key": {"op": "matte.key", "picture": "a", "by": "colour", "colour": SCREEN.tolist(),
                                       "tolerance": 0.05, "softness": 0.9},
                               "out": {"op": "colour.despill", "in": "a", "matte": "key", "colour": SCREEN.tolist()}},
                     "output": "out"}
        cases = [(COLOUR, {"a": screen_with_actor()}), (despilled, {"a": edge}),
                 (key_graph(by="difference", tolerance=0.05, softness=0.1),
                  {"a": screen_with_actor(), "plate": plate}),
                 (key_graph(by="luma", low=0.3, high=0.6, invert=True), {"a": screen_with_actor()})]
        for graph, inputs in cases:
            with self.subTest(graph=sorted(graph["nodes"])):
                renderer = renderer_for(graph)
                self.assertIsNotNone(renderer)
                exact = evaluate(graph, inputs, frames=1, size=(W, H), fps=12)
                fast = np.stack(list(renderer.evaluate(graph, inputs, frames=1, size=(W, H), fps=12, stream=True)))
                self.assertLess(float(np.abs(exact.squeeze() - fast.squeeze()).max()), 0.01)


if __name__ == "__main__":
    unittest.main()
