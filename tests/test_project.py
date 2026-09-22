from __future__ import annotations

import unittest
from pathlib import Path

from cine_toaster.project import load_production, load_scene


DEMO_PROJECT = Path(__file__).parents[1] / "examples" / "demo-project"
AMIGA_DEMO_PROJECT = Path(__file__).parents[1] / "examples" / "amiga-demo-reel"


class ProjectTests(unittest.TestCase):
    def test_reads_the_production_straight_from_its_files(self) -> None:
        production = load_production(DEMO_PROJECT)

        self.assertEqual(production["id"], "the-last-signal")
        self.assertEqual(production["title"], "The Last Signal")
        self.assertEqual(production["metrics"]["total_scenes"], 2)
        self.assertEqual(production["active_scene"]["id"], "SC-030")

    def test_takes_are_discovered_from_disk_not_declared(self) -> None:
        scene = load_scene(DEMO_PROJECT, "SC-030")
        assert scene is not None
        shot = next(item for item in scene["shots"] if item["id"] == "P1")

        self.assertEqual(
            sorted(take["id"] for take in shot["takes"]),
            ["CUT", "HARD-CUT-IN", "LONGER-HOLD"],
        )
        self.assertTrue(all(take["media"] for take in shot["takes"]))
        self.assertEqual(shot["status"], "needs_review")

    def test_a_rejected_take_is_read_from_its_folder_and_its_name(self) -> None:
        scene = load_scene(DEMO_PROJECT, "SC-030")
        assert scene is not None
        shot = next(item for item in scene["shots"] if item["id"] == "P2")
        rejected = next(take for take in shot["takes"] if take["id"] == "LOOKS-AT-CAMERA")

        self.assertEqual(rejected["status"], "rejected")
        self.assertFalse(rejected["selectable"])
        self.assertEqual(rejected["note"], "Looks at camera")

    def test_cameras_are_assigned_from_the_geography_plan(self) -> None:
        scene = load_scene(DEMO_PROJECT, "SC-030")
        assert scene is not None
        cameras = {shot["id"]: shot["camera"] for shot in scene["shots"]}
        self.assertEqual(cameras, {"P1": "CAM-B", "P2": "CAM-C", "P3": "CAM-A"})

    def test_geography_becomes_geometry(self) -> None:
        scene = load_scene(DEMO_PROJECT, "SC-030")
        assert scene is not None
        geometry = scene["geometry"]

        self.assertEqual(geometry["room"]["width"], 6.0)
        self.assertEqual({item["id"] for item in geometry["subjects"]}, {"MARA", "SPEAKER"})
        self.assertEqual(geometry["axis"]["between"], ["MARA", "SPEAKER"])
        by_id = {item["id"]: item for item in geometry["cameras"]}
        self.assertEqual(by_id["CAM-A"]["target"], "MARA")

    def test_shots_with_no_media_have_no_takes(self) -> None:
        scene = load_scene(DEMO_PROJECT, "SC-010")
        assert scene is not None
        self.assertEqual([shot["take_count"] for shot in scene["shots"]], [0, 0])

    def test_demo_projects_have_independent_identity_and_state(self) -> None:
        last_signal = load_production(DEMO_PROJECT)
        amiga_reel = load_production(AMIGA_DEMO_PROJECT)

        self.assertEqual(last_signal["id"], "the-last-signal")
        self.assertEqual(amiga_reel["id"], "amiga-demo-reel")
        # The reel lands on the scene that shows three transitions at once.
        self.assertEqual(amiga_reel["active_scene"]["id"], "SC-030")
        # Both productions use the id SC-030, and each resolves its own: a scene
        # id is unique within a project, never across them.
        self.assertEqual(last_signal["active_scene"]["id"], "SC-030")
        self.assertEqual(last_signal["active_scene"]["title"], "Echo Chamber")
        self.assertEqual(amiga_reel["active_scene"]["title"], "The Switcher")


class VariantTests(unittest.TestCase):
    """A scene may be reworked for a different engine; only one is in production."""

    def setUp(self) -> None:
        import shutil, tempfile

        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "production"
        shutil.copytree(DEMO_PROJECT, self.root)
        variant = self.root / "scenes" / "030-echo-chamber" / "ltx"
        variant.mkdir()
        (variant / "scene.yaml").write_text(
            "scene: SC-030\norder: 30\ntitle: Echo Chamber (LTX)\nvariant: ltx\n"
            "shots:\n  - n: 1\n    duration: 6\n    label: Reworked for LTX.\n",
            encoding="utf-8",
        )

    def declare_variant(self, name: str) -> None:
        manifest = self.root / "project.yaml"
        manifest.write_text(
            manifest.read_text().replace(
                "  active_scene: SC-030",
                f"  active_scene: SC-030\n  variant: {name}",
            ),
            encoding="utf-8",
        )

    def test_without_a_declared_variant_the_plain_breakdown_wins(self) -> None:
        scene = load_scene(self.root, "SC-030")
        assert scene is not None
        self.assertEqual(scene["title"], "Echo Chamber")

    def test_the_declared_variant_wins(self) -> None:
        self.declare_variant("ltx")
        scene = load_scene(self.root, "SC-030")
        assert scene is not None
        self.assertEqual(scene["title"], "Echo Chamber (LTX)")
        self.assertEqual(scene["variant"], "ltx")

    def test_a_scene_id_is_never_duplicated_by_a_variant(self) -> None:
        self.declare_variant("ltx")
        production = load_production(self.root)
        self.assertEqual(production["metrics"]["total_scenes"], 2)


if __name__ == "__main__":
    unittest.main()
