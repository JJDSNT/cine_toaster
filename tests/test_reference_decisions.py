"""What a shot is made from, decided in the runtime over the breakdown, without rewriting it (CT-0046)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.commands import dispatch
from cine_toaster.errors import RevisionConflictError, ValidationError
from cine_toaster.graph import production_graph
from cine_toaster.project import load_production, load_scene

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HUMAN = {"id": "director", "kind": "human"}


class ReferenceDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        self.addCleanup(self._restore)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        self.scene_file = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        # P3's picture is derived from P2's, with Mara's face; P2 reuses P1's.
        text = self.scene_file.read_text(encoding="utf-8")
        text = text.replace("  - n: 2\n", "  - n: 2\n    from: 1\n", 1)
        text = text.replace("  - n: 3\n", "  - n: 3\n    derive: {from: 2, with: [MARA], request: Her face lit by the stack}\n", 1)
        self.scene_file.write_text(text, encoding="utf-8")
        self.authored = self.scene_file.read_bytes()

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def shot(self, shot_id: str) -> dict:
        return next(item for item in load_scene(self.root, "SC-030")["shots"] if item["id"] == shot_id)

    def set(self, shot_id: str, **payload) -> None:
        dispatch(self.root, "set_reference", {"scene_id": "SC-030", "shot_id": shot_id, "actor": HUMAN, **payload})

    def test_a_decided_reference_is_the_reference_and_the_breakdown_is_untouched(self) -> None:
        self.assertEqual(self.shot("P3")["derive"]["from"], "2")
        self.set("P3", **{"from": "P1", "with": [], "rationale": "The wide frame holds the stack"})
        shot = self.shot("P3")
        self.assertEqual(shot["derive"]["from"], "1")  # the shot id is written as the breakdown writes it
        self.assertEqual(shot["derive"]["with"], [])
        self.assertEqual(shot["derive"]["request"], "Her face lit by the stack")
        self.assertEqual([item["ref"] for item in shot["from"]], ["1"])
        self.assertEqual([item["ref"] for item in shot["authored_from"]], ["2"])
        self.assertEqual(shot["authored_with"], ["MARA"])
        self.assertEqual(self.scene_file.read_bytes(), self.authored)

        graph = production_graph(load_production(self.root), self.root)
        lineage = {edge["id"]: edge for edge in graph["edges"] if edge["type"] == "lineage"}
        self.assertIn("from:SC-030/P1-P3", lineage)
        self.assertTrue(lineage["from:SC-030/P1-P3"]["data"]["decided"])
        self.assertNotIn("from:SC-030/P2-P3", lineage)
        self.assertIn("from:SC-030/P1-P2", lineage)
        node = next(item for item in graph["nodes"] if item["id"] == "shot:SC-030/P3")
        self.assertTrue(node["data"]["reference_decided"])
        self.assertEqual(node["data"]["authored_from"], ["2"])

        dispatch(self.root, "clear_reference", {"scene_id": "SC-030", "shot_id": "P3", "actor": HUMAN})
        shot = self.shot("P3")
        self.assertEqual((shot["derive"]["from"], shot["derive"]["with"]), ("2", ["MARA"]))
        kinds = [entry["kind"] for entry in load_scene(self.root, "SC-030")["decision_log"]]
        self.assertEqual(kinds[:2], ["reference.cleared", "reference.set"])

    def test_the_cast_alone_can_be_changed(self) -> None:
        self.set("P3", **{"with": ["SPEAKER", "MARA"]})
        shot = self.shot("P3")
        self.assertEqual((shot["derive"]["from"], shot["derive"]["with"]), ("2", ["SPEAKER", "MARA"]))

    def test_what_cannot_be_decided_is_refused(self) -> None:
        with self.assertRaisesRegex(ValidationError, "made from itself"):
            self.set("P2", **{"from": "2"})
        # P1 made from P3 would close a loop: P3 <- P2 <- P1 <- P3.
        with self.assertRaisesRegex(ValidationError, "made from itself, through"):
            self.set("P1", **{"from": "P3"})
        with self.assertRaisesRegex(ValidationError, "neither a shot"):
            self.set("P2", **{"from": "nowhere.png"})
        with self.assertRaisesRegex(ValidationError, "not a derived picture"):
            self.set("P2", **{"with": ["MARA"]})
        with self.assertRaisesRegex(ValidationError, "no cast sheet"):
            self.set("P3", **{"with": ["NOBODY"]})
        with self.assertRaisesRegex(ValidationError, "were not decided here"):
            dispatch(self.root, "clear_reference", {"scene_id": "SC-030", "shot_id": "P2", "actor": HUMAN})
        with self.assertRaises(RevisionConflictError):
            self.set("P2", **{"from": "P1", "expected_revision": 7})
        self.assertEqual(self.scene_file.read_bytes(), self.authored)


if __name__ == "__main__":
    unittest.main()
