"""C5 (CT-0076): the transition catalog as recipes of primitives -- one way of drawing a join."""

from __future__ import annotations

import unittest

import numpy as np

from cine_toaster.compositing.gl import gl_unavailable_reason
from cine_toaster.compositing.reference import decode_srgb, evaluate, read
from cine_toaster.transitions import list_transitions

W, H, FPS = 96, 54, 12


def catalog() -> dict[str, dict]:
    return {item["id"]: item for item in list_transitions() if item["origin"] == "built-in"}


def solid(rgb) -> np.ndarray:
    out = np.ones((H, W, 4), np.float32)
    out[..., :3] = rgb
    return out


FROM, TO = solid([0.8, 0.2, 0.1]), solid([0.05, 0.3, 0.9])


def join(item: dict, frames: int, renderer=None) -> np.ndarray:
    """The item's graph drawn as a join of two solid pictures, with its own pictures read."""

    inputs = {"from": FROM, "to": TO}
    for name, path in (item.get("inputs") or {}).items():
        if name in item["graph"]["ports"]:
            inputs[name] = read(path, frames, (W, H), FPS)
    if renderer is not None:
        return np.stack(list(renderer.evaluate(item["graph"], inputs, frames=frames, size=(W, H), fps=FPS,
                                               stream=True)))
    return evaluate(item["graph"], inputs, frames=frames, size=(W, H), fps=FPS)


class CatalogTests(unittest.TestCase):
    def test_no_reviewed_transition_reimplements_what_the_primitives_do(self) -> None:
        """Every built-in reviewed item is a recipe (or a matte join, or a reference clip); a closed shader stays
        only with the reason it cannot be a recipe yet."""

        for item in catalog().values():
            if not item["curated"]:
                continue
            with self.subTest(item=item["id"]):
                if item["kind"] == "glsl":
                    self.assertTrue(item["opaque_reason"], f"{item['id']} is a shader with no reason given")
                else:
                    self.assertIn(item["kind"], ("graph", "matte", "webm"))

    def test_a_recipe_needs_no_stand_in(self) -> None:
        for item in catalog().values():
            if item["kind"] == "graph":
                with self.subTest(item=item["id"]):
                    self.assertEqual(item["render"]["ffmpeg"], "graph")
                    self.assertTrue(item["preview"], "a recipe's preview is drawn from its graph")

    def test_a_replaced_shader_is_not_listed_beside_its_recipe(self) -> None:
        listed = list_transitions()
        replaced = {item["upstream"] for item in listed if item["kind"] == "graph" and item["upstream"]}
        raw = [item["id"] for item in listed if not item["curated"] and item["upstream"] in replaced]
        self.assertEqual(raw, [])


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class ConformanceTests(unittest.TestCase):
    def test_every_recipe_runs_on_gl_as_the_reference_draws_it(self) -> None:
        from cine_toaster.compositing.gl import renderer_for

        for item in catalog().values():
            if item["kind"] != "graph":
                continue
            with self.subTest(item=item["id"]):
                renderer = renderer_for(item["graph"])
                self.assertIsNotNone(renderer, f"{item['id']} falls back to the reference")
                exact, fast = join(item, 6), join(item, 6, renderer)
                self.assertLess(float(np.abs(exact - fast).mean()), 0.01)


