"""SPEC-0012: the example graphs are valid, and the mistakes it must catch are caught."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from cine_toaster.compositing.schema import OPS, validate

EXAMPLES = Path(__file__).parents[1] / "ai-context" / "specs" / "SPEC-0012-examples"


class ExampleTests(unittest.TestCase):
    def test_every_example_is_a_valid_graph(self) -> None:
        files = sorted(EXAMPLES.glob("*.yaml"))
        self.assertGreaterEqual(len(files), 15)
        for path in files:
            with self.subTest(example=path.name):
                self.assertEqual(validate(yaml.safe_load(path.read_text())), [])

    def test_every_invalid_example_is_refused_for_its_reason(self) -> None:
        files = sorted((EXAMPLES / "invalid").glob("*.yaml"))
        self.assertGreaterEqual(len(files), 5)
        for path in files:
            with self.subTest(example=path.name):
                graph = yaml.safe_load(path.read_text())
                codes = [code for code, _ in validate(graph)]
                self.assertIn(graph["expect"], codes, codes)

    def test_the_examples_use_every_primitive_family(self) -> None:
        used = {node["op"].split(".")[0] for path in EXAMPLES.glob("*.yaml")
                for node in yaml.safe_load(path.read_text())["nodes"].values()}
        self.assertTrue({"signal", "matte", "merge", "warp", "filter", "time", "generate", "track", "curve",
                         "opaque"} <= used, used)


class SchemaTests(unittest.TestCase):
    def test_a_curve_can_drive_a_number_but_not_a_choice(self) -> None:
        graph = {"ports": {"progress": "curve", "a": "picture"},
                 "nodes": {"out": {"op": "filter.blur", "in": "a", "kind": {"curve": "progress"}}}, "output": "out"}
        self.assertIn("composite_type_mismatch", [code for code, _ in validate(graph)])
        graph["nodes"]["out"] = {"op": "filter.blur", "in": "a", "radius": {"curve": "progress"}}
        self.assertEqual(validate(graph), [])

    def test_a_picture_may_be_taken_as_its_alpha_matte_and_nothing_else_converts(self) -> None:
        graph = {"ports": {"a": "picture", "b": "picture", "s": "signal"},
                 "nodes": {"out": {"op": "merge.over", "front": "a", "back": "b", "matte": "a"}}, "output": "out"}
        self.assertEqual(validate(graph), [])
        graph["nodes"]["out"]["matte"] = "s"
        self.assertIn("composite_type_mismatch", [code for code, _ in validate(graph)])

    def test_every_op_is_named_by_its_primitive(self) -> None:
        families = {"signal", "matte", "merge", "warp", "colour", "filter", "time", "generate", "track", "curve"}
        self.assertEqual({name.split(".")[0] for name in OPS}, families)


class SignalKindTests(unittest.TestCase):
    """Signals of different kinds are not interchangeable where an op says which it takes."""

    def check(self, nodes: dict, output: str = "out", ports: dict | None = None) -> list[str]:
        return [code for code, _ in validate({"ports": ports or {"p": "picture"}, "nodes": nodes, "output": output})]

    def test_depth_and_relative_depth_go_only_where_they_belong(self) -> None:
        relative = {"op": "signal.estimate", "picture": "p", "kind": "depth_relative", "model": "m"}
        metric = {"op": "signal.read", "file": "z.exr", "kind": "depth", "camera": "shot"}
        merged = {"op": "merge.depth", "pictures": ["p", "p"], "depths": ["metric", "metric"]}
        self.assertEqual(self.check({"metric": metric, "out": merged}), [])
        # Relative depth is refused by merge.depth, and metric depth is refused where only relative is aligned.
        self.assertIn("composite_type_mismatch",
                      self.check({"guess": relative, "out": {**merged, "depths": ["guess", "guess"]}}))
        self.assertIn("composite_type_mismatch", self.check(
            {"metric": metric, "aligned": {"op": "signal.align_depth", "signal": "metric"}, "out": merged}))
        self.assertEqual(self.check({"guess": relative, "metric": metric,
                                     "aligned": {"op": "signal.align_depth", "signal": "guess", "reference": "metric"},
                                     "out": {**merged, "depths": ["aligned", "metric"]}}), [])

    def test_labels_come_only_from_a_segmentation(self) -> None:
        luma = {"op": "signal.luma", "picture": "p"}
        label = {"op": "matte.label", "signal": "luma", "labels": [1]}
        over = {"op": "merge.over", "front": "p", "back": "p", "matte": "label"}
        self.assertIn("composite_type_mismatch", self.check({"luma": luma, "label": label, "out": over}))
        segments = {"op": "signal.estimate", "picture": "p", "kind": "segmentation", "model": "m"}
        self.assertEqual(self.check({"luma": segments, "label": label, "out": over}), [])

    def test_depths_are_compared_one_per_picture_and_within_one_camera(self) -> None:
        def depth(camera: str) -> dict:
            return {"op": "signal.read", "file": "z.exr", "kind": "depth", **({"camera": camera} if camera else {})}

        merged = {"op": "merge.depth", "pictures": ["p", "p"], "depths": ["a", "b"]}
        self.assertEqual(self.check({"a": depth("shot"), "b": depth("shot"), "out": merged}), [])
        self.assertIn("composite_type_mismatch", self.check({"a": depth("shot"), "b": depth("other"), "out": merged}))
        self.assertIn("composite_param_missing", self.check({"a": depth(""), "b": depth("shot"), "out": merged}))
        self.assertIn("composite_type_mismatch",
                      self.check({"a": depth("shot"), "b": depth("shot"), "out": {**merged, "pictures": ["p"]}}))


class RequiredTests(unittest.TestCase):
    def codes(self, nodes: dict) -> list[str]:
        return [code for code, _ in validate({"ports": {"p": "picture", "progress": "curve"}, "nodes": nodes,
                                              "output": "out"})]

    def test_an_op_without_what_it_cannot_run_without_is_refused(self) -> None:
        self.assertIn("composite_param_missing", self.codes(
            {"z": {"op": "signal.read", "kind": "depth"}, "out": {"op": "warp.displace", "in": "p", "map": "z"}}))
        self.assertIn("composite_param_missing", self.codes({"out": {"op": "generate.source"}}))
        self.assertEqual(self.codes({"out": {"op": "generate.source", "file": "a.mov"}}), [])

    def test_an_opaque_node_is_checked_against_the_ports_its_renderer_declares(self) -> None:
        good = {"out": {"op": "opaque.gl", "shader": "cube", "from": "p", "to": "p", "progress": "progress"}}
        self.assertEqual(self.codes(good), [])
        self.assertIn("composite_input_missing", self.codes({"out": {"op": "opaque.gl", "shader": "cube", "from": "p"}}))
        self.assertIn("composite_type_mismatch",
                      self.codes({"out": {**good["out"], "progress": "p"}}))
        self.assertIn("composite_unknown_op", self.codes({"out": {"op": "opaque.unreal"}}))


class KeyTests(unittest.TestCase):
    def codes(self, key: dict) -> list[str]:
        graph = {"ports": {"p": "picture", "plate": "picture"},
                 "nodes": {"k": {"op": "matte.key", "picture": "p", **key},
                           "out": {"op": "merge.over", "front": "p", "back": "plate", "matte": "k"}}, "output": "out"}
        return [code for code, _ in validate(graph)]

    def test_each_way_of_keying_needs_its_own_parameters(self) -> None:
        self.assertEqual(self.codes({"by": "luminance", "low": 0.7, "high": 0.9}), [])
        self.assertEqual(self.codes({"by": "colour", "colour": [0, 1, 0], "tolerance": 0.2}), [])
        self.assertEqual(self.codes({"by": "difference", "reference": "plate", "tolerance": 0.1}), [])
        for key in ({"by": "luminance", "low": 0.7}, {"by": "colour", "tolerance": 0.2},
                    {"by": "difference", "tolerance": 0.1}, {"low": 0.2, "high": 0.8}):
            with self.subTest(key=key):
                self.assertIn("composite_param_missing", self.codes(key))

if __name__ == "__main__":
    unittest.main()
