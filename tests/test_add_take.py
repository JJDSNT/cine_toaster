"""Bringing a recording or a still in as a take, with where it came from (CT-0065)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cine_toaster.commands import add_take
from cine_toaster.errors import ValidationError
from cine_toaster.project import load_production
from cine_toaster.state import Actor

ACTOR = Actor(id="tester")


class AddTakeTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "film"
        (self.root / "scenes" / "010").mkdir(parents=True)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
        (self.root / "scenes" / "010" / "scene.yaml").write_text(
            "scene: S1\nshots:\n  - n: 2\n    source: archival\n    duration: 3\n    label: A launch.\n")
        self.clip = Path(directory.name) / "Launch Pad.mp4"
        self.clip.write_bytes(b"not really a film")

    def add(self, **options):
        return add_take(self.root, scene_id="S1", shot_id="P2", source=self.clip, actor=ACTOR, **options)

    def takes(self) -> list[dict]:
        return load_production(self.root)["scenes"][0]["shots"][0]["takes"]

    def test_the_first_take_is_the_one_in_the_cut_and_carries_its_origin(self) -> None:
        result = self.add(kind="archival", origin="https://example.org/launch", licence="CC0 1.0", credit="An Agency")
        self.assertEqual((result.type, result.take_id), ("take.added", "CUT"))
        take = self.takes()[0]
        self.assertEqual(take["media"], "scenes/010/work/c02.mp4")
        origin = take["provenance"]["origin"]
        self.assertEqual((origin["kind"], origin["licence"], origin["credit"]), ("archival", "CC0 1.0", "An Agency"))
        self.assertEqual(len(origin["sha256"]), 64)
        self.assertEqual(self.clip.read_bytes(), (self.root / take["media"]).read_bytes())

    def test_a_second_take_is_an_alternative_and_nothing_is_replaced(self) -> None:
        self.add()
        second = self.add(name="Wide angle")
        self.assertEqual(second.take_id, "WIDE-ANGLE")
        self.assertEqual(sorted(take["media"] for take in self.takes()),
                         ["scenes/010/work/_takes/c02-wide-angle.mp4", "scenes/010/work/c02.mp4"])
        with self.assertRaises(ValidationError):
            self.add(name="wide angle")

    def test_archival_footage_without_a_source_and_a_licence_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            self.add(kind="archival", origin="https://example.org/launch")
        self.assertEqual(self.takes(), [])
        self.assertFalse((self.root / "scenes" / "010" / "work").exists())

    def test_a_file_that_is_not_a_picture_or_a_clip_is_refused(self) -> None:
        self.clip = self.clip.with_suffix(".txt")
        self.clip.write_text("notes")
        with self.assertRaises(ValidationError):
            self.add()


if __name__ == "__main__":
    unittest.main()
