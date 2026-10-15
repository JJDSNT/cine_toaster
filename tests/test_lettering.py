"""C6b (CT-0078): animated lettering -- letters with their own time, drawn by generate.text in both renderers."""

from __future__ import annotations

import unittest

import numpy as np

from cine_toaster.compositing.gl import gl_unavailable_reason
from cine_toaster.compositing.reference import evaluate, letter_ranks
from cine_toaster.compositing.schema import validate
from cine_toaster.titles import list_titles

W, H, FPS = 320, 180, 12
DROP = {"keys": [{"t": 0.0, "offset": [0, -60], "rotate": -30, "opacity": 0.0, "ease": "out"},
                 {"t": 0.4, "offset": [0, 0], "rotate": 0, "opacity": 1.0}], "stagger": 0.1}


def text(frames: int = 1, **more) -> np.ndarray:
    node = {"op": "generate.text", "text": "ABCDEF", "size": 50, "colour": [1, 1, 1, 1], **more}
    return evaluate({"ports": {}, "nodes": {"t": node}, "output": "t"}, {}, frames=frames, size=(W, H), fps=FPS)


def columns(frame: np.ndarray) -> np.ndarray:
    return np.nonzero(frame[..., 3].max(axis=0) > 0.3)[0]


class LetteringTests(unittest.TestCase):
    def test_letters_land_where_the_block_puts_them(self) -> None:
        """Once every letter has played its keys, the line is the text drawn whole: no letter is out of place."""

        settled = text(frames=24, letters=DROP)[-1]  # 1.96 s: the last letter landed at 0.5 + 0.4 s
        block = text()[0]
        self.assertLess(float(np.abs(settled[..., 3] - block[..., 3]).mean()), 0.01)
        for align in ("left", "right"):
            with self.subTest(align=align):
                moved = text(frames=24, letters=DROP, align=align, position=[0.5, 0.5])[-1]
                still = text(align=align, position=[0.5, 0.5])[0]
                self.assertLess(float(np.abs(moved[..., 3] - still[..., 3]).mean()), 0.01)

    def test_each_letter_has_its_own_time(self) -> None:
        frames = text(frames=12, letters=DROP)
        early = frames[3]  # 0.29 s: the first letters are in, the last not yet
        block = text()[0]
        left, right = block[:, : W // 2, 3].sum(), block[:, W // 2:, 3].sum()
        self.assertGreater(float(early[:, : W // 2, 3].sum()) / left, float(early[:, W // 2:, 3].sum()) / right + 0.3)

    def test_orders(self) -> None:
        self.assertEqual(letter_ranks("ABCD", "forward"), [0, 1, 2, 3])
        self.assertEqual(letter_ranks("ABCD", "backward"), [3, 2, 1, 0])
        self.assertEqual(letter_ranks("ABCDE", "centre"), [2, 1, 0, 1, 2])
        self.assertEqual(letter_ranks("AB CD", "forward"), [0, 1, 0, 2, 3])  # a space takes no place
        self.assertEqual(sorted(letter_ranks("ABCD", "random", 3)), [0, 1, 2, 3])

    def test_a_wave_runs_along_the_line(self) -> None:
        wave = {"wave": {"amplitude": 20.0, "frequency": 0.5, "phase": 0.25}}
        frame = text(letters=wave)[0]
        heights = []
        for column in np.array_split(columns(frame), 6):  # roughly a letter each
            rows = np.nonzero(frame[:, column, 3].max(axis=1) > 0.3)[0]
            if len(rows):
                heights.append(rows.mean())
        self.assertGreater(max(heights) - min(heights), 8)  # the letters are not on one line

    def test_a_mistaken_animator_is_refused_before_anything_is_drawn(self) -> None:
        def problems(letters):
            node = {"op": "generate.text", "text": "A", "letters": letters}
            return [message for _, message in validate({"ports": {}, "nodes": {"t": node}, "output": "t"})]

        self.assertIn("spin", problems({"keys": [{"t": 0, "spin": 2}]})[0])
        self.assertIn("orders letters", problems({"keys": [{"t": 0}], "order": "sideways"})[0])
        self.assertIn("nothing would move", problems({"stagger": 0.1})[0])
        self.assertEqual(problems(DROP), [])

    def test_the_lettering_titles_are_in_the_catalog(self) -> None:
        catalog = {item["id"]: item for item in list_titles()}
        for item in ("type-drop", "type-wave", "type-pop"):
            self.assertEqual((catalog[item]["engine"], catalog[item]["effect"]), ("graph", "letters"))


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class LetteringConformanceTests(unittest.TestCase):
    def test_gl_draws_the_letters_the_reference_draws(self) -> None:
        from cine_toaster.compositing.gl import renderer_for

        node = {"op": "generate.text", "text": "ABCDEF", "size": 50, "colour": [1, 1, 1, 1], "letters": DROP}
        graph = {"ports": {}, "nodes": {"t": node}, "output": "t"}
        exact = evaluate(graph, {}, frames=8, size=(W, H), fps=FPS)
        fast = np.stack(list(renderer_for(graph).evaluate(graph, {}, frames=8, size=(W, H), fps=FPS, stream=True)))
        self.assertLess(float(np.abs(exact - fast).max()), 1e-5)


if __name__ == "__main__":
    unittest.main()
