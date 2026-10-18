"""A sequence's storyboard in time: latest drawing per shot, declared order and durations."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from cine_toaster.state import Actor
from cine_toaster.storyboard import load_storyboard, register_storyboard_candidate
from cine_toaster.storyboard_animatic import plan

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class AnimaticPlanTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / "film"
        shutil.copytree(DEMO, self.root)
        self.picture = Path(folder.name) / "board.png"
        Image.new("RGB", (64, 36), "white").save(self.picture)

    def draw(self, scene, shot, based_on=""):
        return register_storyboard_candidate(self.root, scene=scene, shot=shot, image=self.picture, title=f"{scene} {shot}",
                                             expected_revision=load_storyboard(self.root)["revision"],
                                             actor=Actor(id="director", kind="human"), based_on=based_on)["candidate"]

    def test_every_shot_in_order_with_its_latest_drawing_and_missing_ones_shown(self):
        first = self.draw("SC-010", "P1")
        second = self.draw("SC-010", "P1", based_on=first["id"])
        shots = plan(self.root, "the-reply")
        self.assertEqual([(item["scene"], item["shot"]) for item in shots],
                         [("SC-010", "P1"), ("SC-010", "P2"), ("SC-030", "P1"), ("SC-030", "P2"), ("SC-030", "P3")])
        self.assertEqual(shots[0]["board"], second["id"])  # the latest version, not the first
        self.assertIsNone(shots[1]["image"])               # no drawing yet: kept in the timeline, marked
        self.assertTrue(all(item["seconds"] > 0 for item in shots))


if __name__ == "__main__":
    unittest.main()
