"""C6 stage D (CT-0077): the title catalog drawn by the compositing graph, not by FFmpeg's drawtext."""

from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from cine_toaster.compositing.gl import gl_unavailable_reason
from cine_toaster.compositing.reference import evaluate
from cine_toaster.compositing.schema import validate
from cine_toaster.compositing.title_graphs import BUILDERS, graph_for, primitives_of
from cine_toaster.titles import BASE_PARAMS, expand, list_titles

W, H, FPS = 256, 144, 12
SOURCE = Path(__file__).parents[1] / "src" / "cine_toaster" / "titles.py"


def black() -> np.ndarray:
    out = np.zeros((H, W, 4), np.float32)
    out[..., 3] = 1.0
    return out


def drawn(effect: str, length: float = 2.0, frames: int | None = None, **params) -> np.ndarray:
    title = {"engine": "graph", "effect": effect, "params": {**BASE_PARAMS, "text": "TITLE", **params}}
    graph = graph_for(title, length, FPS)
    return evaluate(graph, {"picture": black()}, frames=frames or int(length * FPS), size=(W, H), fps=FPS)


def lit(frame: np.ndarray) -> float:
    return float((frame[..., :3].max(axis=-1) > 0.05).mean())


class CatalogTests(unittest.TestCase):
    def test_every_title_says_its_primitives_truly(self) -> None:
        for item in list_titles():
            with self.subTest(item=item["id"]):
                self.assertIn(item["engine"], ("graph", "blender"))
                self.assertEqual(sorted(item["primitives"]), primitives_of(item))

    def test_no_title_is_drawn_by_drawtext_any_more(self) -> None:
        source = SOURCE.read_text()
        for formula in ("drawtext", "drawbox", "def ffmpeg_filters", "def _neon_graph", "geq=", "overlay="):
            self.assertNotIn(formula, source, formula)

    def test_every_animation_is_a_valid_graph(self) -> None:
        for effect in BUILDERS:
            with self.subTest(effect=effect):
                title = {"engine": "graph", "effect": effect,
                         "params": {**BASE_PARAMS, "text": "A B", "subtitle": "s", "line2": "c"}}
                self.assertEqual(validate(graph_for(title, 2.0, FPS)), [])


class BehaviourTests(unittest.TestCase):
    def test_a_title_whose_fades_do_not_fit_still_rises(self) -> None:
        """Enter at 1 s, rise over 2.5 s, fall over 2 s, in a 3 s shot: it rises while it can, as FFmpeg's did."""

        out = drawn("fade", length=3.0, enter_at=1.0, fade_in=2.5, fade_out=2.0, size=60)
        brightness = [float(frame[..., :3].max()) for frame in out]
        self.assertEqual(brightness[5], 0.0)  # 0.46 s: not yet
        self.assertGreater(brightness[24], brightness[18])  # still rising
        self.assertGreater(brightness[34], 0.3)

    def test_a_typewriter_shows_its_letters_one_after_another(self) -> None:
        out = drawn("typewriter", length=3.0, text="ABCDEFGH", size=40, enter_at=0.0, typing_seconds=1.6)
        covered = [lit(frame) for frame in out[:24]]
        self.assertTrue(all(b >= a for a, b in zip(covered, covered[1:])))  # it only grows
        self.assertGreater(covered[20], covered[3] * 3)

    def test_word_by_word_shows_whole_words(self) -> None:
        out = drawn("words", length=3.0, text="one two three", size=40, enter_at=0.0, fade_out=0.5)
        counts = sorted({round(lit(frame), 4) for frame in out[:20] if lit(frame) > 0})
        self.assertEqual(len(counts), 3)  # three steps: one, two, three words

    def test_a_lower_third_sits_on_the_left_on_its_bar(self) -> None:
        out = drawn("lower-third", length=2.0, text="NAME", subtitle="role", size=36, enter_at=0.0, fade_in=0.3)[8]
        ys, xs = np.nonzero(out[..., :3].max(axis=-1) > 0.4)
        self.assertLess(xs.max(), W * 0.45)  # on the left
        self.assertGreater(ys.min(), H * 0.75)  # low in the frame
        self.assertGreater(float(out[int(H * 0.9), int(W * 0.3), 3]), 0.5)  # the bar

    def test_credits_climb(self) -> None:
        out = drawn("roll", length=3.0, text="A\\nB\\nC", size=30, enter_at=0.0)
        centre = lambda frame: float(np.nonzero(frame[..., :3].max(axis=-1) > 0.3)[0].mean())  # noqa: E731
        self.assertLess(centre(out[24]), centre(out[12]))  # higher later

    def test_neon_lights_what_is_around_it(self) -> None:
        out = drawn("neon", length=2.0, text="OPEN", size=60, enter_at=0.0, ignite=0.1, fade_out=0.3)[12]
        letters = out[..., :3].max(axis=-1) > 0.5
        around = (out[..., 0] > 0.01) & ~letters
        self.assertGreater(float(around.mean()), float(letters.mean()))  # the glow spills past the tubes


class TextTests(unittest.TestCase):
    def text(self, **params) -> np.ndarray:
        node = {"op": "generate.text", "text": "Hello", "size": 40, "colour": [1, 1, 1, 1], **params}
        graph = {"ports": {}, "nodes": {"t": node}, "output": "t"}
        return evaluate(graph, {}, frames=1, size=(W, H), fps=FPS)[0, ..., 3]

    def test_left_alignment_starts_the_line_at_its_position(self) -> None:
        xs = np.nonzero(self.text(align="left", position=[0.2, 0.5]) > 0.3)[1]
        self.assertAlmostEqual(xs.min() / W, 0.2, delta=0.02)

    def test_lines_stack_and_space(self) -> None:
        one = np.nonzero(self.text(text="A") > 0.3)[0]
        three = np.nonzero(self.text(text="A\\nB\\nC", line_spacing=10) > 0.3)[0]
        self.assertGreater(three.max() - three.min(), 2.5 * (one.max() - one.min()))

    def test_a_hollow_outline_covers_less_than_the_letters(self) -> None:
        filled, hollow = self.text(outline=4, hollow=False), self.text(outline=4, hollow=True)
        self.assertGreater(float(hollow.sum()), 0.0)
        self.assertLess(float(hollow.sum()), float(filled.sum()))


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class ConformanceTests(unittest.TestCase):
    def test_every_animation_runs_on_gl_as_the_reference_draws_it(self) -> None:
        from cine_toaster.compositing.gl import renderer_for

        for effect in BUILDERS:
            with self.subTest(effect=effect):
                title = {"engine": "graph", "effect": effect,
                         "params": {**BASE_PARAMS, "text": "TITLE", "subtitle": "sub", "size": 40, "enter_at": 0.0,
                                    "fade_in": 0.3, "ignite": 0.1}}
                graph = graph_for(title, 1.0, FPS)
                renderer = renderer_for(graph)
                self.assertIsNotNone(renderer, f"{effect} falls back to the reference")
                exact = evaluate(graph, {"picture": black()}, frames=8, size=(W, H), fps=FPS)
                fast = np.stack(list(renderer.evaluate(graph, {"picture": black()}, frames=8, size=(W, H), fps=FPS,
                                                       stream=True)))
                self.assertLess(float(np.abs(exact - fast).mean()), 0.01)


class ExpandTests(unittest.TestCase):
    def test_a_bare_string_is_still_a_card(self) -> None:
        title, problem = expand("Hello", {item["id"]: item for item in list_titles()})
        self.assertEqual((problem, title["id"], title["engine"]), ("", "card", "graph"))


if __name__ == "__main__":
    unittest.main()
