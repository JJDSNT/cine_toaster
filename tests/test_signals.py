"""C8 step 1 (CT-0081): signals as production records -- kind, origin and transformations kept apart; provenance,
quality, invalidation, corrections, time; read by the graph under SPEC-0012's contract."""

from __future__ import annotations

import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import numpy as np

from cine_toaster import signals
from cine_toaster.compositing.reference import evaluate
from cine_toaster.compositing.schema import validate
from cine_toaster.errors import ValidationError
from cine_toaster.events import tail_events
from cine_toaster.state import Actor

TOOL = Actor(id="renderer", kind="system")
PERSON = Actor(id="editor")
DEPTH = {"quantity": "z", "unit": "m", "near_is_small": True}
W, H = 16, 9


def ramp(count: int, base: float = 1.0) -> list[np.ndarray]:
    """Depth frames whose every pixel says its frame: base + frame."""

    return [np.full((H, W), base + index, np.float32) for index in range(count)]


class SignalCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
        (self.root / "plates").mkdir()
        (self.root / "plates" / "shot.mp4").write_bytes(b"a medium")
        (self.root / "scenes").mkdir()
        (self.root / "scenes" / "room.blend").write_bytes(b"a scene")

    def geometric(self, signal_id: str = "room-z", count: int = 5, **more) -> dict:
        return signals.record_signal(self.root, signal_id=signal_id, kind="depth", origin="geometric",
                                     frames=ramp(count), rate=24, actor=TOOL, media="plates/shot.mp4",
                                     camera="cam-a", depth=DEPTH,
                                     maker={"kind": "renderer", "name": "blender", "version": "4.2"},
                                     inputs=[{"file": "scenes/room.blend"}], **more)

    def estimated(self, signal_id: str = "shot-depth", count: int = 5) -> dict:
        frames = [np.full((H, W), 1.0 / (2.0 + index), np.float32) for index in range(count)]
        return signals.record_signal(self.root, signal_id=signal_id, kind="depth_relative", origin="estimated",
                                     frames=frames, rate=24, actor=TOOL, media="plates/shot.mp4",
                                     depth={"quantity": "inverse_z", "near_is_small": False},
                                     maker={"kind": "model", "name": "depth-anything-v2-small", "version": "1",
                                            "weights": "sha256:..."},
                                     declared=[0.8] * count)


class RecordTests(SignalCase):
    def test_values_come_back_as_recorded(self) -> None:
        self.geometric()
        reader = signals.SignalReader(self.root, "room-z")
        np.testing.assert_array_equal(reader.frame(3), ramp(5)[3])
        vectors = [np.stack([np.full((H, W), index, np.float32), np.full((H, W), -index, np.float32)], -1)
                   for index in range(3)]
        signals.record_signal(self.root, signal_id="flow", kind="vectors", origin="estimated", frames=vectors,
                              rate=24, actor=TOOL, media="plates/shot.mp4")
        np.testing.assert_array_equal(signals.frame(self.root, "flow", 2), vectors[2])
        labels = [np.arange(W * H, dtype=np.int32).reshape(H, W) % 3]
        signals.record_signal(self.root, signal_id="people", kind="segmentation", origin="estimated", frames=labels,
                              rate=24, actor=TOOL, media="plates/shot.mp4", labels={0: "room", 1: "mara", 2: "chair"})
        got = signals.frame(self.root, "people", 0)
        self.assertTrue(np.issubdtype(got.dtype, np.integer))
        np.testing.assert_array_equal(got, labels[0])
        self.assertEqual(signals.load_record(self.root, "people")["labels"], {0: "room", 1: "mara", 2: "chair"})

    def test_the_contract_is_held_when_recording(self) -> None:
        cases = {"no camera": dict(kind="depth", origin="geometric", depth=DEPTH),
                 "no unit": dict(kind="depth", origin="geometric", camera="c", depth={"quantity": "z"}),
                 "no quantity": dict(kind="depth", origin="geometric", camera="c", depth={"unit": "m"}),
                 "a relative depth with a unit": dict(kind="depth_relative", origin="estimated",
                                                     depth={"quantity": "z", "unit": "m"}),
                 "a segmentation without labels": dict(kind="segmentation", origin="estimated"),
                 "an unknown kind": dict(kind="heat", origin="estimated"),
                 "an unknown origin": dict(kind="luminance", origin="guessed")}
        for name, given in cases.items():
            with self.subTest(case=name):
                frames = [np.zeros((H, W), np.int32 if given["kind"] == "segmentation" else np.float32)]
                with self.assertRaises(ValidationError):
                    signals.record_signal(self.root, signal_id="x", frames=frames, rate=24, actor=TOOL, **given)
        with self.assertRaises(ValidationError):  # frames of two sizes
            signals.record_signal(self.root, signal_id="x", kind="luminance", origin="authored", rate=24, actor=TOOL,
                                  frames=[np.zeros((H, W), np.float32), np.zeros((H + 1, W), np.float32)])


