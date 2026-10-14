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


if __name__ == "__main__":
    unittest.main()
