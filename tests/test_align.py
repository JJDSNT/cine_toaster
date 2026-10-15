"""C8 step 4 (CT-0081): a relative depth aligned to a metric one, over a stretch, with its residuals -- still an
estimate, its unknown pixels never made far, its use in a composite a decision said and checked.

Synthetic fields first, whose true scale and shift are known exactly; then the models on a rendered dolly
where a ball crosses behind a pillar."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cine_toaster import align, signals
from cine_toaster.compositing.reference import evaluate
from cine_toaster.errors import ValidationError
from cine_toaster.state import Actor

sys.path.insert(0, str(Path(__file__).parent))
from heavy import heavy  # noqa: E402

TOOL = Actor(id="aligner", kind="system")
W, H, FRAMES = 80, 48, 6
TRUE_S, TRUE_T = 0.025, -0.0025  # 1/z = s e + t, so e = (1/z - t) / s
GEOMETRY = {"quantity": "z", "unit": "m", "near_is_small": True}
RELATIVE = {"quantity": "inverse_z", "near_is_small": False, "scale": "unknown: affine"}


def scene(index: int) -> np.ndarray:
    """A wall coming nearer, a disc in front, a floor rising toward the camera, and empty sky top left."""

    z = np.full((H, W), 10.0 - 0.3 * index, np.float32)
    rows, cols = np.indices((H, W))
    z[rows > 36] = 3.0 + (H - rows[rows > 36]) * 0.1  # gentle: a steeper floor reads as edges at this size
    z[(rows - 24) ** 2 + (cols - 30 - 3 * index) ** 2 < 64] = 4.0 - 0.3 * index
    z[:8, :12] = np.inf
    return z


def objects_of(index: int) -> np.ndarray:
    """The scene's objects as instances: 1 the wall, 2 the floor, 3 the disc; 0 the sky."""

    z = scene(index)
    labels = np.ones((H, W), np.int32)
    rows, cols = np.indices((H, W))
    labels[rows > 36] = 2
    labels[(rows - 24) ** 2 + (cols - 30 - 3 * index) ** 2 < 64] = 3
    labels[~np.isfinite(z)] = 0
    return labels


def estimate_of(z: np.ndarray, s: float = TRUE_S, t: float = TRUE_T) -> np.ndarray:
    e = (np.where(np.isfinite(z), 1.0 / z, 0.0) - t) / s
    e[~np.isfinite(z)] = 0.0  # the sky: the model's smallest inverse depth -- beyond any reach once aligned
    return e.astype(np.float32)