class ProvenanceTests(SignalCase):
    def test_an_aligned_estimate_stays_estimated_and_keeps_its_history(self) -> None:
        self.geometric()
        self.estimated()
        aligned = [np.full((H, W), 3.0 + index, np.float32) for index in range(5)]
        signals.record_signal(self.root, signal_id="shot-depth-aligned", kind="depth", frames=aligned, rate=24,
                              actor=TOOL, camera="cam-a", depth=DEPTH, derived_from="shot-depth",
                              transformation={"name": "align_depth", "method": "scale_shift", "reference": "room-z",
                                              "scale": 1.7, "shift": 0.2, "residual_m": 0.04},
                              measured=[{"against": "room-z", "metric": "rmse_m", "value": 0.04,
                                         "how": "fit over the floor"}])
        record = signals.load_record(self.root, "shot-depth-aligned")
        self.assertEqual((record["kind"], record["origin"]), ("depth", "estimated"))  # a transformation, not an origin
        history = record["provenance"]
        self.assertEqual([step["step"] for step in history], ["made", "derived"])
        self.assertEqual(history[0]["maker"]["name"], "depth-anything-v2-small")
        self.assertEqual(history[1]["transformation"]["reference"], "room-z")
        pinned = {item.get("signal") for item in history[1]["inputs"]}
        self.assertTrue({"shot-depth", "room-z"} <= pinned)
        self.assertEqual(signals.status(self.root, "shot-depth-aligned")["transformations"], ["align_depth"])
        with self.assertRaises(ValidationError):  # an estimate cannot become geometric by being aligned
            signals.record_signal(self.root, signal_id="cheat", kind="depth", origin="geometric", frames=aligned,
                                  rate=24, actor=TOOL, camera="cam-a", depth=DEPTH, derived_from="shot-depth",
                                  transformation={"name": "align_depth"})
        with self.assertRaises(ValidationError):  # a derivation says what it did
            signals.record_signal(self.root, signal_id="vague", kind="depth", frames=aligned, rate=24, actor=TOOL,
                                  camera="cam-a", depth=DEPTH, derived_from="shot-depth")

    def test_quality_is_what_was_given_and_nothing_more(self) -> None:
        self.geometric()
        self.assertEqual(signals.status(self.root, "room-z")["quality"], "unknown")
        self.estimated()
        quality = signals.status(self.root, "shot-depth")["quality"]
        self.assertEqual((quality["declared"], quality["measured"]), ([0.8] * 5, []))  # declared, nothing measured
        with self.assertRaises(ValidationError):
            signals.record_signal(self.root, signal_id="bad", kind="luminance", origin="estimated",
                                  frames=ramp(3), rate=24, actor=TOOL, declared=[0.5])

    def test_recording_is_a_command_with_events(self) -> None:
        self.geometric()
        types = [event["type"] for event in tail_events(self.root)]
        self.assertIn("signal.recorded", types)


