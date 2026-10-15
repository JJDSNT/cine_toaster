"""A production says its frame once; every version is made in it (CT-0068)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cine_toaster.formats import parse_frame
from cine_toaster.project import load_production


class ParseTests(unittest.TestCase):
    def test_the_ways_a_frame_is_written(self) -> None:
        self.assertEqual(parse_frame("1920x1080@29.97"), ({"width": 1920, "height": 1080, "fps": 29.97}, ""))
        self.assertEqual(parse_frame("1920x1080"), ({"width": 1920, "height": 1080, "fps": None}, ""))
        self.assertEqual(parse_frame({"width": 1280, "height": 720, "fps": "30000/1001"})[0]["fps"], 29.97)
        self.assertEqual(parse_frame(None), (None, ""))

    def test_a_frame_that_cannot_be_made_is_refused(self) -> None:
        for raw in ("1921x1080", "big", {"width": 0, "height": 1080}, "1920x1080@0", "1920x1080@fast"):
            with self.subTest(raw=raw):
                frame, problem = parse_frame(raw)
                self.assertIsNone(frame)
                self.assertTrue(problem)


class ProductionTests(unittest.TestCase):
    def production(self, frame: str) -> dict:
        root = Path(tempfile.mkdtemp())
        (root / "project.yaml").write_text(f"id: t\ntitle: T\nframe: {frame}\npaths:\n  scenes: scenes\n")
        (root / "scenes" / "010").mkdir(parents=True)
        (root / "scenes" / "010" / "scene.yaml").write_text("scene: S1\nshots:\n  - {n: 1, duration: 2}\n")
        return load_production(root)

    def test_every_scene_carries_the_productions_frame(self) -> None:
        loaded = self.production('"1920x1080@25"')
        self.assertEqual(loaded["frame"], {"width": 1920, "height": 1080, "fps": 25.0})
        self.assertEqual(loaded["scenes"][0]["frame"], loaded["frame"])

    def test_a_frame_that_cannot_be_read_is_put_to_the_production(self) -> None:
        loaded = self.production("huge")
        self.assertIsNone(loaded["frame"])
        self.assertEqual([item["kind"] for item in loaded["attention"]], ["frame"])


if __name__ == "__main__":
    unittest.main()
