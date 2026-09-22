"""The half of the interface that asks what a scene is, not whether it is good."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.project import (
    discover_renders,
    discover_stills,
    load_production,
    writing_room,
)


EXAMPLES = Path(__file__).parents[1] / "examples"


class DiscoveryTests(unittest.TestCase):
    """Renders and stills are found on disk, never declared -- as takes are."""

    def test_a_render_that_exists_is_a_render_the_interface_shows(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "renders").mkdir()
            (root / "renders" / "reel.mp4").write_bytes(b"video")
            (root / "renders" / "notes.txt").write_text("ignored", encoding="utf-8")
            found = discover_renders(root)
        self.assertEqual([item["name"] for item in found], ["reel"])
        self.assertEqual(found[0]["path"], "renders/reel.mp4")
        self.assertEqual(found[0]["size_bytes"], 5)

    def test_no_renders_directory_is_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(discover_renders(Path(raw)), [])

    def test_stills_are_found_per_scene_and_keyed_by_shot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "stills" / "SC-010").mkdir(parents=True)
            (root / "stills" / "SC-010" / "P1.png").write_bytes(b"png")
            (root / "stills" / "SC-010" / "P2.png").write_bytes(b"png")
            stills = discover_stills(root, "SC-010")
            self.assertEqual(sorted(stills), ["P1", "P2"])
            self.assertEqual(stills["P1"], "stills/SC-010/P1.png")
            self.assertEqual(discover_stills(root, "SC-999"), {})

    def test_a_shot_carries_its_still(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "reel"
            shutil.copytree(EXAMPLES / "amiga-demo-reel", root)
            (root / "stills" / "SC-020").mkdir(parents=True)
            (root / "stills" / "SC-020" / "P1.png").write_bytes(b"png")
            scene = next(
                s for s in load_production(root)["scenes"] if s["id"] == "SC-020"
            )
        self.assertEqual(scene["shots"][0]["still"], "stills/SC-020/P1.png")


class WritingRoomTests(unittest.TestCase):
    def test_the_reel_reports_its_frames_lines_and_speakers(self) -> None:
        data = writing_room(EXAMPLES / "amiga-demo-reel")
        self.assertEqual(data["counts"]["scenes"], 4)
        self.assertEqual(data["counts"]["frames"], 7)
        self.assertEqual(data["counts"]["lines"], 1)
        self.assertEqual(data["counts"]["speakers"], 1)
        self.assertEqual(data["cast"][0]["who"], "NARRATOR")
        self.assertEqual(data["cast"][0]["scenes"], ["SC-010"])

    def test_the_cast_is_counted_from_the_lines_themselves(self) -> None:
        """Nothing declares a speaker; the dialogue is the declaration."""

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "scenes" / "010").mkdir(parents=True)
            (root / "project.yaml").write_text("id: x\ntitle: X\n", encoding="utf-8")
            (root / "scenes" / "010" / "scene.yaml").write_text(
                "scene: SC-010\nshots:\n"
                "  - n: 1\n    duration: 2\n    label: A.\n"
                "    lines:\n"
                "      - {who: MARA, text: One.}\n"
                "      - {who: MARA, text: Two.}\n"
                "      - {who: STATION, text: Three.}\n",
                encoding="utf-8",
            )
            data = writing_room(root)
        self.assertEqual(data["counts"]["lines"], 3)
        self.assertEqual([member["who"] for member in data["cast"]], ["MARA", "STATION"])
        self.assertEqual(data["cast"][0]["lines"], 2)

    def test_the_screenplay_is_read_when_the_production_points_at_one(self) -> None:
        data = writing_room(EXAMPLES / "demo-project")
        self.assertEqual(data["script_path"], "story/screenplay.fountain")
        self.assertIn("The Last Signal", data["screenplay"])

    def test_a_production_with_no_screenplay_says_so_rather_than_failing(self) -> None:
        data = writing_room(EXAMPLES / "amiga-demo-reel")
        self.assertEqual(data["script_path"], "")
        self.assertEqual(data["screenplay"], "")
        # The direction written on each scene is what it has instead.
        self.assertTrue(any(scene["direction"] for scene in data["scenes"]))

    def test_open_questions_are_the_decisions_with_no_answer(self) -> None:
        data = writing_room(EXAMPLES / "demo-project")
        scene = next(s for s in data["scenes"] if s["id"] == "SC-030")
        self.assertEqual(len(scene["decisions"]), 2)
        self.assertEqual(len(scene["open_questions"]), 1)
        self.assertIn("intelligible", scene["open_questions"][0]["question"])

    def test_a_frame_carries_what_the_storyboard_needs(self) -> None:
        data = writing_room(EXAMPLES / "amiga-demo-reel")
        scene = next(s for s in data["scenes"] if s["id"] == "SC-030")
        frame = scene["frames"][1]
        self.assertEqual(frame["shot_id"], "P2")
        self.assertEqual(frame["source"], "composed")
        self.assertEqual(frame["transition"]["id"], "cross-dissolve")
        self.assertIn("still", frame)


if __name__ == "__main__":
    unittest.main()