class StaleTests(SignalCase):
    def test_a_changed_medium_or_input_file_makes_it_stale_and_refused(self) -> None:
        self.geometric()
        self.assertEqual(signals.status(self.root, "room-z")["stale"], [])
        (self.root / "scenes" / "room.blend").write_bytes(b"another scene")
        self.assertTrue(any("room.blend" in reason for reason in signals.status(self.root, "room-z")["stale"]))
        with self.assertRaises(ValidationError):
            signals.SignalReader(self.root, "room-z")

    def test_staleness_runs_down_the_chain(self) -> None:
        self.geometric()
        self.estimated()
        signals.record_signal(self.root, signal_id="aligned", kind="depth", frames=ramp(5), rate=24, actor=TOOL,
                              camera="cam-a", depth=DEPTH, derived_from="shot-depth",
                              transformation={"name": "align_depth", "reference": "room-z"})
        self.assertEqual(signals.status(self.root, "aligned")["stale"], [])
        self.geometric()  # the same values recorded again: by content, nothing changed
        self.assertEqual(signals.status(self.root, "aligned")["stale"], [])
        signals.record_signal(self.root, signal_id="room-z", kind="depth", origin="geometric", frames=ramp(5, 2.0),
                              rate=24, actor=TOOL, media="plates/shot.mp4", camera="cam-a", depth=DEPTH,
                              inputs=[{"file": "scenes/room.blend"}])  # the reference, other values
        self.assertTrue(any("room-z" in reason for reason in signals.status(self.root, "aligned")["stale"]))
        signals.record_signal(self.root, signal_id="aligned", kind="depth", frames=ramp(5), rate=24, actor=TOOL,
                              camera="cam-a", depth=DEPTH, derived_from="shot-depth",
                              transformation={"name": "align_depth", "reference": "room-z"})
        self.assertEqual(signals.status(self.root, "aligned")["stale"], [])
        (self.root / "plates" / "shot.mp4").write_bytes(b"another medium")  # the medium under everything
        reasons = signals.status(self.root, "aligned")["stale"]
        self.assertTrue(any("shot.mp4" in reason or "shot-depth" in reason for reason in reasons), reasons)

    def test_data_changed_behind_its_commands_is_seen(self) -> None:
        self.geometric()
        data = next((self.root / "signals" / "room-z" / "data" / "0001").iterdir())
        data.write_bytes(data.read_bytes()[:-8] + b"tampered")
        self.assertTrue(signals.status(self.root, "room-z")["stale"])


class CorrectionTests(SignalCase):
    def test_corrections_are_kept_apart_and_reverted(self) -> None:
        self.geometric()
        before = sorted(p.read_bytes() for p in (self.root / "signals" / "room-z" / "data" / "0001").iterdir())
        where = np.zeros((H, W), bool)
        where[2:4, 2:6] = True
        signals.correct_signal(self.root, signal_id="room-z", frame=1, where=where,
                               values=np.full((H, W), 9.0, np.float32), actor=PERSON, note="a hole in the pass")
        corrected = signals.frame(self.root, "room-z", 1)
        self.assertEqual((float(corrected[3, 3]), float(corrected[0, 0])), (9.0, 2.0))
        after = sorted(p.read_bytes() for p in (self.root / "signals" / "room-z" / "data" / "0001").iterdir())
        self.assertEqual(before, after)  # the data untouched
        signals.revert_signal_corrections(self.root, signal_id="room-z", frame=1, actor=PERSON)
        self.assertEqual(float(signals.frame(self.root, "room-z", 1)[3, 3]), 2.0)
        kept = json.loads((self.root / "signals" / "room-z" / "corrections" / "corrections.json").read_text())
        self.assertEqual([item["active"] for item in kept], [False])


