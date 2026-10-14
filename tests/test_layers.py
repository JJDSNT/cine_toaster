"""A shot's layers (C4, CT-0075): written as a filmmaker thinks of them, compiled into the one graph."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from cine_toaster.compositing.gl import gl_unavailable_reason
from cine_toaster.compositing.layers import compile_layers
from cine_toaster.compositing.reference import decode_srgb, evaluate
from cine_toaster.compositing.schema import validate

W, H, FPS = 128, 72, 12


def solid(rgb_encoded, alpha: float = 1.0) -> np.ndarray:
    out = np.zeros((H, W, 4), np.float32)
    out[..., :3] = decode_srgb(np.asarray(rgb_encoded, np.float32)) * alpha
    out[..., 3] = alpha
    return out


def run(layers: list, sources: dict[str, np.ndarray], frames: int = 1, renderer=None) -> np.ndarray:
    """The layers drawn with each source given as a picture: the graph's source nodes become its ports."""

    graph, problems = compile_layers(layers)
    assert not problems, problems
    ports = {}
    for name, node in list(graph["nodes"].items()):
        if node["op"] == "generate.source":
            del graph["nodes"][name]
            ports[name] = "picture"
    graph["ports"] = ports
    problems = validate(graph)
    assert not problems, problems
    inputs = {}
    for port in ports:  # L1, L2...: the source of that layer
        index = int(port[1:].split("-")[0]) - 1
        source = layers[index]["source"]
        inputs[port] = sources[source] if port.count("-") == 0 else sources[layers[index]["key"]["reference"]]
    if renderer is not None:
        return np.stack(list(renderer.evaluate(graph, inputs, frames=frames, size=(W, H), fps=FPS, stream=True)))
    return evaluate(graph, inputs, frames=frames, size=(W, H), fps=FPS)


SKY, SEA = (0.3, 0.5, 0.9), (0.9, 0.5, 0.2)


class CompileTests(unittest.TestCase):
    def test_layers_become_one_valid_graph(self) -> None:
        graph, problems = compile_layers([
            {"source": "CUT"},
            {"source": "plates/launch.mp4", "start": 1.0,
             "place": {"translate": {"keys": [{"t": 0, "value": [0.6, -0.4], "ease": "out"}, [1, [0.3, -0.3]]]},
                       "scale": 0.4, "rotate": [0, 20, 0], "perspective": 35},
             "key": {"by": "colour", "colour": "#1fb34a", "tolerance": 0.08, "softness": 0.05},
             "garbage": {"shape": "rectangle", "points": [[0.1, 0], [0.9, 1]]},
             "border": {"width": 4, "colour": "#ffffff"},
             "shadow": {"offset": [0.01, 0.015], "blur": 12, "opacity": 0.6},
             "opacity": {"beats": {"low": 0.8, "high": 1.0}}},
        ])
        self.assertEqual(problems, [])
        self.assertEqual(validate(graph), [])
        self.assertEqual(graph["nodes"]["L1"], {"op": "generate.source", "take": "CUT"})
        self.assertEqual(graph["nodes"]["L2"]["file"], "plates/launch.mp4")
        self.assertEqual(graph["nodes"]["L2-key"]["colour"][1] > 0.4, True)  # the green, as linear
        self.assertEqual(graph["output"], "L2-over")

    def test_what_cannot_be_drawn_is_said_not_guessed(self) -> None:
        cases = {
            "has no blur": [{"source": "CUT"}, {"source": "B", "blur": 3}],
            "says no `source`": [{"source": "CUT"}, {"place": {"scale": 0.5}}],
            "mode is 'multiply'": [{"source": "CUT"}, {"source": "B", "mode": "multiply"}],
            "is at the back": [{"source": "CUT", "opacity": 0.5}],
            "place has no spin": [{"source": "CUT"}, {"source": "B", "place": {"spin": 3}}],
            "is a shape": [{"source": "CUT"}, {"source": "B", "matte": {"shape": "star"}}],
            "border is": [{"source": "CUT"}, {"source": "B", "border": {"width": -1}}],
            "needs a `reference`": [{"source": "CUT"}, {"source": "B", "key": {"by": "difference", "tolerance": 0.1}}],
            "keys: [...]": [{"source": "CUT"}, {"source": "B", "place": {"scale": {"curve": "x"}}}],
        }
        for expected, layers in cases.items():
            with self.subTest(expected=expected):
                _, problems = compile_layers(layers)
                self.assertTrue(any(expected in problem for problem in problems), problems)


