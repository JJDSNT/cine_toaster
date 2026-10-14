"""C3: parameters over time -- a beat's instant kept apart from how a parameter reacts to it (CT-0074)."""

from __future__ import annotations

import unittest

import numpy as np

from cine_toaster.compositing.gl import gl_unavailable_reason
from cine_toaster.compositing.reference import curve_factory, evaluate
from cine_toaster.compositing.schema import validate

OUT = "1 - (1 - x)^2"  # the `out` ease, for reading the tests


def beat_curve(beats: list[float], **params):
    """The beat curve of a one-node graph, as every renderer gets it. At 1000 frames a second a beat at 1.0 s
    peaks at 1.0005, the centre of its frame: the times below are read as offsets from there."""

    nodes = {"pulse": {"op": "curve.beats", **params}}
    curve = curve_factory(nodes, {}, fps=1000, length=10.0, beats=beats, tracks=lambda name: {})("pulse")
    return lambda seconds: curve(seconds + 0.0005)


def sampled(curve, start: float, end: float, step: float = 0.0005) -> tuple[np.ndarray, np.ndarray]:
    times = np.arange(start, end, step)
    return times, np.array([float(curve(t)) for t in times])


class EnvelopeTests(unittest.TestCase):
    def test_an_ease_reshapes_the_pulse_and_never_moves_it_off_the_beat(self) -> None:
        shapes = {}
        for ease in ("linear", "in", "out", [0.2, 0.9, 0.3, 1.0]):
            curve = beat_curve([1.0], attack=0.05, decay=0.3, attack_ease=ease, decay_ease=ease)
            times, values = sampled(curve, 0.9, 1.4)
            with self.subTest(ease=ease):
                self.assertAlmostEqual(float(times[int(np.argmax(values))]), 1.0, places=3)  # the peak is the beat's
                self.assertEqual(float(curve(1.0)), 1.0)
                self.assertEqual(float(curve(0.94)), 0.0)  # before the attack: at rest
                self.assertEqual(float(curve(1.31)), 0.0)  # after the decay: at rest
            shapes[str(ease)] = float(curve(1.1))
        # ...while the shape between differs: `out` falls fast first, `in` holds high first.
        self.assertLess(shapes["out"], shapes["linear"])
        self.assertGreater(shapes["in"], shapes["linear"])
        self.assertAlmostEqual(shapes["out"], 1 - (1 - (1 - 1 / 3) ** 2), places=4)  # 1 - out(0.1 / 0.3)

    def test_the_frame_a_beat_falls_in_shows_the_full_pulse_whatever_the_ease(self) -> None:
        """Frames read curves at their centre; a beat at a frame's edge must not peak on the frame before."""

        fps = 24
        for beat in (0.5, 0.5 + 0.2 / fps, 0.5 + 0.99 / fps):  # at the start, inside, at the end of frame 12
            for rise, fall in (("linear", "linear"), ("out", [0.0, 0.0, 0.2, 1.0]), ("in", "out")):
                nodes = {"pulse": {"op": "curve.beats", "attack": 0.05, "decay": 0.3, "attack_ease": rise,
                                   "decay_ease": fall}}
                curve = curve_factory(nodes, {}, fps=fps, length=2.0, beats=[beat], tracks=lambda name: {})("pulse")
                values = [float(curve((frame + 0.5) / fps)) for frame in range(24)]
                with self.subTest(beat=beat, rise=rise, fall=fall):
                    self.assertEqual(int(np.argmax(values)), 12)
                    self.assertEqual(values[12], 1.0)

    def test_a_pulse_is_continuous_with_no_jump(self) -> None:
        curve = beat_curve([1.0, 2.0], attack=0.03, decay=0.28, decay_ease=[0.0, 0.0, 0.2, 1.0], low=1.0, high=1.06)
        _, values = sampled(curve, 0.5, 2.5)
        steps = np.abs(np.diff(values))
        # At 2 kHz the steepest step is the attack's: 0.06 over 0.03 s is 0.001 per sample.
        self.assertLess(float(steps.max()), 0.0011)
        self.assertAlmostEqual(float(values.min()), 1.0)
        self.assertAlmostEqual(float(values.max()), 1.06)

    def test_close_beats_meet_by_the_overlap_rule(self) -> None:
        """Beats closer than a pulse lasts: `max` keeps the higher pulse, `add` sums them up to a full one.
        Either way the second beat still peaks on its own instant, and nothing jumps."""

        beats = [1.0, 1.1]  # the first pulse's decay (0.25 s) is still high when the second rises
        kept = beat_curve(beats, attack=0.04, decay=0.25)
        added = beat_curve(beats, attack=0.04, decay=0.25, overlap="add")
        self.assertEqual(float(kept(1.1)), 1.0)
        self.assertEqual(float(added(1.1)), 1.0)  # a sum is capped at a full pulse
        # Just before the second beat, the first has fallen to 0.64 and the second risen to 0.75.
        self.assertAlmostEqual(float(kept(1.09)), 0.75, places=3)
        self.assertAlmostEqual(float(added(1.09)), 1.0, places=3)  # 0.64 + 0.75, capped
        self.assertGreater(float(added(1.08)), float(kept(1.08)))
        for curve in (kept, added):
            times, values = sampled(curve, 0.9, 1.5)
            self.assertLessEqual(float(values.max()), 1.0)
            self.assertLess(float(np.abs(np.diff(values)).max()), 0.0126)  # the attack's 1/40 per ms, at most

    def test_every_other_beat(self) -> None:
        curve = beat_curve([1.0, 1.5, 2.0], every=2, attack=0.02, decay=0.1)
        self.assertEqual([float(curve(t)) for t in (1.0, 1.5, 2.0)], [1.0, 0.0, 1.0])