class GraphTests(SignalCase):
    def read(self, nodes: dict, frames: int = 4, origins: dict | None = None, size=(W, H)) -> np.ndarray:
        graph = {"ports": {"plate": "picture"}, "output": "out", "nodes": nodes}
        self.assertEqual(validate(graph), [])
        plate = np.zeros((10, size[1], size[0], 4), np.float32)
        return evaluate(graph, {"plate": plate}, frames=frames, size=size, fps=24, root=self.root,
                        origins=origins or {"plate": Fraction(0)})

    def depth_to_picture(self, extra: dict | None = None, **read) -> dict:
        return {"z": {"op": "signal.read", "signal": "room-z", "kind": "depth", "camera": "cam-a", **read},
                "m": {"op": "matte.from_signal", "signal": "z", "low": 0.0, "high": 10.0},
                "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
                **(extra or {}), "out": {"op": "merge.over", "front": "white", "back": "plate", "matte": "m"}}

    def values(self, out: np.ndarray) -> list[int]:
        return [round(float(frame[0, 0, 3]) * 10) for frame in out]

    def test_read_frame_by_frame_and_at_the_instant_its_medium_shows(self) -> None:
        self.geometric(count=10)
        self.assertEqual(self.values(self.read(self.depth_to_picture())), [1, 2, 3, 4])
        # Read where its medium is shown: the shot cut later, then retimed.
        self.assertEqual(self.values(self.read(self.depth_to_picture(of="plate"), origins={"plate": Fraction(3, 24)})),
                         [4, 5, 6, 7])
        retimed = self.depth_to_picture(extra={"k": {"op": "curve.keys", "keys": [[0, 0], [1, 2]]},
                                               "fast": {"op": "time.remap", "in": "plate", "map": {"curve": "k"}}},
                                        of="plate")
        retimed["out"]["back"] = "fast"
        self.assertEqual(self.values(self.read(retimed)), [2, 4, 6, 8])

    def test_what_the_node_says_must_be_what_the_record_is(self) -> None:
        self.geometric()
        with self.assertRaises(ValidationError):
            self.read(self.depth_to_picture() | {"z": {"op": "signal.read", "signal": "room-z", "kind": "depth",
                                                       "camera": "cam-b"}})
        self.estimated()
        with self.assertRaises(ValidationError):
            self.read(self.depth_to_picture() | {"z": {"op": "signal.read", "signal": "shot-depth", "kind": "depth",
                                                       "camera": "cam-a"}})

    def test_a_relative_depth_is_refused_where_metric_depth_is_needed(self) -> None:
        graph = {"ports": {"a": "picture", "b": "picture"}, "output": "out", "nodes": {
            "za": {"op": "signal.read", "signal": "x", "kind": "depth_relative"},
            "zb": {"op": "signal.read", "signal": "y", "kind": "depth", "camera": "cam-a"},
            "out": {"op": "merge.depth", "pictures": ["a", "b"], "depths": ["za", "zb"]}}}
        self.assertTrue(validate(graph))  # SPEC-0012: a relative depth is not compared

    def test_labels_are_resized_to_the_nearest_never_blended(self) -> None:
        labels = [(np.indices((H, W)).sum(axis=0) % 3).astype(np.int32)]
        signals.record_signal(self.root, signal_id="people", kind="segmentation", origin="estimated", frames=labels,
                              rate=24, actor=TOOL, media="plates/shot.mp4", labels={0: "a", 1: "b", 2: "c"})
        graph = {"ports": {"plate": "picture"}, "output": "out", "nodes": {
            "s": {"op": "signal.read", "signal": "people", "kind": "segmentation"},
            "m": {"op": "matte.label", "signal": "s", "labels": [1]},
            "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
            "out": {"op": "merge.over", "front": "white", "back": "plate", "matte": "m"}}}
        out = evaluate(graph, {"plate": np.zeros((2, 27, 48, 4), np.float32)}, frames=1, size=(48, 27), fps=24,
                       root=self.root)
        self.assertEqual(set(np.unique(out[0, ..., 3]).round(4)), {0.0, 1.0})  # whole labels, no in-betweens

    def test_one_signal_serves_two_readers(self) -> None:
        self.geometric(count=10)
        nodes = self.depth_to_picture()
        nodes["z2"] = {"op": "signal.read", "signal": "room-z", "kind": "depth", "camera": "cam-a", "of": "plate"}
        nodes["m2"] = {"op": "matte.from_signal", "signal": "z2", "low": 0.0, "high": 10.0}
        nodes["out"] = {"op": "merge.over", "front": "white", "back": "plate", "matte": "m2"}
        nodes["first"] = {"op": "merge.over", "front": "white", "back": "plate", "matte": "m"}
        self.assertEqual(self.values(self.read(nodes)), [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