class Synthetic(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\n")
        signals.record_signal(self.root, signal_id="truth", kind="depth", origin="geometric", rate=24, actor=TOOL,
                              frames=[scene(i) for i in range(FRAMES)], camera="cam", depth=GEOMETRY)

    def estimate(self, frames: list[np.ndarray], signal_id: str = "guess") -> None:
        signals.record_signal(self.root, signal_id=signal_id, kind="depth_relative", origin="estimated", rate=24,
                              actor=TOOL, frames=frames, depth=RELATIVE)

    def align(self, **given) -> dict:
        return align.align_depth(self.root, **{"signal_id": "aligned", "estimate": "guess", "reference": "truth",
                                               "camera": "cam", "actor": TOOL, **given})

    def test_a_known_scale_and_shift_are_found_in_every_mode(self) -> None:
        self.estimate([estimate_of(scene(i)) for i in range(FRAMES)])
        for mode in align.TEMPORAL:
            made = self.align(temporal=mode)
            for item in made["parameters"]:
                self.assertAlmostEqual(item["s"], TRUE_S, places=6)
                self.assertAlmostEqual(item["t"], TRUE_T, places=6)
            self.assertLess(made["residual"]["abs_rel"], 1e-4)
            self.assertLess(made["held_out_frames"]["abs_rel"], 1e-4)
            self.assertLess(made["held_out_pixels"]["abs_rel"], 1e-4)
        # An alignment beats a depth that knows nothing, on frames it did not see.
        self.assertLess(made["held_out_frames"]["abs_rel"],
                        made["modes_compared"]["baseline: a constant depth"]["abs_rel"] / 10)

    def test_an_aligned_estimate_stays_an_estimate_with_its_history(self) -> None:
        self.estimate([estimate_of(scene(i)) for i in range(FRAMES)])
        self.align()
        record = signals.load_record(self.root, "aligned")
        self.assertEqual((record["kind"], record["origin"], record["camera"]), ("depth", "estimated", "cam"))
        self.assertEqual(signals.status(self.root, "aligned")["transformations"], ["align_depth"])
        step = record["provenance"][-1]
        self.assertEqual(step["transformation"]["reference"], "truth")
        self.assertEqual(set(step["transformation"]["modes_compared"]),
                         {"shared", "regularized", "per_frame", "baseline: a constant depth"})
        self.assertIn({"signal": "truth"}, [{"signal": item["signal"]} for item in step["inputs"] if "signal" in item])
        metrics = [item["metric"] for item in record["quality"]["measured"]]
        self.assertTrue(any("frames held out" in metric for metric in metrics), metrics)
        self.assertEqual(record["quality"]["declared"], None)  # nothing claimed by a maker
        self.assertEqual(record["depth"]["calibrated"]["frames"], [0, FRAMES - 1])
        # The reference recorded again: the calibration no longer follows from it.
        signals.record_signal(self.root, signal_id="truth", kind="depth", origin="geometric", rate=24, actor=TOOL,
                              frames=[scene(i) * 1.1 for i in range(FRAMES)], camera="cam", depth=GEOMETRY)
        self.assertTrue(any("truth" in reason for reason in signals.status(self.root, "aligned")["stale"]))

    def test_beyond_the_reach_of_the_calibration_is_unknown_never_far_never_zero(self) -> None:
        self.estimate([estimate_of(scene(i)) for i in range(FRAMES)])
        self.align()
        reader = signals.SignalReader(self.root, "aligned")
        unknown = reader.unknown(0)
        np.testing.assert_array_equal(unknown, ~np.isfinite(scene(0)))  # the sky, and only it
        self.assertFalse((reader.frame(0) == 0).any())
        self.assertIn("not far", reader.record["unknown"])

    def objects(self) -> None:
        signals.record_signal(self.root, signal_id="objects", kind="segmentation", origin="geometric", rate=24,
                              actor=TOOL, frames=[objects_of(i) for i in range(FRAMES)], camera="cam",
                              labels={0: "nothing", 1: "wall", 2: "floor", 3: "disc"}, labels_are="instances")

    def test_an_inverted_occlusion_is_found_flagged_and_refused_unless_accepted(self) -> None:
        # The model puts the disc behind the wall on frames 2 and 3 -- a small share of the pixels, a large
        # error where it shows: the disc would vanish behind the wall.
        frames = []
        for index in range(FRAMES):
            z = scene(index).copy()
            if index in (2, 3):
                z[objects_of(index) == 3] = 14.0
            frames.append(estimate_of(z))
        self.estimate(frames)
        self.objects()
        made = self.align(objects="objects")
        self.assertEqual(made["occlusions_inverted"], {"wall/disc": [2, 3]})
        self.assertLess(made["residual"]["abs_rel"], 0.15)  # the average does not show it
        self.card()
        run = lambda graph: evaluate(graph, {}, frames=FRAMES, size=(W, H), fps=24, root=self.root)  # noqa: E731
        with self.assertRaisesRegex(ValidationError, "occlusions inverted"):
            run(self.graph({"estimated": True}, unknown="behind"))
        run(self.graph({"estimated": True, "inversions": "accept"}, unknown="behind"))  # a decision, said
        # A correct estimate is not flagged.
        self.estimate([estimate_of(scene(i)) for i in range(FRAMES)])
        self.assertEqual(self.align(objects="objects")["occlusions_inverted"], {})

    def test_objects_that_do_not_meet_are_not_an_occlusion(self) -> None:
        # The model sets the disc behind the wall -- but the disc stands well apart here (a sky between them):
        # an order wrong, reported apart, never flagged as an occlusion nor refused.
        frames, labels = [], []
        for index in range(FRAMES):
            z = scene(index).copy()
            label = objects_of(index)
            ring = (label == 1) & (np.abs(np.indices((H, W))[0] - 24) < 14) & (np.abs(np.indices((H, W))[1] - 30
                                                                                     - 3 * index) < 14)
            z[ring & (label != 3)] = np.inf  # empty all round the disc
            label[ring & (label != 3)] = 0
            truth_z = z.copy()
            z[label == 3] = 14.0
            frames.append((estimate_of(z), truth_z, label))
        signals.record_signal(self.root, signal_id="truth", kind="depth", origin="geometric", rate=24, actor=TOOL,
                              frames=[item[1] for item in frames], camera="cam", depth=GEOMETRY)
        self.estimate([item[0] for item in frames])
        signals.record_signal(self.root, signal_id="objects", kind="segmentation", origin="geometric", rate=24,
                              actor=TOOL, frames=[item[2] for item in frames], camera="cam",
                              labels={0: "nothing", 1: "wall", 2: "floor", 3: "disc"}, labels_are="instances")
        made = self.align(objects="objects")
        self.assertEqual(made["occlusions_inverted"], {})
        self.assertEqual(made["order_by_objects"]["wall/disc"]["apart_inverted"], list(range(FRAMES)))
        self.assertEqual(made["order_by_objects"]["wall/disc"]["met"], [])

    def test_the_record_says_everything_the_alignment_did(self) -> None:
        self.estimate([estimate_of(scene(i)) for i in range(FRAMES)])
        self.objects()
        self.align(objects="objects", region="objects", leave_labels=[2], smoothness=2.0)
        step = signals.load_record(self.root, "aligned")["provenance"][-1]
        done = step["transformation"]
        for key in ("method", "temporal", "smoothness", "time", "reference", "camera", "camera_stated_by",
                    "stretch", "depth_range", "parameters", "excluded", "residual", "trimmed", "held_out_pixels",
                    "held_out_frames", "held_out_tail", "beyond_region", "temporal_agreement", "modes_compared",
                    "objects", "order_by_objects", "occlusions_inverted", "unknown"):
            self.assertIn(key, done)
        self.assertEqual((done["temporal"], done["smoothness"]), ("regularized", 2.0))
        self.assertEqual(done["excluded"]["region"], {"signal": "objects", "keep": None, "leave": [2]})
        pinned = {item["signal"] for item in step["inputs"] if "signal" in item}
        self.assertEqual(pinned, {"guess", "truth", "objects"})
        # The three measures stay apart: metric error, stability in time, order of occlusion.
        metrics = [item["metric"] for item in signals.load_record(self.root, "aligned")["quality"]["measured"]]
        self.assertTrue(any("temporal agreement" in m for m in metrics))
        self.assertTrue(any("order of objects" in m for m in metrics))
        self.assertTrue(any("held out" in m for m in metrics))
        # The objects re-recorded: the alignment no longer follows.
        signals.record_signal(self.root, signal_id="objects", kind="segmentation", origin="geometric", rate=24,
                              actor=TOOL, frames=[np.zeros((H, W), np.int32)] * FRAMES, camera="cam",
                              labels={0: "nothing"}, labels_are="instances")
        self.assertTrue(any("objects" in reason for reason in signals.status(self.root, "aligned")["stale"]))

    def test_the_command_line_aligns_and_says_what_it_found(self) -> None:
        import contextlib
        import io
        import json

        from cine_toaster.cli import main

        self.estimate([estimate_of(scene(i)) for i in range(FRAMES)])
        self.objects()
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = main(["signal", "align", str(self.root), "aligned", "--estimate", "guess", "--reference", "truth",
                         "--camera", "cam", "--objects", "objects", "--actor", "editor"])
        self.assertEqual(code, 0)
        shown = json.loads(printed.getvalue())
        self.assertEqual(shown["occlusions_inverted"], {})
        self.assertLess(shown["held_out_frames"]["abs_rel"], 1e-3)
        self.assertEqual(signals.load_record(self.root, "aligned")["provenance"][-1]["by"]["id"], "editor")
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(io.StringIO()):
            code = main(["signal", "align", str(self.root), "aligned", "--estimate", "guess", "--reference", "truth",
                         "--camera", "elsewhere"])
        self.assertNotEqual(code, 0)  # refused, not aligned to a camera the reference is not from

    def test_a_continuous_stretch_held_out_asks_whether_the_fit_holds_forward(self) -> None:
        # The model's scale drifts steadily: alternate frames left out are interpolated from their neighbours
        # and come out exact; the last stretch, fitted from the past alone, does not.
        self.estimate([estimate_of(scene(i), s=TRUE_S * (1.0 + 0.2 * i)) for i in range(FRAMES)])
        made = self.align(temporal="per_frame")
        self.assertEqual(made["held_out_tail"]["frames"], [FRAMES - 1, FRAMES - 1])  # the last quarter: one frame
        measured = signals.load_record(self.root, "aligned")["quality"]["measured"]
        self.assertTrue(any("last stretch" in item["metric"] for item in measured))
        self.assertLess(made["held_out_frames"]["abs_rel"], made["held_out_tail"]["abs_rel"])  # neighbours flatter
        self.assertLess(made["held_out_frames"]["abs_rel"], 1e-3)
        self.assertGreater(made["held_out_tail"]["abs_rel"], 0.05)
        self.assertLess(made["residual"]["abs_rel"], 1e-3)

    def test_a_scale_that_drifts_frame_to_frame_is_carried_into_metres_by_a_shared_fit(self) -> None:
        # A frame-by-frame model renormalizes each frame (measured: Depth Anything V2's scale moves 4x).
        drift = [1.0, 1.6, 0.7, 1.3, 0.8, 1.5]
        self.estimate([estimate_of(scene(i), s=TRUE_S / drift[i]) for i in range(FRAMES)])
        compared = self.align(temporal="per_frame")["modes_compared"]
        self.assertLess(compared["per_frame"]["residual"]["abs_rel"], 1e-4)
        self.assertGreater(compared["shared"]["temporal_agreement"]["mean_change_error"],
                           10 * compared["per_frame"]["temporal_agreement"]["mean_change_error"] + 1e-3)
        spread = lambda mode: compared[mode]["s_range"][1] - compared[mode]["s_range"][0]  # noqa: E731
        self.assertLess(spread("regularized"), spread("per_frame"))
        self.assertGreater(spread("regularized"), spread("shared"))

    def test_frames_held_out_catch_a_fit_that_holds_only_where_it_looked(self) -> None:
        # The model's scale alternates frame to frame: each frame fits exactly; frames left out of the fit, given
        # parameters from their neighbours, do not.
        self.estimate([estimate_of(scene(i), s=TRUE_S / (1.0 if i % 2 == 0 else 2.0)) for i in range(FRAMES)])
        made = self.align(temporal="per_frame")
        self.assertLess(made["residual"]["abs_rel"], 1e-4)
        self.assertGreater(made["held_out_frames"]["abs_rel"], 0.1)

    def test_regularization_counts_the_real_time_between_frames(self) -> None:
        estimates = [estimate_of(scene(i), s=TRUE_S * (1.0 if i < 3 else 2.0)) for i in range(4)]
        references = [scene(i) for i in range(4)]
        masks = [align.valid_pixels(e, r, edge_jump=0.05) for e, r in zip(estimates, references)]
        close, _ = align.fit(estimates, references, masks, mode="regularized", times=[0, 1, 2, 3], smoothness=5)
        apart, _ = align.fit(estimates, references, masks, mode="regularized", times=[0, 1, 2, 30], smoothness=5)
        # Far apart in time, the last frame may differ more: its scale nearer its own.
        self.assertLess(abs(apart[3, 0] - TRUE_S * 2.0), abs(close[3, 0] - TRUE_S * 2.0))

    def test_what_cannot_be_aligned_is_refused(self) -> None:
        self.estimate([estimate_of(scene(i)) for i in range(FRAMES)])
        cases = {
            "another camera": dict(camera="other"),
            "an estimate not relative": dict(estimate="truth"),
            "a stretch the reference does not reach": dict(first=2, count=FRAMES),
        }
        for name, given in cases.items():
            with self.subTest(case=name), self.assertRaises(ValidationError):
                self.align(**given)
        signals.record_signal(self.root, signal_id="far", kind="depth", origin="geometric", rate=24, actor=TOOL,
                              frames=[scene(i) for i in range(FRAMES)], camera="cam",
                              depth={**GEOMETRY, "quantity": "distance"})
        with self.assertRaisesRegex(ValidationError, "distance"):
            self.align(reference="far")
        signals.record_signal(self.root, signal_id="small", kind="depth", origin="geometric", rate=24, actor=TOOL,
                              frames=[scene(i)[::2, ::2] for i in range(FRAMES)], camera="cam", depth=GEOMETRY)
        with self.assertRaisesRegex(ValidationError, "pixel for pixel"):
            self.align(reference="small")
        # An estimate that is a z, said to be an inverse z: aligned, it would turn near into far.
        self.estimate([np.where(np.isfinite(scene(i)), scene(i), 50.0) for i in range(FRAMES)], signal_id="z-guess")
        with self.assertRaisesRegex(ValidationError, "not positive"):
            self.align(estimate="z-guess")

    def graph(self, depth_node: dict, card_z: str = "card-z", **merge) -> dict:
        return {"output": "out", "nodes": {
            "a": {"op": "generate.solid", "colour": [1, 0, 0, 1]},
            "card": {"op": "generate.solid", "colour": [0, 1, 0, 1]},
            "za": {"op": "signal.read", "signal": "aligned", "kind": "depth", "camera": "cam", **depth_node},
            "zc": {"op": "signal.read", "signal": card_z, "kind": "depth", "camera": "cam"},
            "out": {"op": "merge.depth", "pictures": ["a", "card"], "depths": ["za", "zc"], **merge}}}

    def card(self, signal_id: str = "card-z", size: tuple[int, int] = (H, W), **depth) -> None:
        signals.record_signal(self.root, signal_id=signal_id, kind="depth", origin="authored", rate=24, actor=TOOL,
                              frames=[np.full(size, 6.0, np.float32)] * FRAMES, camera="cam",
                              depth={**GEOMETRY, **depth})

    def test_a_composite_uses_an_aligned_depth_only_when_told_and_only_where_it_holds(self) -> None:
        self.estimate([estimate_of(scene(i)) for i in range(FRAMES)])
        self.align()
        self.card()
        run = lambda graph, frames=FRAMES: evaluate(graph, {}, frames=frames, size=(W, H), fps=24,  # noqa: E731
                                                    root=self.root)
        with self.assertRaisesRegex(ValidationError, "estimated: true"):
            run(self.graph({}))
        with self.assertRaisesRegex(ValidationError, "unknown"):  # the sky shows red there: unknown, refused
            run(self.graph({"estimated": True}))
        out = run(self.graph({"estimated": True}, unknown="behind"))
        z = scene(0)
        self.assertTrue(np.allclose(out[0][np.isfinite(z) & (z < 6)], [1, 0, 0, 1]))  # the disc, the floor's front
        self.assertTrue(np.allclose(out[0][np.isfinite(z) & (z > 6)], [0, 1, 0, 1]))  # the wall behind the card
        self.assertTrue(np.allclose(out[0][~np.isfinite(z)], [0, 1, 0, 1]))  # unknown, put behind as told
        # Said estimated, still refused past its calibrated stretch...
        with self.assertRaisesRegex(ValidationError, "valid on its frames"):
            run(self.graph({"estimated": True}, unknown="behind"), frames=FRAMES + 2)
        # ... of another camera ...
        with self.assertRaises(ValidationError):
            run(self.graph({"estimated": True, "camera": "other"}, unknown="behind"))
        # ... beside a depth of another quantity, or of another pixel grid ...
        self.card("card-distance", quantity="distance")
        with self.assertRaisesRegex(ValidationError, "quantities"):
            run(self.graph({"estimated": True}, card_z="card-distance", unknown="behind"))
        self.card("card-small", size=(H // 2, W // 2))
        with self.assertRaisesRegex(ValidationError, "pixel grids"):
            run(self.graph({"estimated": True}, card_z="card-small", unknown="behind"))
        # One camera, one size, but a crop of its image: other pixels.
        signals.record_signal(self.root, signal_id="card-crop", kind="depth", origin="authored", rate=24, actor=TOOL,
                              frames=[np.full((H, W), 6.0, np.float32)] * FRAMES, camera="cam", depth=GEOMETRY,
                              window=[0.25, 0.25, 0.75, 0.75])
        with self.assertRaisesRegex(ValidationError, "windows"):
            run(self.graph({"estimated": True}, card_z="card-crop", unknown="behind"))
        # ... and once stale.
        signals.record_signal(self.root, signal_id="truth", kind="depth", origin="geometric", rate=24, actor=TOOL,
                              frames=[scene(i) * 1.1 for i in range(FRAMES)], camera="cam", depth=GEOMETRY)
        with self.assertRaisesRegex(ValidationError, "stale"):
            run(self.graph({"estimated": True}, unknown="behind"))


class RecordedWrongOcclusion(unittest.TestCase):
    """Real model output kept as a fixture (fixtures/c8/da2-occlusion.md): the fast suite checks, without
    Blender or a model, that Depth Anything V2's wrong occlusion is still found and refused."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\n")
        recorded = np.load(Path(__file__).parent / "fixtures" / "c8" / "da2-occlusion.npz")
        signals.record_signal(self.root, signal_id="occ-depth", kind="depth", origin="geometric", rate=24,
                              actor=TOOL, frames=list(recorded["depth"].astype(np.float32)), camera="occ/cam",
                              depth={**GEOMETRY, "empty": "inf"})
        signals.record_signal(self.root, signal_id="occ-da2", kind="depth_relative", origin="estimated", rate=24,
                              actor=TOOL, frames=list(recorded["estimate"].astype(np.float32)), depth=RELATIVE)
        signals.record_signal(self.root, signal_id="occ-objects", kind="segmentation", origin="geometric", rate=24,
                              actor=TOOL, frames=list(recorded["objects"].astype(np.int32)), camera="occ/cam",
                              labels={0: "nothing", 1: "ball", 2: "floor", 3: "pillar", 4: "wall"},
                              labels_are="instances")

    def test_the_wrong_occlusion_is_found_where_the_two_meet_and_only_there(self) -> None:
        made = align.align_depth(self.root, signal_id="occ-z", estimate="occ-da2", reference="occ-depth",
                                 camera="occ/cam", actor=TOOL, objects="occ-objects")
        self.assertEqual(made["occlusions_inverted"], {"floor/pillar": [0, 1, 2, 7]})
        self.assertEqual(made["order_by_objects"]["ball/pillar"]["apart_inverted"], [0, 1, 2, 6, 7])
        self.assertEqual(made["order_by_objects"]["ball/pillar"]["occlusion_inverted"], [])
        self.assertLess(made["residual"]["abs_rel"], 0.15)  # the average passes; the occlusion does not
        signals.record_signal(self.root, signal_id="card-z", kind="depth", origin="authored", rate=24, actor=TOOL,
                              frames=[np.full((180, 320), 6.0, np.float32)] * 8, camera="occ/cam",
                              depth=GEOMETRY)
        graph = {"output": "out", "nodes": {
            "a": {"op": "generate.solid", "colour": [1, 0, 0, 1]},
            "card": {"op": "generate.solid", "colour": [0, 1, 0, 1]},
            "z": {"op": "signal.read", "signal": "occ-z", "kind": "depth", "camera": "occ/cam", "estimated": True},
            "zc": {"op": "signal.read", "signal": "card-z", "kind": "depth", "camera": "occ/cam"},
            "out": {"op": "merge.depth", "pictures": ["a", "card"], "depths": ["z", "zc"], "unknown": "refuse"}}}
        with self.assertRaisesRegex(ValidationError, "floor/pillar on frames \\[0, 1, 2, 7\\]"):
            evaluate(graph, {}, frames=8, size=(320, 180), fps=24, root=self.root)
        graph["nodes"]["z"]["inversions"] = "accept"
        self.assertEqual(evaluate(graph, {}, frames=8, size=(320, 180), fps=24, root=self.root).shape,
                         (8, 180, 320, 4))


def _models_and_blender() -> str:
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from test_estimates import _models_here

    return _models_here()


OCCLUSION = {
    "objects": [
        {"name": "wall", "type": "plane", "size": [30, 20], "location": [0, 12, 0], "rotation": [90, 0, 0],
         "colour": [0.55, 0.5, 0.45]},
        {"name": "floor", "type": "plane", "size": [30, 30], "location": [0, 6, -1.2], "colour": [0.3, 0.35, 0.3]},
        {"name": "pillar", "type": "cube", "size": 1.0, "location": [0.3, 6, 0], "colour": [0.2, 0.3, 0.7]},
        # Crosses behind the pillar, hidden at the fifth frame.
        {"name": "ball", "type": "sphere", "radius": 0.5, "location": [-3.0, 8, -0.3], "colour": [0.85, 0.25, 0.1],
         "keys": [{"frame": 1, "location": [-3.0, 8, -0.3]}, {"frame": 8, "location": [3.0, 8, -0.3]}]}],
    # A dolly of 2.5 m: everything grows in the frame.
    "camera": {"name": "cam", "lens": 35, "sensor_width": 36,
               "keys": [{"frame": 1, "location": [0, 0, 0.2], "rotation": [90, 0, 0]},
                        {"frame": 8, "location": [0, 2.5, 0.2], "rotation": [90, 0, 0]}]},
}


@heavy("renders with Blender and runs two models")
@unittest.skipIf(_models_and_blender(), _models_and_blender())
class OnARenderedDolly(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import json
        import subprocess

        from cine_toaster import estimates, renders

        cls.directory = tempfile.TemporaryDirectory()
        cls.root = root = Path(cls.directory.name)
        (root / "project.yaml").write_text("id: t\ntitle: T\n")
        (root / "scenes").mkdir()
        (root / "scenes" / "occlusion.json").write_text(json.dumps(OCCLUSION))
        renders.render_passes(root, render_id="occ", camera="cam", first=1, last=8, size=(320, 180), fps=24,
                              recipe="scenes/occlusion.json", samples=16, actor=TOOL)
        reader = renders.RenderReader(root, "occ")
        pictures = []
        for index in range(8):
            picture = reader.picture(index)
            rgb = np.clip(picture[..., :3] + (1 - picture[..., 3:]) * 0.18, 0, 1)
            srgb = np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * rgb ** (1 / 2.4) - 0.055)
            pictures.append((srgb * 255 + 0.5).astype(np.uint8))
        (root / "plates").mkdir()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "320x180",
                        "-r", "24", "-i", "-", "-c:v", "ffv1", str(root / "plates" / "occ.mkv")],
                       input=np.stack(pictures).tobytes(), check=True)
        cls.made = {}
        for model, name in (("depth-anything-v2-small", "da2"), ("video-depth-anything-small", "vda")):
            estimates.estimate(root, signal_id=f"occ-{name}", model=model, media="plates/occ.mkv", actor=TOOL,
                               parameters={"input_size": 252} if name == "vda" else None)
            cls.made[name] = align.align_depth(root, signal_id=f"occ-{name}-z", estimate=f"occ-{name}",
                                               reference="occ-depth", camera="occ/cam", actor=TOOL,
                                               objects="occ-objects")
            cls.made[f"{name}-floor"] = align.align_depth(root, signal_id=f"occ-{name}-floor",
                                                          estimate=f"occ-{name}", reference="occ-depth",
                                                          camera="occ/cam", actor=TOOL, region="occ-objects",
                                                          keep_labels=[2])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def test_aligned_depth_beats_knowing_nothing_on_frames_it_did_not_see(self) -> None:
        for name in ("da2", "vda", "da2-floor", "vda-floor"):
            made = self.made[name]
            baseline = made["modes_compared"]["baseline: a constant depth"]["abs_rel"]
            self.assertLess(made["held_out_frames"]["abs_rel"], baseline / 2, (name, made["held_out_frames"]))

    def test_the_default_does_not_flicker_more_than_a_shared_fit(self) -> None:
        for name in ("da2", "vda", "da2-floor", "vda-floor"):
            compared = self.made[name]["modes_compared"]
            self.assertLess(compared["regularized"]["temporal_agreement"]["mean_change_error"],
                            compared["shared"]["temporal_agreement"]["mean_change_error"], name)

    def test_the_alignment_never_reorders_a_frame(self) -> None:
        # s > 0 makes the map monotone: whatever the estimate orders wrong (Depth Anything V2 puts the pillar
        # behind the ball), it is the estimate's, measured, not the alignment's.
        for name in ("da2", "vda"):
            estimate = signals.SignalReader(self.root, f"occ-{name}")
            aligned = signals.SignalReader(self.root, f"occ-{name}-z")
            for index in range(8):
                e, z = estimate.frame(index), aligned.frame(index)
                known = ~aligned.unknown(index)
                order_e = np.argsort(-e[known].ravel(), kind="stable")
                self.assertTrue(np.all(np.diff(z[known].ravel()[order_e]) >= -1e-4), (name, index))

    def test_a_wrong_occlusion_is_caught_even_when_it_cannot_be_put_right(self) -> None:
        # Measured on these pinned models: Depth Anything V2 sets the pillar behind the floor along its
        # silhouette; the video model does not. The calibration cannot fix an order (s > 0); it says so, and a
        # composite refuses the depth until someone accepts it.
        flagged = self.made["da2"]["occlusions_inverted"]
        self.assertTrue(any("pillar" in pair for pair in flagged), flagged)
        self.assertLess(self.made["da2"]["residual"]["abs_rel"], 0.2)  # an average that would pass
        self.assertEqual(self.made["vda"]["occlusions_inverted"], {})
        graph = {"output": "out", "nodes": {
            "r": {"op": "generate.render", "render": "occ", "camera": "occ/cam"},
            "card": {"op": "generate.solid", "colour": [0, 1, 0, 1]},
            "z": {"op": "signal.read", "signal": "occ-da2-z", "kind": "depth", "camera": "occ/cam",
                  "estimated": True},
            "out": {"op": "merge.depth", "pictures": ["card", "r"], "depths": ["z", "r.depth"]}}}
        with self.assertRaisesRegex(ValidationError, "occlusions inverted"):
            evaluate(graph, {}, frames=8, size=(320, 180), fps=24, root=self.root)
        graph["nodes"]["z"]["signal"] = "occ-vda-z"
        evaluate(graph, {}, frames=8, size=(320, 180), fps=24, root=self.root)

    def test_a_ground_plane_does_not_vouch_for_what_stands_on_it(self) -> None:
        # Calibrated on the floor only, the objects are an extrapolation: measured, on record, and worse.
        for name in ("da2-floor", "vda-floor"):
            made = self.made[name]
            self.assertIn("beyond_region", made)
            self.assertGreater(made["beyond_region"]["abs_rel"], made["residual"]["abs_rel"])


if __name__ == "__main__":
    unittest.main()
