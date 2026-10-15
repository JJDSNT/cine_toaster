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


def styled(style: dict, frames: int = 1, effect: str = "fade", **params) -> np.ndarray:
    from cine_toaster.compositing.title_graphs import graph_for
    from cine_toaster.titles import BASE_PARAMS

    black = np.zeros((H, W, 4), np.float32)
    black[..., 3] = 1.0
    title = {"engine": "graph", "effect": effect,
             "params": {**BASE_PARAMS, "text": "HOME", "size": 120, "fade_in": 0.01, "style": style, **params}}
    return evaluate(graph_for(title, 2.0, FPS), {"picture": black}, frames=frames, size=(W, H), fps=FPS)


class StyleTests(unittest.TestCase):
    """C6b stage B (CT-0078): a title's look, compiled into the graph's own nodes."""

    def test_a_style_that_cannot_be_drawn_is_refused(self) -> None:
        from cine_toaster.compositing.title_graphs import style_problem
        from cine_toaster.titles import expand

        self.assertIn("sparkle", style_problem({"sparkle": {}}))
        self.assertIn("fills with", style_problem({"fill": {"plasma": {}}}))
        catalog = {item["id"]: item for item in list_titles()}
        title, problem = expand({"id": "card", "text": "X", "style": {"sparkle": {}}}, catalog)
        self.assertIsNone(title)
        self.assertIn("style", problem)

    def test_a_fill_runs_across_the_letters_not_the_frame(self) -> None:
        out = styled({"fill": {"gradient": {"colours": ["#FF0000", "#0000FF"], "angle": 90}}})[-1]
        letters = out[..., :3].max(axis=-1) > 0.1  # over black: the letters are what has colour
        rows = np.nonzero(letters.max(axis=1))[0]
        top, bottom = out[rows.min() + 2], out[rows.max() - 2]
        lit_top, lit_bottom = top[letters[rows.min() + 2]], bottom[letters[rows.max() - 2]]
        self.assertGreater(float(lit_top[:, 0].mean()), float(lit_top[:, 2].mean()))  # red at the letters' top
        self.assertGreater(float(lit_bottom[:, 2].mean()), float(lit_bottom[:, 0].mean()))  # blue at their foot

    def test_an_outline_rings_the_letters_in_its_colour(self) -> None:
        plain = styled({"fill": {"gradient": {"colours": ["#FFFFFF", "#FFFFFF"]}}})[-1]
        ringed = styled({"fill": {"gradient": {"colours": ["#FFFFFF", "#FFFFFF"]}},
                         "outline": {"width": 12, "colour": "#00FF00"}})[-1]
        self.assertGreater(float((ringed[..., 1] > 0.3).sum()), float((plain[..., 1] > 0.3).sum()) * 1.1)
        rim = (ringed[..., 1] > 0.5) & (ringed[..., 0] < 0.1)  # green and not white: the ring
        self.assertGreater(int(rim.sum()), 50)

    def test_a_shadow_falls_below_and_to_the_right(self) -> None:
        out = styled({"shadow": {"offset": [24, 24], "blur": 0, "opacity": 1.0, "colour": "#FF00FF"}})[-1]
        shadow = (out[..., 0] > 0.3) & (out[..., 1] < 0.1)  # magenta where the letters are not
        ys, xs = np.nonzero(shadow)
        letters = out[..., 1] > 0.5
        ly, lx = np.nonzero(letters)
        self.assertGreater(ys.mean(), ly.mean())
        self.assertGreater(xs.mean(), lx.mean())

    def test_a_bevel_lights_the_edges_facing_the_light(self) -> None:
        flat = styled({"fill": {"gradient": {"colours": ["#808080", "#808080"]}}})[-1]
        raised = styled({"fill": {"gradient": {"colours": ["#808080", "#808080"]}},
                         "bevel": {"radius": 16, "depth": 2.0, "angle": 135.0}})[-1]
        change = raised[..., 0] - flat[..., 0]
        letters = flat[..., 3] > 0.5
        ys, xs = np.nonzero(letters)
        upper_left = change[letters & (np.arange(H)[:, None] < ys.mean()) & (np.arange(W)[None, :] < xs.mean())]
        lower_right = change[letters & (np.arange(H)[:, None] > ys.mean()) & (np.arange(W)[None, :] > xs.mean())]
        self.assertGreater(float(upper_left.max()), 0.05)  # some faces lit
        self.assertLess(float(lower_right.min()), -0.02)  # some darkened

    def test_a_style_follows_the_letters_animation(self) -> None:
        drop = {"keys": [{"t": 0.0, "opacity": 0.0}, {"t": 0.3, "opacity": 1.0}], "stagger": 0.15}
        frames = styled({"fill": {"gradient": {"colours": ["#FF0000", "#FFFF00"]}}, "shadow": {"offset": [6, 6]}},
                        frames=12, effect="letters", letters=drop, enter_at=0.0)
        seen = [float((frame[..., 0] > 0.3).mean()) for frame in frames]
        self.assertTrue(all(b >= a - 1e-4 for a, b in zip(seen, seen[1:])))
        self.assertGreater(seen[-1], seen[2] * 1.5)

    def test_the_styled_items_are_in_the_catalog(self) -> None:
        catalog = {item["id"]: item for item in list_titles()}
        for item in ("chrome", "colour-font"):
            self.assertIn("filter.bevel", catalog[item]["primitives"])
        self.assertIn("colour.cycle", catalog["colour-font"]["primitives"])


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class StyleConformanceTests(unittest.TestCase):
    def test_gl_draws_styled_titles_as_the_reference_does(self) -> None:
        from cine_toaster.compositing.gl import renderer_for
        from cine_toaster.compositing.title_graphs import graph_for
        from cine_toaster.titles import list_titles as titles

        black = np.zeros((H, W, 4), np.float32)
        black[..., 3] = 1.0
        for item in [item for item in titles() if item["id"] in ("chrome", "colour-font")]:
            with self.subTest(item=item["id"]):
                graph = graph_for({**item, "params": {**item["params"], "text": "HOME", "fade_in": 0.1}}, 1.0, FPS)
                renderer = renderer_for(graph)
                self.assertIsNotNone(renderer)
                exact = evaluate(graph, {"picture": black}, frames=6, size=(W, H), fps=FPS)
                fast = np.stack(list(renderer.evaluate(graph, {"picture": black}, frames=6, size=(W, H), fps=FPS,
                                                       stream=True)))
                self.assertLess(float(np.abs(exact - fast).mean()), 0.005)

    def test_gradients_with_many_stops_on_gl(self) -> None:
        from cine_toaster.compositing.gl import renderer_for

        stops = [[1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 1], [1, 1, 0, 1]]
        for kind in ("linear", "circle", "conic"):
            graph = {"ports": {}, "output": "g", "nodes": {"g": {"op": "generate.gradient", "kind": kind,
                                                                  "colours": stops}}}
            exact = evaluate(graph, {}, frames=1, size=(W, H), fps=FPS)[0]
            fast = next(iter(renderer_for(graph).evaluate(graph, {}, frames=1, size=(W, H), fps=FPS, stream=True)))
            self.assertLess(float(np.abs(exact - fast).max()), 1e-4, kind)


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
