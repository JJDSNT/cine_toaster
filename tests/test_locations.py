"""A set declared once, and pinned from a shared backlot (SPEC-0010)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.errors import ValidationError
from cine_toaster.locations import pin, status
from cine_toaster.project import load_production, load_scene

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class LocationTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        keys = ("XDG_CACHE_HOME", "XDG_STATE_HOME", "CINE_TOASTER_BACKLOT")
        self.previous = {key: os.environ.get(key) for key in keys}
        os.environ["XDG_CACHE_HOME"] = str(self.base / "cache")
        os.environ["XDG_STATE_HOME"] = str(self.base / "state")
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
                                 for k, v in self.previous.items()])
        self.root = self.base / "film"
        shutil.copytree(DEMO, self.root)
        self.scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"

    def test_scenes_in_a_location_share_its_plan(self) -> None:
        production = load_production(self.root)
        station = production["locations"]["LISTENING-STATION"]
        self.assertEqual(station["appearances"], ["SC-010", "SC-030"])
        scene = next(item for item in production["scenes"] if item["id"] == "SC-030")
        cameras = {camera["id"]: camera for camera in scene["geometry"]["cameras"]}
        self.assertEqual(cameras["CAM-A"]["lens_mm"], 50)  # from the location
        self.assertEqual([mark["id"] for mark in scene["geometry"]["marks"]], ["HALFWAY"])

    def test_a_scene_that_moves_the_sets_camera_is_told(self) -> None:
        self.scene.write_text(self.scene.read_text(encoding="utf-8").replace(
            "    - id: CAM-A\n      shots: \"3\"\n", "    - id: CAM-A\n      shots: \"3\"\n      x: 3.0\n      y: 0.9\n"),
            encoding="utf-8")
        findings = load_scene(self.root, "SC-030")["findings"]
        self.assertIn("location_override", [finding["code"] for finding in findings])

    def test_the_sets_pieces_are_in_every_scene_and_a_scene_may_move_one(self) -> None:
        from cine_toaster.locations import resolve

        location = {"room": [6, 4], "marks": [], "cameras": [],
                    "set_pieces": [{"id": "CONSOLE", "x": 4.7, "y": 2.6, "width": 0.7, "depth": 1.6, "height": 0.95}]}
        merged, notes = resolve({}, location)
        self.assertEqual([piece["id"] for piece in merged["set_pieces"]], ["CONSOLE"])
        merged, notes = resolve({"set_pieces": [{"id": "CONSOLE", "x": 4.0, "y": 2.6},
                                                {"id": "CHAIR", "x": 3, "y": 2, "width": 0.5, "depth": 0.5, "height": 0.9}]},
                                location)
        console = next(piece for piece in merged["set_pieces"] if piece["id"] == "CONSOLE")
        self.assertEqual((console["x"], console["height"]), (4.0, 0.95))  # moved here, the rest from the set
        self.assertIn("set piece CONSOLE stands elsewhere here than in the location", notes)
        self.assertEqual(len(merged["set_pieces"]), 2)

    def test_the_locations_room_reads_each_set_in_the_cores_terms(self) -> None:
        from cine_toaster.project import load_production
        from cine_toaster.web import locations_view

        root = Path(__file__).parents[1] / "examples" / "demo-project"
        [station] = locations_view(root, load_production(root), {})
        self.assertEqual(station["id"], "LISTENING-STATION")
        self.assertEqual(station["appearances"], ["SC-010", "SC-030"])
        plan = station["plan"]
        self.assertEqual(plan["room"], {"width": 6.0, "depth": 4.5, "height": 3.2, "exterior": False})
        self.assertEqual([camera["id"] for camera in plan["cameras"]], ["CAM-A", "CAM-B", "CAM-C"])
        self.assertEqual({piece["id"] for piece in plan["set_pieces"]}, {"CONSOLE", "RACK"})
        self.assertIsNone(station["backlot"])

    def test_an_unknown_location_is_an_error(self) -> None:
        self.scene.write_text(self.scene.read_text(encoding="utf-8").replace(
            "location: LISTENING-STATION", "location: LIGHTHOUSE"), encoding="utf-8")
        self.assertIn("location_unknown", [finding["code"] for finding in load_scene(self.root, "SC-030")["findings"]])

    def test_pinning_from_the_backlot_copies_and_update_is_explicit(self) -> None:
        backlot = self.base / "backlot"
        shutil.copytree(self.root / "locations" / "listening-station", backlot / "harbour-office")
        manifest = backlot / "harbour-office" / "location.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace("LISTENING-STATION", "HARBOUR-OFFICE"),
                            encoding="utf-8")
        os.environ["CINE_TOASTER_BACKLOT"] = str(backlot)
        record = pin(self.root, "harbour-office")
        self.assertEqual(record["directory"], "locations/harbour-office")
        self.assertIn("HARBOUR-OFFICE", load_production(self.root)["locations"])
        self.assertEqual(status(self.root), [{"id": "HARBOUR-OFFICE", "pinned_at": record["pinned_at"],
                                              "edited_here": False, "backlot_moved_on": False, "in_backlot": True}])
        # The backlot moves on: the film does not, until someone says so.
        manifest.write_text(manifest.read_text(encoding="utf-8") + "\nlook: DAY\n", encoding="utf-8")
        self.assertTrue(status(self.root)[0]["backlot_moved_on"])
        self.assertEqual(load_production(self.root)["locations"]["HARBOUR-OFFICE"]["look"], "")
        with self.assertRaisesRegex(ValidationError, "already pinned"):
            pin(self.root, "harbour-office")
        pin(self.root, "harbour-office", update=True)
        self.assertEqual(load_production(self.root)["locations"]["HARBOUR-OFFICE"]["look"], "DAY")
        self.assertFalse(status(self.root)[0]["backlot_moved_on"])


if __name__ == "__main__":
    unittest.main()
