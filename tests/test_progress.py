"""The production strip says what holds the film up, from its records (Demo 01, 2026-10-18)."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.progress import production_progress

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class ProgressTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / "film"
        shutil.copytree(DEMO, self.root)

    def phases(self):
        return {item["id"]: item for item in production_progress(self.root)["phases"]}

    def test_a_film_whose_masters_come_from_the_storyboard_does_not_need_a_blockout(self):
        manifest = self.root / "project.yaml"
        manifest.write_text(manifest.read_text() + "\npictures:\n  provider: codex-image\n  derive:\n"
                            "    from: storyboard\n    request: Finish the drawing.\n")
        phases = self.phases()
        self.assertEqual(phases["blockout"]["state"], "skipped")
        self.assertIn("storyboard", phases["blockout"]["summary"])

    def test_without_a_way_to_make_masters_the_blockout_is_counted(self):
        self.assertNotEqual(self.phases()["blockout"]["state"], "skipped")


if __name__ == "__main__":
    unittest.main()
