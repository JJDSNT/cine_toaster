"""C7 step 1 (CT-0080): what the time operations mean -- which source instant, then how it is pictured."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cine_toaster.compositing.reference import evaluate, reach
from cine_toaster.compositing.schema import validate
from cine_toaster.compositing.semantics import remap_samples

FPS = 10


def numbered(count: int) -> np.ndarray:
    """A clip whose every frame carries its own number in red (in hundredths), opaque."""

    frames = np.zeros((count, 2, 2, 4), np.float32)
    frames[..., 3] = 1.0
    for index in range(count):
        frames[index, ..., 0] = index / 100
    return frames


def remap(keys: list, frames: int = 10, source: int = 20, **more) -> list[float]:
    graph = {"ports": {"a": "picture"}, "output": "out",
             "nodes": {"m": {"op": "curve.keys", "keys": keys},
                       "out": {"op": "time.remap", "in": "a", "map": {"curve": "m"}, **more}}}
    assert validate(graph) == [], validate(graph)
    out = evaluate(graph, {"a": numbered(source)}, frames=frames, size=(2, 2), fps=FPS)
    return [round(float(frame[0, 0, 0]) * 100, 4) for frame in out]


class SamplingTests(unittest.TestCase):
    def test_nearest_is_the_frame_that_contains_the_instant(self) -> None:
        self.assertEqual(remap_samples(0.05, FPS), [(0, 1.0)])  # frame 0's centre
        self.assertEqual(remap_samples(0.0999, FPS), [(0, 1.0)])  # still inside frame 0
        self.assertEqual(remap_samples(0.1, FPS), [(1, 1.0)])  # frame 1 has started

    def test_blend_weighs_the_two_frames_either_side(self) -> None:
        self.assertEqual(remap_samples(0.15, FPS, "blend"), [(1, 1.0)])  # on frame 1's centre: frame 1 alone
        (first, a), (second, b) = remap_samples(0.175, FPS, "blend")
        self.assertEqual((first, second), (1, 2))
        self.assertAlmostEqual(a, 0.75)
        self.assertAlmostEqual(b, 0.25)
        with self.assertRaises(ValueError):
            remap_samples(0.1, FPS, "optical")  # not yet a name


class RemapTests(unittest.TestCase):
    def test_a_speed_up_reads_past_the_shot_without_stutter(self) -> None:
        """2x over ten frames reads twenty: every other source frame, evenly, to the end -- before, it froze on
        frame 9 half way and its cadence stuttered (1, 3, 4, 6, 8)."""

        self.assertEqual(remap([[0, 0], [1, 2]]), [1, 3, 5, 7, 9, 11, 13, 15, 17, 19])

    def test_slow_motion_repeats_or_blends_as_asked(self) -> None:
        self.assertEqual(remap([[0, 0], [1, 0.5]]), [0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
        blended = remap([[0, 0], [1, 0.5]], interpolation="blend")
        self.assertEqual(blended, [0, 0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75, 4.25])

    def test_the_interpolation_does_not_change_which_instant(self) -> None:
        """At speed 1 every output frame's centre is a source frame's centre: both interpolations agree."""

        self.assertEqual(remap([[0, 0], [1, 1]]), list(range(10)))
        self.assertEqual(remap([[0, 0], [1, 1]], interpolation="blend"), list(range(10)))

    def test_reverse_and_freeze(self) -> None:
        self.assertEqual(remap([[0, 1], [1, 0]]), [9, 8, 7, 6, 5, 4, 3, 2, 1, 0])
        self.assertEqual(remap([[0, 0.45], [1, 0.45]]), [4] * 10)

    def test_a_ramp_never_steps_back(self) -> None:
        ramp = remap([{"t": 0, "value": 0, "ease": "in"}, {"t": 1, "value": 1.8}])
        self.assertEqual(ramp, sorted(ramp))
        self.assertGreater(ramp[-1] - ramp[-2], ramp[1] - ramp[0])  # faster at the end

    def test_past_the_source_holds_its_last_frame(self) -> None:
        self.assertEqual(remap([[0, 0], [1, 3]], source=20)[-1], 19)


class ReachTests(unittest.TestCase):
    def graph(self, keys: list, **more) -> dict:
        return {"ports": {"a": "picture"}, "output": "out",
                "nodes": {"m": {"op": "curve.keys", "keys": keys},
                          "out": {"op": "time.remap", "in": "a", "map": {"curve": "m"}, **more}}}

    def test_a_graph_reaches_as_far_as_its_remaps_read(self) -> None:
        self.assertEqual(reach(self.graph([[0, 0], [1, 2]]), 10, FPS), 20)
        self.assertEqual(reach(self.graph([[0, 0], [1, 0.5]]), 10, FPS), 10)  # slower: the shot's own
        self.assertEqual(reach(self.graph([[0, 0], [1, 1]], interpolation="blend"), 10, FPS), 10)
        offset = {"ports": {"a": "picture"}, "output": "o", "nodes": {"o": {"op": "time.offset", "in": "a",
                                                                         "frames": -3}}}
        self.assertEqual(reach(offset, 10, FPS), 13)  # reads three frames ahead

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is missing")
    def test_a_source_file_is_read_as_far_as_the_graph_reaches(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for index in range(20):
                Image.new("RGB", (4, 4), (index * 10, 0, 0)).save(folder / f"f_{index + 1:04d}.png")
            graph = {"ports": {}, "output": "out",
                     "nodes": {"src": {"op": "generate.source", "file": str(folder / "f_%04d.png")},
                               "m": {"op": "curve.keys", "keys": [[0, 0], [1, 2]]},
                               "out": {"op": "time.remap", "in": "src", "map": {"curve": "m"}}}}
            out = evaluate(graph, {}, frames=10, size=(4, 4), fps=FPS)
            from cine_toaster.compositing.reference import encode_srgb

            reds = [round(float(encode_srgb(frame[0, 0, :3])[0]) * 255 / 10) for frame in out]
            self.assertEqual(reds, [1, 3, 5, 7, 9, 11, 13, 15, 17, 19])


class BoundaryTests(unittest.TestCase):
    """The user's review: exact instants stay exact; a tolerance only for approximate curves, explicit."""

    def test_an_exact_map_needs_no_tolerance(self) -> None:
        from fractions import Fraction

        from cine_toaster.compositing.semantics import BOUNDARY_TOLERANCE

        # Exactly on frame 7's start, and a billionth of a frame before it: exact keys keep them apart.
        self.assertEqual(remap_samples(Fraction(7, FPS), FPS), [(7, 1.0)])
        self.assertEqual(remap_samples(Fraction(7, FPS) - Fraction(1, 10**9 * FPS), FPS), [(6, 1.0)])
        # The same instant computed approximately falls under the stated policy: within it, on the boundary.
        self.assertEqual(remap_samples(7 / FPS - BOUNDARY_TOLERANCE / 2 / FPS, FPS), [(7, 1.0)])
        self.assertEqual(remap_samples(7 / FPS - 2 * BOUNDARY_TOLERANCE / FPS, FPS), [(6, 1.0)])

    def test_linear_keys_are_followed_exactly(self) -> None:
        """A billionth of a second short of 2x keeps its instant just under each boundary: 0, 2, 4 ... not 1, 3."""

        self.assertEqual(remap([[0, 0], [1, 2]]), [1, 3, 5, 7, 9, 11, 13, 15, 17, 19])  # on the boundaries
        nearly = remap([[0, "-0.000000001"], [1, "1.999999999"]])
        self.assertEqual(nearly, [0, 2, 4, 6, 8, 10, 12, 14, 16, 18])  # just before each: the frame before

    def test_an_eased_map_is_approximate_and_follows_the_policy(self) -> None:
        eased = remap([{"t": 0, "value": 0, "ease": [0.0, 0.0, 1.0, 1.0]}, {"t": 1, "value": 2}])
        self.assertEqual(eased, sorted(eased))  # a Bezier is computed in floats, monotone all the same


