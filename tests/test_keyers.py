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
    """A green screen with a shadow on its left half, an actor in grey and skin in the middle."""

    out = picture(GREEN)
    out[:, : W // 2, :3] = decode_srgb(np.asarray(GREEN, np.float32) * 0.45)  # the same green in shadow
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


COLOUR = key_graph(by="colour", colour=decode_srgb(np.asarray(GREEN, np.float32)).tolist(), tolerance=0.08,
                   softness=0.05)


class ColourKeyTests(unittest.TestCase):
    def test_the_screen_goes_and_its_shadow_with_it_while_the_actor_stays(self) -> None:
        matte = matte_of(COLOUR, {"a": screen_with_actor()})
        self.assertLess(float(matte[2:8, 44:60].max()), 0.01)  # the lit screen
        self.assertLess(float(matte[2:8, 4:20].max()), 0.01)  # the screen in shadow: chroma ignores brightness
        self.assertGreater(float(matte[20:24, 26:38].min()), 0.99)  # the grey shirt
        self.assertGreater(float(matte[13:17, 29:35].min()), 0.99)  # the face

    def test_softness_spreads_the_edge_between_tolerance_and_beyond(self) -> None:
        near = picture((0.18, 0.66, 0.30))  # a green a little off the key
        hard = matte_of(key_graph(by="colour", colour=decode_srgb(np.asarray(GREEN, np.float32)).tolist(),
                                  tolerance=0.02, softness=0.0), {"a": near})
        soft = matte_of(key_graph(by="colour", colour=decode_srgb(np.asarray(GREEN, np.float32)).tolist(),
                                  tolerance=0.02, softness=0.5), {"a": near})
        self.assertEqual(float(hard.mean()), 1.0)
        self.assertGreater(float(soft.mean()), 0.0)
        self.assertLess(float(soft.mean()), 0.5)


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
        cases = [(COLOUR, {"a": screen_with_actor()}),
                 (key_graph(by="difference", tolerance=0.05, softness=0.1),
                  {"a": screen_with_actor(), "plate": plate}),
                 (key_graph(by="luma", low=0.3, high=0.6, invert=True), {"a": screen_with_actor()})]
        for graph, inputs in cases:
            with self.subTest(by=graph["nodes"]["key"]["by"]):
                renderer = renderer_for(graph)
                self.assertIsNotNone(renderer)
                exact = evaluate(graph, inputs, frames=1, size=(W, H), fps=12)
                fast = np.stack(list(renderer.evaluate(graph, inputs, frames=1, size=(W, H), fps=12, stream=True)))
                self.assertLess(float(np.abs(exact.squeeze() - fast.squeeze()).max()), 0.01)


if __name__ == "__main__":
    unittest.main()
