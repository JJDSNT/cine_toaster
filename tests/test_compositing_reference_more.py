"""The reference's second slice (CT-0071): warps, depth, colour, filters, time, tracking, beats, identity."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from cine_toaster.compositing.identity import identities
from cine_toaster.compositing.reference import evaluate

W, H, FPS, FRAMES = 64, 36, 24, 12


def solid(r: float, g: float, b: float, a: float = 1.0) -> np.ndarray:
    return np.broadcast_to(np.asarray([r * a, g * a, b * a, a], np.float32), (H, W, 4)).copy()


def box(x0: int, y0: int, x1: int, y1: int, colour=(1, 1, 1)) -> np.ndarray:
    picture = np.zeros((H, W, 4), np.float32)
    picture[y0:y1, x0:x1, :3] = colour
    picture[y0:y1, x0:x1, 3] = 1.0
    return picture


def one(nodes: dict, ports: dict, frames: int = 1, **inputs) -> np.ndarray:
    return evaluate({"ports": ports, "nodes": nodes, "output": "out"}, inputs, frames=frames, size=(W, H), fps=FPS)


class WarpTests(unittest.TestCase):
    def test_a_turn_in_perspective_narrows_the_far_edge(self) -> None:
        out = one({"out": {"op": "warp.transform", "in": "a", "rotate": [0, 40, 0], "perspective": 40}},
                  {"a": "picture"}, a=solid(1, 1, 1))[0, ..., 3]
        left, right = out[:, 2].sum(), out[:, -3].sum()
        self.assertNotAlmostEqual(left, right, delta=2)  # one side is farther: shorter on screen

    def test_a_corner_pin_puts_the_picture_where_its_corners_say(self) -> None:
        corners = [[0.5, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]]
        out = one({"out": {"op": "warp.corner_pin", "in": "a", "corners": corners}}, {"a": "picture"},
                  a=solid(1, 1, 1))[0, ..., 3]
        self.assertLess(out[18, 10], 0.01)
        self.assertGreater(out[18, 50], 0.99)

    def test_a_displacement_moves_pixels_and_a_swirl_keeps_its_centre(self) -> None:
        field = np.full((H, W), 1.0, np.float32)  # 0.5 above the neutral grey: a push to the right
        moved = one({"out": {"op": "warp.displace", "in": "a", "map": "f", "strength": 0.2}},
                    {"a": "picture", "f": "signal"}, a=box(10, 0, 20, H), f=field)[0, ..., 3]
        self.assertGreater(moved[18, 18], 0.9)  # the box, 10 to 20, now 6.4 pixels to the right
        self.assertLess(moved[18, 12], 0.01)
        swirled = one({"out": {"op": "warp.procedural", "in": "a", "kind": "swirl", "amount": 3}}, {"a": "picture"},
                      a=box(30, 16, 34, 20))[0, ..., 3]
        self.assertGreater(swirled[18, 32], 0.9)


class DepthTests(unittest.TestCase):
    def test_the_nearer_picture_hides_the_farther_one_pixel_by_pixel(self) -> None:
        near_left = np.where(np.arange(W) < W // 2, 1.0, 5.0).astype(np.float32)[None].repeat(H, 0)
        out = one({"out": {"op": "merge.depth", "pictures": ["red", "blue"], "depths": ["d1", "d2"]}},
                  {"red": "picture", "blue": "picture", "d1": "signal", "d2": "signal"},
                  red=solid(1, 0, 0), blue=solid(0, 0, 1), d1=near_left, d2=np.full((H, W), 3.0, np.float32))[0]
        self.assertGreater(out[18, 5, 0], 0.99)   # red is nearer on the left
        self.assertGreater(out[18, 60, 2], 0.99)  # blue is nearer on the right

    def test_relative_depth_is_aligned_to_a_metric_one(self) -> None:
        metric = np.linspace(2, 10, W, dtype=np.float32)[None].repeat(H, 0)
        relative = (metric - 1.0) / 4.0  # unknown scale and shift
        out = evaluate({"ports": {"r": "signal", "m": "signal"},
                        "nodes": {"aligned": {"op": "signal.align_depth", "signal": "r", "reference": "m"},
                                  "out": {"op": "merge.channels", "red": "aligned"}},
                        "output": "out"}, {"r": relative, "m": metric}, frames=1, size=(W, H), fps=FPS)
        self.assertLess(float(np.abs(out[0, ..., 0] - metric).max()), 1e-3)  # scale and shift recovered


class ColourAndFilterTests(unittest.TestCase):
    def test_posterise_cuts_to_levels_and_a_third_turn_swaps_the_primaries(self) -> None:
        ramp = np.dstack([np.linspace(0, 1, W, dtype=np.float32)[None].repeat(H, 0)] * 3 + [np.ones((H, W), np.float32)])
        out = one({"out": {"op": "colour.posterise", "in": "a", "levels": 3}}, {"a": "picture"}, a=ramp)[0]
        from cine_toaster.compositing.reference import encode_srgb

        self.assertLessEqual(len(np.unique(np.round(encode_srgb(out[..., 0]), 3))), 3)
        turned = evaluate({"ports": {"a": "picture"}, "nodes": {"out": {"op": "colour.cycle", "in": "a", "speed": 240}},
                           "output": "out"}, {"a": solid(1, 0, 0)}, frames=1, size=(W, H), fps=1)[0, 0, 0]
        self.assertGreater(turned[1], 0.9)  # half a second at 240 degrees per second: red becomes green

    def test_a_matte_grows_and_shrinks(self) -> None:
        square = box(28, 14, 36, 22)
        grown = one({"m": {"op": "filter.morphology", "in": "a", "operation": "dilate", "radius": 2},
                     "out": {"op": "merge.over", "front": "white", "back": "black", "matte": "m"}},
                    {"a": "picture", "white": "picture", "black": "picture"},
                    a=square, white=solid(1, 1, 1), black=solid(0, 0, 0))[0, ..., 0]
        self.assertGreater(grown.sum(), square[..., 3].sum())


class TimeTests(unittest.TestCase):
    def moving(self) -> np.ndarray:
        return np.stack([box(4 * frame, 10, 4 * frame + 6, 20) for frame in range(FRAMES)])

    def test_an_offset_shows_an_earlier_frame_and_echoes_trail_behind(self) -> None:
        offset = one({"out": {"op": "time.offset", "in": "a", "frames": 3}}, {"a": "picture"}, FRAMES, a=self.moving())
        self.assertGreater(offset[6, 15, 4 * 3 + 2, 3], 0.99)  # frame 6 shows frame 3
        echoed = one({"out": {"op": "time.echo", "in": "a", "count": 3, "spacing": 1, "decay": 0.5}}, {"a": "picture"},
                     FRAMES, a=self.moving())
        self.assertGreater(echoed[8, 15, 4 * 6 + 2, 3], 0.1)  # an echo of frame 6 is still there at frame 8

    def test_a_point_is_tracked_on_a_moving_picture(self) -> None:
        textured = np.stack([np.roll(np.random.default_rng(1).uniform(0, 1, (H, W, 1)).repeat(4, -1).astype(np.float32),
                                     2 * frame, axis=1) for frame in range(FRAMES)])
        textured[..., 3] = 1.0
        out = one({"t": {"op": "track.measure", "in": "a", "kind": "point", "region": [0.3, 0.3, 0.7, 0.7]},
                   "x": {"op": "curve.from_track", "track": "t", "field": "x"},
                   "out": {"op": "warp.transform", "in": "a", "translate": [0, 0]}}, {"a": "picture"}, FRAMES,
                  a=textured)
        self.assertEqual(out.shape[0], FRAMES)
        from cine_toaster.compositing.tracking import measure

        track = measure(textured, "point", [0.3, 0.3, 0.7, 0.7], "Linear Rec.709 (sRGB)")
        moved = track["frames"][-1]["points"][0][0] - track["frames"][0]["points"][0][0]
        self.assertAlmostEqual(moved * W, 2 * (FRAMES - 1), delta=1.5)


class BeatTests(unittest.TestCase):
    def test_a_beat_curve_peaks_on_its_beats(self) -> None:
        out = evaluate({"ports": {"a": "picture"},
                        "nodes": {"pulse": {"op": "curve.beats", "attack": 0.02, "decay": 0.2, "low": 0.0, "high": 1.0},
                                  "out": {"op": "merge.over", "front": "a", "back": "a", "mix": {"curve": "pulse"}}},
                        "output": "out"}, {"a": solid(1, 1, 1, 0.5)}, frames=24, size=(W, H), fps=24, beats=[0.5])
        alpha = out[:, 0, 0, 3]
        self.assertEqual(int(np.argmax(alpha)), 12)  # the frame on the beat


class IdentityTests(unittest.TestCase):
    def graph(self, radius: float) -> dict:
        return {"ports": {"a": "picture"},
                "nodes": {"blurred": {"op": "filter.blur", "in": "a", "radius": radius},
                          "graded": {"op": "colour.grade", "in": "a", "gain": 2},
                          "out": {"op": "merge.mix", "a": "blurred", "b": "graded", "by": "graded"}}, "output": "out"}

    def test_a_change_moves_its_node_and_what_depends_on_it_and_nothing_else(self) -> None:
        context = {"fps": 24, "size": [64, 36], "frames": 12, "working": "Linear Rec.709 (sRGB)", "ocio": "x"}
        before = identities(self.graph(2), {"a": "A"}, context=context)
        after = identities(self.graph(3), {"a": "A"}, context=context)
        self.assertNotEqual(before["blurred"], after["blurred"])
        self.assertNotEqual(before["out"], after["out"])
        self.assertEqual(before["graded"], after["graded"])
        self.assertEqual(before, identities(self.graph(2), {"a": "A"}, context=context))
        self.assertNotEqual(before["graded"], identities(self.graph(2), {"a": "A"}, context={**context, "fps": 25})["graded"])

    def test_a_file_is_known_by_its_content(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            lut = Path(raw) / "look.cube"
            graph = {"ports": {"a": "picture"}, "nodes": {"out": {"op": "colour.lut", "in": "a", "file": str(lut)}},
                     "output": "out"}
            lut.write_text("LUT_3D_SIZE 2\n" + "0 0 0\n" * 8)
            first = identities(graph, {"a": "A"}, context={})["out"]
            lut.write_text("LUT_3D_SIZE 2\n" + "1 1 1\n" * 8)
            self.assertNotEqual(first, identities(graph, {"a": "A"}, context={})["out"])


if __name__ == "__main__":
    unittest.main()


class CacheTests(unittest.TestCase):
    def test_a_result_is_found_by_its_identity_and_a_change_misses(self) -> None:
        from cine_toaster.compositing.reference import render

        graph = {"ports": {"a": "picture"}, "nodes": {"out": {"op": "filter.blur", "in": "a", "radius": 2}},
                 "output": "out"}
        with tempfile.TemporaryDirectory() as folder:
            options = {"frames": 2, "size": (W, H), "fps": FPS, "cache": Path(folder)}
            first, identity, hit = render(graph, {"a": box(10, 10, 20, 20)}, **options)
            again, same, hit_again = render(graph, {"a": box(10, 10, 20, 20)}, **options)
            self.assertEqual((hit, hit_again, same), (False, True, identity))
            self.assertLess(float(np.abs(first - again).max()), 1e-3)  # kept in half floats
            graph["nodes"]["out"]["radius"] = 3
            self.assertFalse(render(graph, {"a": box(10, 10, 20, 20)}, **options)[2])
            self.assertFalse(render(graph, {"a": box(11, 10, 20, 20)}, **{**options})[2])


class ExamplesEvaluateTests(unittest.TestCase):
    """Every example graph the reference can run, it runs: valid on paper and computable."""

    def test_every_example_within_the_reference_evaluates(self) -> None:
        import yaml

        from cine_toaster.compositing.reference import IMPLEMENTED

        folder = Path(__file__).parents[1] / "ai-context" / "specs" / "SPEC-0012-examples"
        rng = np.random.default_rng(3)
        ran = []
        for path in sorted(folder.glob("*.yaml")):
            graph = yaml.safe_load(path.read_text())
            if any(node["op"] not in IMPLEMENTED for node in graph["nodes"].values()):
                continue
            inputs = {}
            textured = lambda: np.dstack([rng.uniform(0, 1, (H, W)).astype(np.float32)] * 3  # noqa: E731
                                         + [np.ones((H, W), np.float32)])
            for name, kind in (graph.get("ports") or {}).items():
                if kind == "picture":
                    inputs[name] = textured()
            for name, node in graph["nodes"].items():
                if node["op"] == "generate.source":
                    inputs[name] = textured()
            with self.subTest(example=path.name):
                out = evaluate(graph, inputs, frames=4, size=(W, H), fps=FPS, beats=[0.05, 0.1])
                self.assertEqual(out.shape, (4, H, W, 4))
                self.assertTrue(np.isfinite(out).all())
                ran.append(path.stem)
        self.assertGreaterEqual(len(ran), 14, ran)


class IncrementalTests(unittest.TestCase):
    """Made frame by frame, the result is the same as made whole; memory follows the graph, not the length."""

    def graph(self) -> dict:
        return {"ports": {"a": "picture", "b": "picture"},
                "nodes": {"soft": {"op": "filter.blur", "in": "a", "radius": 1.5},
                          "echo": {"op": "time.echo", "in": "soft", "count": 3, "spacing": 2, "decay": 0.5},
                          "late": {"op": "time.offset", "in": "b", "frames": 2},
                          "out": {"op": "merge.over", "front": "echo", "back": "late"}}, "output": "out"}

    def inputs(self, frames: int) -> dict:
        moving = np.stack([box((2 * frame) % (W - 6), 10, (2 * frame) % (W - 6) + 6, 20, (1, 0.5, 0.2))
                           for frame in range(frames)])
        moving[..., :3] *= 0.7  # premultiplied by a partial alpha
        moving[..., 3] *= 0.7
        return {"a": moving, "b": np.stack([solid(0.1, 0.2, frame / frames) for frame in range(frames)])}

    def test_streamed_and_whole_agree_exactly(self) -> None:
        options = {"frames": 30, "size": (W, H), "fps": FPS}
        whole = evaluate(self.graph(), self.inputs(30), **options)
        streamed = np.stack(list(evaluate(self.graph(), self.inputs(30), stream=True, **options)))
        self.assertEqual(float(np.abs(whole - streamed).max()), 0.0)

    def test_what_is_kept_does_not_grow_with_the_length(self) -> None:
        kept = []
        for frames in (20, 120):
            stats: dict = {}
            for _ in evaluate(self.graph(), self.inputs(frames), frames=frames, size=(W, H), fps=FPS, stream=True,
                              stats=stats):
                pass
            kept.append(stats["most_kept"])
        self.assertEqual(kept[0], kept[1])
        # Only the echo's input is kept back (six frames and the present); the other nodes, the present only.
        self.assertLessEqual(kept[1], (6 + 1) + 3 + 2)

    def test_a_cached_result_is_the_streamed_one_in_half_floats(self) -> None:
        from cine_toaster.compositing.reference import render

        with tempfile.TemporaryDirectory() as folder:
            options = {"frames": 12, "size": (W, H), "fps": FPS, "cache": Path(folder)}
            made, identity, _ = render(self.graph(), self.inputs(12), **options)
            found, same, hit = render(self.graph(), self.inputs(12), **options)
            direct = evaluate(self.graph(), self.inputs(12), frames=12, size=(W, H), fps=FPS)
            self.assertTrue(hit and same == identity)
            self.assertLess(float(np.abs(np.asarray(found, np.float32) - direct).max()), 2e-3)


class BudgetTests(unittest.TestCase):
    def test_a_budget_bounds_the_bytes_held_and_costs_recomputation_not_correctness(self) -> None:
        test = IncrementalTests()
        graph, inputs = test.graph(), test.inputs(40)
        options = {"frames": 40, "size": (W, H), "fps": FPS}
        free: dict = {}
        unbounded = np.stack(list(evaluate(graph, inputs, stream=True, stats=free, **options)))
        frame_bytes = W * H * 4 * 4
        tight: dict = {}
        bounded = np.stack(list(evaluate(graph, inputs, stream=True, stats=tight, budget=6 * frame_bytes, **options)))
        self.assertEqual(float(np.abs(unbounded - bounded).max()), 0.0)
        self.assertLessEqual(tight["most_kept_bytes"], 6 * frame_bytes + frame_bytes)  # the frame being made may add one
        self.assertLess(tight["most_kept_bytes"], free["most_kept_bytes"])
        self.assertGreater(tight["recomputed"], free["recomputed"])

    def test_the_bytes_held_do_not_grow_with_the_length(self) -> None:
        test = IncrementalTests()
        held = []
        for frames in (20, 160):
            stats: dict = {}
            for _ in evaluate(test.graph(), test.inputs(frames), frames=frames, size=(W, H), fps=FPS, stream=True,
                              stats=stats):
                pass
            held.append(stats["most_kept_bytes"])
        self.assertEqual(held[0], held[1])


class RetentionTests(unittest.TestCase):
    """Retention follows each result's consumers: the largest reach any of them needs, and only for that result."""

    def moving(self, frames: int) -> np.ndarray:
        return np.stack([box((3 * frame) % (W - 6), 8, (3 * frame) % (W - 6) + 6, 28, (0.9, 0.6, 0.3))
                         for frame in range(frames)])

    def test_two_consumers_of_one_result_keep_it_as_long_as_the_farther_needs(self) -> None:
        from cine_toaster.compositing.reference import node_windows

        graph = {"ports": {"a": "picture"},
                 "nodes": {"soft": {"op": "filter.blur", "in": "a", "radius": 1},
                           "near": {"op": "time.offset", "in": "soft", "frames": 2},
                           "far": {"op": "time.echo", "in": "soft", "count": 3, "spacing": 3},
                           "both": {"op": "merge.over", "front": "near", "back": "far"},
                           "graded": {"op": "colour.grade", "in": "a", "gain": 1.5},
                           "out": {"op": "merge.blend", "a": "both", "b": "graded", "mode": "screen"}},
                 "output": "out"}
        self.assertEqual(node_windows(graph), {"soft": 9})  # the echo's nine, not the offset's two; nobody else
        options = {"frames": 40, "size": (W, H), "fps": FPS}
        whole = evaluate(graph, {"a": self.moving(40)}, **options)
        stats: dict = {}
        streamed = np.stack(list(evaluate(graph, {"a": self.moving(40)}, stream=True, stats=stats, **options)))
        self.assertEqual(float(np.abs(whole - streamed).max()), 0.0)
        self.assertEqual(stats["recomputed"], 0)
        self.assertLessEqual(stats["most_kept"], (9 + 1) + 5 + 1)  # soft's past and present; the rest, the present

    def test_reading_out_of_order_recomputes_what_was_let_go_and_stays_right(self) -> None:
        reverse = {"ports": {"a": "picture"},
                   "nodes": {"soft": {"op": "filter.blur", "in": "a", "radius": 1},
                             "back": {"op": "curve.keys", "keys": [[0, 1.6], [1.6, 0]]},
                             "out": {"op": "time.remap", "in": "soft", "map": {"curve": "back"}}}, "output": "out"}
        options = {"frames": 40, "size": (W, H), "fps": FPS}
        stats: dict = {}
        streamed = np.stack(list(evaluate(reverse, {"a": self.moving(40)}, stream=True, stats=stats, **options)))
        self.assertGreater(float(streamed[0, ..., 3].sum()), 0)  # the first frame shows the clip's end
        expected = evaluate({"ports": {"a": "picture"}, "nodes": {"out": {"op": "filter.blur", "in": "a",
                                                                          "radius": 1}}, "output": "out"},
                            {"a": self.moving(40)}, **options)
        self.assertEqual(float(np.abs(streamed[0] - expected[int(round(1.6 * FPS - 0.5)) - 1]).max()) < 1e-6
                         or float(np.abs(streamed[0] - expected[int(round(1.6 * FPS - 0.5))]).max()) < 1e-6, True)


class EaseTests(unittest.TestCase):
    def test_a_bezier_ease_matches_its_named_twin_and_unknown_eases_are_refused(self) -> None:
        from cine_toaster.compositing.reference import cubic_bezier, keys_curve
        from cine_toaster.errors import ValidationError

        linear = cubic_bezier(0, 0, 1, 1)
        self.assertAlmostEqual(linear(0.3), 0.3, places=4)
        css_ease_in_out = cubic_bezier(0.42, 0, 0.58, 1)
        self.assertAlmostEqual(css_ease_in_out(0.5), 0.5, places=4)
        self.assertLess(css_ease_in_out(0.2), 0.2)  # slow out of the start
        overshoot = keys_curve([{"t": 0, "value": 0, "ease": [0.3, 1.6, 0.6, 1.0]}, [1, 10]])
        self.assertGreater(float(max(overshoot(x / 50) for x in range(51))), 10.0)  # a back-out passes the target
        with self.assertRaises(ValidationError):
            keys_curve([{"t": 0, "value": 0, "ease": "bounce"}, [1, 1]])
