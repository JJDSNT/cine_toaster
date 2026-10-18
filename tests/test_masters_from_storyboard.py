"""Masters finished from the storyboard: a film-wide derive, the drawing as source, and a run with no video."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from cine_toaster.project import load_production
from cine_toaster.state import Actor
from cine_toaster.storyboard import load_storyboard, register_storyboard_candidate

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class MastersFromStoryboardTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / "film"
        shutil.copytree(DEMO, self.root)
        manifest = self.root / "project.yaml"
        text = manifest.read_text()
        self.assertNotIn("\npictures:", text)
        manifest.write_text(text + "\npictures:\n  provider: codex-image\n  derive:\n    from: storyboard\n"
                            "    request: Finish the drawing.\n")
        self.picture = Path(folder.name) / "board.png"
        Image.new("RGB", (64, 36), "white").save(self.picture)

    def draw(self, scene, shot, based_on=""):
        return register_storyboard_candidate(self.root, scene=scene, shot=shot, image=self.picture, title=f"{scene} {shot}",
                                             expected_revision=load_storyboard(self.root)["revision"],
                                             actor=Actor(id="director", kind="human"), based_on=based_on)["candidate"]

    def test_every_shot_inherits_the_film_wide_derive_with_its_own_label(self):
        scene = next(item for item in load_production(self.root)["scenes"] if item["id"] == "SC-010")
        self.assertIsNone(scene["shots"][0]["derive"])  # a black card is composed: no picture to make
        shot = scene["shots"][1]
        self.assertEqual(shot["derive"]["from"], "storyboard")
        self.assertEqual(shot["derive"]["inherited"], "production")
        self.assertTrue(shot["derive"]["request"].startswith("Finish the drawing. This shot: "))

    def test_the_source_is_the_latest_drawing_and_a_missing_one_is_said(self):
        from cine_toaster.errors import ValidationError
        from cine_toaster.pictures import plan_picture

        production = load_production(self.root)
        with self.assertRaisesRegex(ValidationError, "storyboard drawing"):
            plan_picture(self.root, production, "SC-010", "P2")
        first = self.draw("SC-010", "P2")
        second = self.draw("SC-010", "P2", based_on=first["id"])
        plan = plan_picture(self.root, load_production(self.root), "SC-010", "P2")
        self.assertEqual(plan.source, self.root / second["image"]["path"])
        self.assertEqual(plan.provider, "codex-image")

    def test_a_masters_run_asks_for_every_picture_and_generates_no_video(self):
        from cine_toaster.workflows import _master_steps

        scene = next(item for item in load_production(self.root)["scenes"] if item["id"] == "SC-010")
        steps = _master_steps(scene)
        self.assertEqual({step["kind"] for step in steps}, {"picture", "gate"})
        self.assertEqual(len(steps), 2 * len([s for s in scene["shots"] if s.get("derive")]))


if __name__ == "__main__":
    unittest.main()
