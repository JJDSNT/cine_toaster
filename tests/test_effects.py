"""C6, first stage (CT-0077): the VFX catalog's effects drawn by the compositing graph, not by FFmpeg chains."""

from __future__ import annotations

import threading
import unittest
from pathlib import Path

import numpy as np

from cine_toaster.compositing.effects import BUILDERS, graph_for, primitives_of
from cine_toaster.compositing.gl import gl_unavailable_reason
from cine_toaster.compositing.reference import evaluate
from cine_toaster.compositing.schema import validate
from cine_toaster.vfx import list_effects

W, H, FPS = 128, 72, 24
SOURCE = Path(__file__).parents[1] / "src" / "cine_toaster" / "vfx.py"


def picture() -> np.ndarray:
    """Detail an effect can be seen on: a left half darker than the right, a bright square in the middle."""

    out = np.ones((H, W, 4), np.float32)
    out[..., :3] = 0.3
    out[:, : W // 2, :3] = 0.1
    out[H // 2 - 8:H // 2 + 8, W // 2 - 8:W // 2 + 8, :3] = 0.9
    return out


def drawn(kind: str, frames: int = 12, shot: float = 0.5, **params) -> np.ndarray:
    graph = graph_for([{"effect": kind, "params": params}], shot, FPS)
    return evaluate(graph, {"picture": picture()}, frames=frames, size=(W, H), fps=FPS)


class CatalogTests(unittest.TestCase):
    def test_every_effect_the_graph_draws_says_its_primitives(self) -> None:
        """C6's rule: every item says which primitives it uses -- and says it truly."""

        graph_drawn = [item for item in list_effects() if item["engine"] in ("graph", "blender")]
        self.assertEqual({item["effect"] for item in graph_drawn if item["engine"] == "graph"}, set(BUILDERS))
        for item in graph_drawn:
            # A Blender effect is rendered by Blender and laid as an element: the element's primitives.
            kind = "element" if item["engine"] == "blender" else item["effect"]
            with self.subTest(item=item["id"]):
                self.assertEqual(sorted(item["primitives"]), primitives_of(kind, item["params"]))

    def test_no_effect_is_drawn_by_an_ffmpeg_chain_of_its_own_any_more(self) -> None:
        source = SOURCE.read_text()
        self.assertNotIn("def _chain(", source)  # the FFmpeg filter chains are gone (CT-0077)
        for formula in ("hflip", "gblur", "rgbashift", "vignette=", "noise=alls", "drawgrid", "colorkey=", "lut3d=",
                        "alphamerge", "overlay=", "blend=all_mode"):
            self.assertNotIn(formula, source, formula)

    def test_every_effect_is_a_valid_graph(self) -> None:
        for kind in BUILDERS:
            with self.subTest(kind=kind):
                prepared = {"_clip": "element.mov"} if kind == "element" else {}
                self.assertEqual(validate(graph_for([{"effect": kind, "params": {}, "prepared": prepared}], 1.0, FPS)),
                                 [])


class BehaviourTests(unittest.TestCase):
    def test_a_mirror_flips_left_and_right(self) -> None:
        out = drawn("mirror", frames=1)[0]
        self.assertGreater(float(out[5, 5, 0]), float(out[5, -5, 0]))  # the bright half is now on the left

    def test_a_crop_enlarges_a_detail(self) -> None:
        out = drawn("crop", frames=1, x=0.375, y=0.25, width=0.25, height=0.5)[0]
        self.assertGreater(float(out[H // 2, W // 2, 0]), 0.8)  # the bright square fills the middle
        self.assertGreater(float((out[..., 0] > 0.8).mean()), 0.15)

    def test_a_fade_ends_in_black(self) -> None:
        out = drawn("fade-out", frames=12, shot=0.5, length=0.25)
        self.assertGreater(float(out[0, ..., :3].mean()), 0.2)
        # The last frame's centre is 0.479 s: 92% of the way to black.
        self.assertLess(float(out[-1, ..., :3].max()), 0.1)
        self.assertLess(float(out[-1, ..., :3].mean()), 0.1 * float(out[0, ..., :3].mean()))

    def test_a_flash_peaks_at_its_start(self) -> None:
        out = drawn("flash", frames=12, start=0.25, length=0.1, strength=1.0)
        brightness = out[..., :3].mean(axis=(1, 2, 3))
        self.assertEqual(int(np.argmax(brightness)), 5)  # the frame whose centre is nearest 0.25 s
        self.assertAlmostEqual(float(brightness[0]), float(picture()[..., :3].mean()), places=4)

    def test_a_defocus_comes_into_focus(self) -> None:
        out = drawn("defocus", frames=12, shot=0.5, length=0.4)
        edge = lambda frame: float(np.abs(np.diff(frame[H // 2, :, 0])).max())  # noqa: E731
        self.assertLess(edge(out[0]), edge(out[-1]))  # soft first, sharp at the end

    def test_a_vignette_darkens_the_corners_not_the_centre(self) -> None:
        out, original = drawn("vignette", frames=1, strength=0.8)[0], picture()
        self.assertLess(float(out[1, -2, 0]), float(original[1, -2, 0]) * 0.5)
        self.assertAlmostEqual(float(out[H // 2, W // 2, 0]), float(original[H // 2, W // 2, 0]), delta=0.02)

    def test_aberration_moves_red_and_blue_apart(self) -> None:
        out = drawn("aberration", frames=1, strength=1.0)[0]
        row = out[H // 2]
        red_edge = int(np.argmax(np.diff(row[:, 0]) > 0.2))
        blue_edge = int(np.argmax(np.diff(row[:, 2]) > 0.2))
        self.assertLess(red_edge, blue_edge)  # red shifted left, blue right


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class ConformanceTests(unittest.TestCase):
    def test_every_effect_runs_on_gl_as_the_reference_draws_it(self) -> None:
        from cine_toaster.compositing.gl import renderer_for

        rng = np.random.default_rng(3)
        detail = np.dstack([rng.uniform(0.05, 0.8, (H, W, 3)).astype(np.float32), np.ones((H, W), np.float32)])
        for kind in [kind for kind in BUILDERS if kind != "element"]:  # an element is tested with its clip below
            with self.subTest(kind=kind):
                graph = graph_for([{"effect": kind, "params": {"strength": 0.6, "start": 0.1, "length": 0.2}}],
                                  0.5, FPS)
                renderer = renderer_for(graph)
                self.assertIsNotNone(renderer, f"{kind} falls back to the reference")
                exact = evaluate(graph, {"picture": detail}, frames=6, size=(W, H), fps=FPS)
                fast = np.stack(list(renderer.evaluate(graph, {"picture": detail}, frames=6, size=(W, H), fps=FPS,
                                                       stream=True)))
                self.assertLess(float(np.abs(exact - fast).mean()), 0.01)

    def test_an_element_is_laid_on_gl_as_the_reference_lays_it(self) -> None:
        """Each blend of a stock element -- screen for one on black, over for one with alpha, a key with its spill
        taken out for one on green -- placed, the same in both renderers (CT-0077, C6 B). Its delay is in its
        prepared clip (`vfx.prepare_element`), tested with the VFX catalog."""

        import subprocess
        import tempfile

        from cine_toaster.compositing.gl import renderer_for

        with tempfile.TemporaryDirectory() as raw:
            clip = Path(raw) / "element.mov"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "color=c=0x00FF00:s=160x90:d=0.5:r=24,drawbox=x=60:y=30:w=40:h=30:color=orange:t=fill",
                            "-c:v", "qtrle", "-pix_fmt", "argb", str(clip)], check=True)
            for blend in ("screen", "alpha", "key"):
                with self.subTest(blend=blend):
                    graph = graph_for([{"effect": "element", "params": {"scale": 0.6, "x": 0.4},
                                        "prepared": {"_clip": str(clip), "_blend": blend, "_key_color": "0x00FF00"}}],
                                      0.5, FPS)
                    exact = evaluate(graph, {"picture": picture()}, frames=6, size=(W, H), fps=FPS)
                    fast = np.stack(list(renderer_for(graph).evaluate(graph, {"picture": picture()}, frames=6,
                                                                      size=(W, H), fps=FPS, stream=True)))
                    self.assertLess(float(np.abs(exact - fast).mean()), 0.01)
                    if blend == "key":
                        late = exact[-1]
                        self.assertLess(float(late[..., 1].max() - late[..., 0].max()), 0.05)  # no green left

    def test_a_look_has_no_fixed_place_in_the_graph(self) -> None:
        """colour.lut is a node like any other (the user, 2026-10-14): on one picture before it is merged, or on
        the merged result -- the graph decides, the op does not. Both drawn the same by GL and the reference."""

        from cine_toaster.compositing.gl import renderer_for

        view = "ACES 2.0 - SDR 100 nits (Rec.709)"
        element, below = picture() * 4.0, picture()  # an element with highlights past white, over a picture
        element[..., 3] = 1.0
        element[:, : W // 2] = 0.0  # it covers the right half only
        before = {"ports": {"element": "picture", "below": "picture"}, "output": "out",
                  "nodes": {"graded": {"op": "colour.lut", "in": "element", "view": view},
                            "out": {"op": "merge.over", "front": "graded", "back": "below"}}}
        after = {"ports": {"element": "picture", "below": "picture"}, "output": "out",
                 "nodes": {"merged": {"op": "merge.over", "front": "element", "back": "below"},
                           "out": {"op": "colour.lut", "in": "merged", "view": view}}}
        inputs = {"element": element, "below": below}
        drawn = {}
        for name, graph in (("before", before), ("after", after)):
            self.assertEqual(validate(graph), [])
            exact = evaluate(graph, inputs, frames=1, size=(W, H), fps=FPS)
            fast = np.stack(list(renderer_for(graph).evaluate(graph, inputs, frames=1, size=(W, H), fps=FPS,
                                                              stream=True)))
            self.assertLess(float(np.abs(exact - fast).mean()), 0.01, name)
            drawn[name] = exact[0]
        # Graded before the merge, the picture below it is untouched; graded after, it is graded too.
        np.testing.assert_allclose(drawn["before"][:, : W // 2], below[:, : W // 2], atol=1e-6)
        self.assertGreater(float(np.abs(drawn["after"][:, : W // 2] - below[:, : W // 2]).mean()), 0.01)

    def test_gl_draws_in_several_threads_at_once(self) -> None:
        """Each thread has its own GL context (CT-0077): previews are drawn in workers, and a context made current
        in one thread cannot be made current in another -- GLX refuses and Xlib ends the process."""

        from cine_toaster.compositing.gl import renderer_for

        graph = graph_for([{"effect": "vignette", "params": {"strength": 0.5}}], 0.5, FPS)
        here = renderer_for(graph)
        results: dict[int, tuple[object, float]] = {}

        def draw(index: int) -> None:
            renderer = renderer_for(graph)
            frames = list(renderer.evaluate(graph, {"picture": picture()}, frames=2, size=(W, H), fps=FPS,
                                            stream=True))
            results[index] = (renderer, float(frames[0][..., 0].mean()))

        workers = [threading.Thread(target=draw, args=(index,)) for index in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(len(results), 2)
        renderers = {id(renderer) for renderer, _ in results.values()} | {id(here)}
        self.assertEqual(len(renderers), 3)  # one per thread
        self.assertAlmostEqual(results[0][1], results[1][1], places=6)


if __name__ == "__main__":
    unittest.main()
