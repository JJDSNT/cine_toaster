from __future__ import annotations

import unittest
from pathlib import Path

from cine_toaster.project import load_production, load_scene


DEMO_PROJECT = Path(__file__).parents[1] / "examples" / "demo-project"


class ProjectTests(unittest.TestCase):
    def test_loads_operational_demo(self) -> None:
        production = load_production(DEMO_PROJECT)

        self.assertEqual(production["title"], "The Last Signal")
        self.assertEqual(production["metrics"]["total_scenes"], 6)
        self.assertEqual(production["active_scene"]["id"], "SC-030")
        self.assertGreaterEqual(production["metrics"]["attention_items"], 2)

    def test_loads_scene_workflow_and_iterations(self) -> None:
        scene = load_scene(DEMO_PROJECT, "SC-030")

        self.assertIsNotNone(scene)
        assert scene is not None
        self.assertEqual(scene["current_step"], "review")
        self.assertEqual(len(scene["workflow"]), 6)
        self.assertEqual(len(scene["iterations"]), 3)
        self.assertEqual(scene["shots"][1]["status"], "needs_review")


if __name__ == "__main__":
    unittest.main()
