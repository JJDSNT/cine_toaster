"""A scene entered on action is bridged: the shot before it ends on its first master (Demo 01, 2026-10-18)."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from cine_toaster.generation import entry_bridge
from cine_toaster.project import load_production
from cine_toaster.takes import work_directory_for

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class EntryBridgeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / "film"
        shutil.copytree(DEMO, self.root)
        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene.write_text(scene.read_text().replace("\nshots:", "\nenter:\n  type: action\n  reason: carried on.\nshots:", 1))

    def last_of_first_scene(self, production):
        first = next(item for item in production["scenes"] if item["id"] == "SC-010")
        moving = [shot for shot in first["shots"] if shot.get("source") != "composed" and shot.get("kind") != "title"]
        return first, moving[-1]["id"]

    def test_off_unless_the_film_asks_for_it(self):
        production = load_production(self.root)
        scene, shot = self.last_of_first_scene(production)
        self.assertIsNone(entry_bridge(self.root, production, scene, shot))

    def test_the_last_shot_ends_on_the_next_scenes_first_master(self):
        manifest = self.root / "project.yaml"
        manifest.write_text(manifest.read_text() + "\nclips:\n  end_on_entry: true\n")
        production = load_production(self.root)
        following = next(item for item in production["scenes"] if item["id"] == "SC-030")
        work = work_directory_for(self.root / following["file"])
        work.mkdir(parents=True, exist_ok=True)
        number = int(following["shots"][0]["number"])
        Image.new("RGB", (160, 90), "white").save(work / f"p{number:02d}.png")
        scene, shot = self.last_of_first_scene(production)
        bridge = entry_bridge(self.root, production, scene, shot)
        self.assertIsNotNone(bridge)
        self.assertEqual((bridge["scene"], bridge["shot"]), ("SC-030", following["shots"][0]["id"]))
        self.assertIn("transforms", bridge["text"])
        first_shot = scene["shots"][0]["id"]
        if first_shot != shot:
            self.assertIsNone(entry_bridge(self.root, production, scene, first_shot))  # only the scene's last shot


if __name__ == "__main__":
    unittest.main()