class DrawTests(unittest.TestCase):
    def test_a_picture_flies_into_a_corner_holds_and_flies_out(self) -> None:
        """The ADO move: eased keys on its place, the picture playing all along."""

        layers = [{"source": "sea"},
                  {"source": "sky", "place": {
                      "scale": 0.3,
                      "translate": {"keys": [{"t": 0.0, "value": [0.9, -0.6], "ease": "out"},
                                             {"t": 1.0, "value": [0.3, -0.3], "ease": "hold"},
                                             {"t": 2.0, "value": [0.3, -0.3], "ease": "in"},
                                             [3.0, [-0.9, 0.6]]]}}}]
        frames = run(layers, {"sea": solid(SEA), "sky": solid(SKY)}, frames=36)
        blue = frames[..., 2] > frames[..., 0]  # where the flown picture is

        def centre(frame: int) -> tuple[float, float] | None:
            ys, xs = np.nonzero(blue[frame])
            return (float(xs.mean() / W), float(ys.mean() / H)) if len(xs) else None

        self.assertIsNone(centre(0))  # it starts outside the frame
        held = [centre(frame) for frame in range(13, 23)]
        for place in held:  # held in the top right corner for a second
            self.assertAlmostEqual(place[0], 0.8, delta=0.02)
            self.assertAlmostEqual(place[1], 0.2, delta=0.02)
        self.assertIsNone(centre(35))  # and gone at the end

    def test_a_border_and_a_shadow_follow_the_placed_picture(self) -> None:
        layers = [{"source": "sea"},
                  {"source": "sky", "place": {"scale": 0.4},
                   "border": {"width": 40, "colour": "#ffffff"},  # 4 px at 72 lines
                   "shadow": {"offset": [0.08, 0.1], "blur": 0, "opacity": 1.0}}]
        out = run(layers, {"sea": solid(SEA), "sky": solid(SKY)})[0]
        # The picture spans 0.3..0.7 of the frame; its border just outside it is white, and past it the sea.
        self.assertGreater(float(out[H // 2, int(0.7 * W) + 2, :3].min()), 0.95)
        self.assertLess(float(out[int(0.2 * H), int(0.7 * W) + 8, 2]), 0.5)
        # Below and to the right of it, the shadow darkens the sea; above and to the left, the sea is untouched.
        sea = decode_srgb(np.asarray(SEA, np.float32))
        self.assertLess(float(out[int(0.78 * H), int(0.76 * W), 0]), 0.05)
        self.assertAlmostEqual(float(out[int(0.2 * H), int(0.2 * W), 0]), float(sea[0]), places=3)

    def test_a_person_on_a_light_background_is_keyed_over_another_picture(self) -> None:
        shot = solid((0.92, 0.92, 0.9))  # a light backdrop
        shot[20:60, 50:78, :3] = decode_srgb(np.asarray((0.35, 0.25, 0.2), np.float32))  # a person
        layers = [{"source": "sea"},
                  {"source": "person", "key": {"by": "luma", "low": 0.7, "high": 0.85, "invert": True},
                   "garbage": {"shape": "rectangle", "points": [[0.2, 0.0], [0.8, 1.0]]}}]
        out = run(layers, {"sea": solid(SEA), "person": shot})[0]
        sea = decode_srgb(np.asarray(SEA, np.float32))
        np.testing.assert_allclose(out[5, 5, :3], sea, atol=1e-4)  # the backdrop is gone
        person = decode_srgb(np.asarray((0.35, 0.25, 0.2), np.float32))
        np.testing.assert_allclose(out[40, 64, :3], person, atol=1e-4)  # the person stays

    def test_a_window_is_replaced_by_a_landscape(self) -> None:
        room = solid((0.25, 0.22, 0.2))
        window = [[0.3, 0.2], [0.6, 0.2], [0.6, 0.7], [0.3, 0.7]]
        layers = [{"source": "room"}, {"source": "sky", "matte": {"shape": "polygon", "points": window}}]
        out = run(layers, {"room": room, "sky": solid(SKY)})[0]
        self.assertGreater(float(out[int(0.45 * H), int(0.45 * W), 2]), 0.7)  # the landscape in the window
        self.assertLess(float(out[int(0.9 * H), int(0.1 * W), 2]), 0.1)  # the room around it


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class LayerConformanceTests(unittest.TestCase):
    def test_gl_draws_a_layered_shot_as_the_reference_does(self) -> None:
        from cine_toaster.compositing.gl import GLRenderer

        shot = solid((0.92, 0.92, 0.9))
        shot[20:60, 50:78, :3] = decode_srgb(np.asarray((0.35, 0.25, 0.2), np.float32))
        layers = [{"source": "sea"},
                  {"source": "person", "key": {"by": "luma", "low": 0.7, "high": 0.85, "invert": True},
                   "garbage": {"shape": "ellipse", "points": [[0.2, 0.0], [0.8, 1.0]], "feather": 0.02},
                   "place": {"scale": {"keys": [[0, 1.0], {"t": 1, "value": 0.5, "ease": [0.2, 0.9, 0.3, 1.0]}]},
                             "rotate": [0, 25, 5], "perspective": 35},
                   "border": {"width": 8, "colour": "#ffd000"},
                   "shadow": {"offset": [0.03, 0.04], "blur": 10, "opacity": 0.7}}]
        sources = {"sea": solid(SEA), "person": shot}
        gl = GLRenderer()
        try:
            fast = run(layers, sources, frames=12, renderer=gl)
        finally:
            gl.release()
        exact = run(layers, sources, frames=12)
        self.assertLess(float(np.abs(exact - fast).mean()), 0.01)


class LoadTests(unittest.TestCase):
    def test_layers_in_a_scene_become_its_composite_and_bad_ones_are_findings(self) -> None:
        from cine_toaster.project import load_production

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
            (root / "scenes" / "010").mkdir(parents=True)
            (root / "scenes" / "010" / "scene.yaml").write_text(textwrap.dedent("""\
                scene: S1
                shots:
                  - n: 1
                    duration: 2
                    label: A window replaced.
                    layers:
                      - source: plates/room.png
                      - source: plates/sky.png
                        matte: {shape: polygon, points: [[0.3, 0.2], [0.6, 0.2], [0.6, 0.7], [0.3, 0.7]]}
                  - n: 2
                    duration: 2
                    label: Mistyped.
                    layers:
                      - source: plates/room.png
                      - source: plates/sky.png
                        mode: multiply
                  - n: 3
                    duration: 2
                    label: Both ways.
                    layers: [{source: plates/room.png}]
                    composite: {nodes: {out: {op: generate.solid, colour: [0, 0, 0, 1]}}, output: out}
                """))
            for name in ("room", "sky"):
                (root / "plates").mkdir(exist_ok=True)
                from PIL import Image

                Image.new("RGB", (16, 9), (40, 40, 40)).save(root / "plates" / f"{name}.png")
            scene = load_production(root)["scenes"][0]
        shots = {shot["id"]: shot for shot in scene["shots"]}
        self.assertEqual(shots["P1"]["composite"]["nodes"]["L2-matte"]["shape"], "polygon")
        codes = {(finding["code"], finding["shots"][0]) for finding in scene["findings"]
                 if finding["code"].startswith(("layers", "composite"))}
        self.assertEqual(codes, {("layers_invalid", "P2"), ("layers_and_composite", "P3")})


if __name__ == "__main__":
    unittest.main()