class BehaviourTests(unittest.TestCase):
    def frame(self, item_id: str, progress: float) -> np.ndarray:
        """The join at a progress (frames are read at their centres: progress = (f + 0.5) / frames)."""

        frames = 20
        index = int(round(progress * frames - 0.5))
        return join(catalog()[item_id], frames)[index]

    def test_a_dissolve_mixes_in_linear_light(self) -> None:
        mid = self.frame("cross-dissolve", 0.5)
        np.testing.assert_allclose(mid[5, 5, :3], 0.5 * FROM[0, 0, :3] + 0.5 * TO[0, 0, :3], atol=0.03)

    def test_a_dip_passes_through_black_and_holds_there(self) -> None:
        self.assertLess(float(self.frame("dip-to-black", 0.5)[..., :3].max()), 1e-6)
        self.assertGreater(float(self.frame("dip-to-black", 0.1)[..., 0].mean()), 0.4)

    def test_the_iris_is_round_whatever_the_frame(self) -> None:
        opened = self.frame("iris-open", 0.3)[..., 2] > 0.5  # where `to` shows
        ys, xs = np.nonzero(opened)
        across, down = (xs.max() - xs.min() + 1), (ys.max() - ys.min() + 1)
        self.assertAlmostEqual(across / down, 1.0, delta=0.1)  # a circle, not the frame's ellipse

    def test_the_clock_sweeps_clockwise_from_twelve(self) -> None:
        quarter = self.frame("clock-wipe", 0.3)[..., 2] > 0.5
        self.assertTrue(quarter[: H // 3, W // 2 + 5:].mean() > 0.9)  # top right, swept
        self.assertTrue(quarter[: H // 3, : W // 2 - 5].mean() < 0.1)  # top left, not yet
        self.assertTrue(quarter[H // 2 + 5:, : W // 2 - 5].mean() < 0.1)  # the bottom left, not yet

    def test_the_diamond_opens_from_the_centre(self) -> None:
        early = self.frame("diamond-wipe", 0.25)[..., 2] > 0.5
        self.assertTrue(early[H // 2, W // 2])
        self.assertFalse(early[2, 2])

    def test_the_flip_folds_the_outgoing_to_its_right_edge(self) -> None:
        folding = self.frame("switcher-flip", 0.25)
        self.assertLess(float(folding[:, :15, :3].max()), 1e-6)  # black where it has left
        self.assertGreater(float(folding[:, -10:, 0].mean()), 0.4)  # `from`, folding toward the right


class GeneratedMatteTests(unittest.TestCase):
    """A join's matte drawn by a generator, inside the matte join's own graph (CT-0076)."""

    def test_a_generated_matte_is_a_node_of_the_join(self) -> None:
        from cine_toaster.mattes import generated_problem, generated_recipe

        graph = generated_recipe({"gradient": {"kind": "conic"}})
        self.assertNotIn("matte_clip", graph["ports"])
        self.assertEqual(graph["nodes"]["matte_clip"], {"op": "generate.gradient", "kind": "conic"})
        drawn = evaluate(graph, {"from": FROM, "to": TO}, frames=4, size=(W, H), fps=FPS)
        self.assertGreater(float(drawn[1, : H // 3, W // 2 + 5:, 2].mean()), 0.8)  # clockwise from twelve
        self.assertIsNone(generated_problem({"noise": {"kind": "perlin", "scale": 4, "seed": 2}}))
        self.assertIn("one of", generated_problem({"plasma": {}}))
        self.assertIn("kind", generated_problem({"gradient": {"kind": "spiral"}}))

    def test_a_scene_refuses_a_generated_matte_that_cannot_be_drawn(self) -> None:
        import tempfile
        import textwrap
        from pathlib import Path

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
                    label: A.
                  - n: 2
                    duration: 2
                    label: B.
                    transition: {id: matte-wipe, matte: {noise: {kind: perlin, scale: 3}}}
                  - n: 3
                    duration: 2
                    label: C.
                    transition: {id: matte-wipe, matte: {gradient: {kind: spiral}}}
                """))
            scene = load_production(root)["scenes"][0]
        codes = [(f["code"], f["shots"][0]) for f in scene["findings"]
                 if f["code"].startswith(("transition_matte", "transition_input"))]
        self.assertEqual(codes, [("transition_matte_invalid", "P3")])


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class MovingTextureTests(unittest.TestCase):
    def test_a_shader_reads_a_moving_texture_frame_by_frame(self) -> None:
        """A gl-transitions shader's texture is a port of the graph, read at every frame (CT-0072's B1): a clip
        given as its texture moves in the shader's picture."""

        import tempfile
        from pathlib import Path

        from cine_toaster.assembly import shader_recipe
        from cine_toaster.compositing.gl import renderer_for

        with tempfile.TemporaryDirectory() as raw:
            shader = Path(raw) / "show.glsl"
            shader.write_text("uniform sampler2D clip;\nvec4 transition(vec2 uv) { return texture2D(clip, uv); }\n")
            graph = shader_recipe({"shader": str(shader), "textures": {"clip": "clip.png"}})
            clip = np.stack([solid([float(f) / 5.0] * 3) for f in range(6)])
            drawn = np.stack(list(renderer_for(graph).evaluate(graph, {"from": FROM, "to": TO, "clip": clip},
                                                               frames=6, size=(W, H), fps=FPS, stream=True)))
        means = drawn[..., :3].mean(axis=(1, 2, 3))
        self.assertTrue(np.all(np.diff(means) > 0.01), means)  # brighter with each frame of the clip


if __name__ == "__main__":
    unittest.main()