class EaseValidationTests(unittest.TestCase):
    def graph(self, **pulse) -> dict:
        return {"ports": {"a": "picture"},
                "nodes": {"pulse": {"op": "curve.beats", **pulse},
                          "out": {"op": "warp.transform", "in": "a", "scale": {"curve": "pulse"}}}, "output": "out"}

    def test_an_unknown_ease_is_refused_before_anything_renders(self) -> None:
        self.assertEqual(validate(self.graph(decay_ease="bounce"))[0][0], "composite_unknown_param")
        self.assertIn("handles' times", validate(self.graph(attack_ease=[1.5, 0, 0.5, 1]))[0][1])
        self.assertEqual(validate(self.graph(overlap="replace"))[0][0], "composite_unknown_param")
        self.assertEqual(validate(self.graph(decay_ease=[0.2, 0.9, 0.3, 1.0], overlap="add")), [])
        keys = {"ports": {}, "nodes": {"k": {"op": "curve.keys", "keys": [{"t": 0, "value": 0, "ease": "wobble"},
                                                                            [1, 1]]}}, "output": "k"}
        self.assertIn("no ease 'wobble'", validate(keys)[0][1])


def square(size: int = 64) -> np.ndarray:
    picture = np.zeros((size * 9 // 16, size, 4), np.float32)
    h, w = picture.shape[:2]
    picture[h // 2 - 6:h // 2 + 6, w // 2 - 6:w // 2 + 6] = 1.0
    return picture


PULSE = {"ports": {"a": "picture"},
         "nodes": {"pulse": {"op": "curve.beats", "attack": 0.05, "decay": 0.3, "low": 1.0, "high": 1.5,
                             "attack_ease": "out", "decay_ease": [0.0, 0.0, 0.2, 1.0]},
                   "out": {"op": "warp.transform", "in": "a", "scale": {"curve": "pulse"}}}, "output": "out"}


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class RenderersAgreeInTimeTests(unittest.TestCase):
    def test_the_scale_pulses_on_the_same_frames_in_the_reference_and_on_gl(self) -> None:
        from cine_toaster.compositing.gl import renderer_for

        options = {"frames": 48, "size": (64, 36), "fps": 24, "beats": [0.5, 1.25]}
        exact = evaluate(PULSE, {"a": square()}, **options)
        fast = np.stack(list(renderer_for(PULSE).evaluate(PULSE, {"a": square()}, stream=True, **options)))
        coverage = exact[..., 3].sum(axis=(1, 2)), fast[..., 3].sum(axis=(1, 2))
        # The same frames are largest, on the beats (frames 12 and 30), and the pulse has the same shape.
        for area in coverage:
            peaks = [frame for frame in range(1, 47) if area[frame] > area[frame - 1] and area[frame] >= area[frame + 1]]
            self.assertEqual(peaks, [12, 30])
        self.assertLess(float(np.abs(coverage[0] - coverage[1]).max() / coverage[0].max()), 0.03)
        self.assertLess(float(np.abs(exact - fast).mean()), 0.02)


if __name__ == "__main__":
    unittest.main()