class ExtentTests(unittest.TestCase):
    def test_a_map_that_turns_back_reaches_its_furthest_instant(self) -> None:
        graph = {"ports": {"a": "picture"}, "output": "out",
                 "nodes": {"m": {"op": "curve.keys", "keys": [[0, 0], [0.5, 1.5], [1, 0.5]]},
                           "out": {"op": "time.remap", "in": "a", "map": {"curve": "m"}}}}
        self.assertEqual(reach(graph, 10, FPS), 15)  # past its last instant (0.5 s), to its furthest (1.45 s)
        frames = remap([[0, 0], [0.5, 1.5], [1, 0.5]], source=20)
        self.assertEqual(max(frames), 14)

    def test_before_the_source_its_first_frame(self) -> None:
        self.assertEqual(remap([[0, -1], [1, -0.5]]), [0] * 10)

    def test_a_blend_on_the_last_frame_holds_it_for_arrays_and_clips(self) -> None:
        """At the source's last frame a blend asks for the one after: the last is held, whatever holds it."""

        self.assertEqual(remap([[0, 0.95], [1, 0.97]], source=10, interpolation="blend"), [9] * 10)
        from cine_toaster.compositing.reference import Clip

        raw = (numbered(10) * 65535).astype(np.uint16)
        clip = Clip(raw, "Linear Rec.709 (sRGB)", "premultiplied", "Linear Rec.709 (sRGB)")
        graph = {"ports": {"a": "picture"}, "output": "out",
                 "nodes": {"m": {"op": "curve.keys", "keys": [[0, 0.95], [1, 0.97]]},
                           "out": {"op": "time.remap", "in": "a", "map": {"curve": "m"}, "interpolation": "blend"}}}
        out = evaluate(graph, {"a": clip}, frames=10, size=(2, 2), fps=FPS)
        self.assertEqual({round(float(frame[0, 0, 0]) * 100, 2) for frame in out}, {9.0})


class ShutterTests(unittest.TestCase):
    def test_time_blend_stays_a_shutter_over_output_frames(self) -> None:
        """Kept as it is (the user): an average of neighbouring output frames -- at speed 1, a temporal blur."""

        graph = {"ports": {"a": "picture"}, "output": "b",
                 "nodes": {"b": {"op": "time.blend", "in": "a", "frames": 2}}}
        out = evaluate(graph, {"a": numbered(10)}, frames=10, size=(2, 2), fps=FPS)
        self.assertEqual([round(float(frame[0, 0, 0]) * 100, 4) for frame in out][:4], [0, 0.5, 1.5, 2.5])


if __name__ == "__main__":
    unittest.main()
