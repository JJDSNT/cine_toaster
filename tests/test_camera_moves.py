"""The camera-move catalog: guidance, the geometry a move implies, the words a model gets (CT-0027)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.camera_moves import BUILTIN, list_moves
from cine_toaster.movement import KINDS, RIGS, SPEEDS
from cine_toaster.project import load_scene

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class CatalogTests(unittest.TestCase):
    def test_every_built_in_move_is_complete_and_speaks_the_movement_vocabulary(self) -> None:
        moves = list_moves()
        self.assertGreaterEqual(len(moves), 30)
        for move in moves:
            with self.subTest(move=move["id"]):
                self.assertTrue(move["says"] and move["use_when"] and move["avoid_when"] and move["prompt"])
                implied = move["implies"]
                self.assertIn(implied["kind"], ("", *KINDS))
                self.assertIn(implied["rig"], ("", *RIGS))
                self.assertIn(implied["speed"], ("", *SPEEDS))

    def test_a_production_can_replace_a_move(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "camera_moves" / "push-in").mkdir(parents=True)
            shutil.copy(BUILTIN / "push-in" / "move.toml", root / "camera_moves" / "push-in" / "move.toml")
            text = (root / "camera_moves" / "push-in" / "move.toml").read_text(encoding="utf-8")
            (root / "camera_moves" / "push-in" / "move.toml").write_text(
                text.replace('name = "Push in"', 'name = "Our push"'), encoding="utf-8")
            move = next(item for item in list_moves(root) if item["id"] == "push-in")
            self.assertEqual((move["name"], move["origin"]), ("Our push", "project"))


class ShotMoveTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
                                 for k, v in self.previous.items()])
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        self.scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"

    def with_move(self, move: str) -> dict:
        text = self.scene.read_text(encoding="utf-8").replace("  - n: 3\n", f"  - n: 3\n    move: {move}\n", 1)
        self.scene.write_text(text, encoding="utf-8")
        return load_scene(self.root, "SC-030")

    def test_a_named_move_takes_its_geometry_from_the_catalog(self) -> None:
        scene = self.with_move("{id: push-in}")
        shot = next(item for item in scene["shots"] if item["id"] == "P3")
        self.assertEqual((shot["move"]["kind"], shot["move"]["rig"], shot["move"]["name"]), ("dolly_in", "dolly", "Push in"))
        self.assertEqual(shot["motion"]["declared_kind"], "dolly")
        from cine_toaster.generation import _camera

        self.assertIn("dolly in toward the subject", _camera(scene, shot))

    def test_an_unknown_move_is_reported_not_guessed(self) -> None:
        scene = self.with_move("{id: vertigo-spin}")
        codes = [finding["code"] for finding in scene["findings"]]
        self.assertIn("move_unknown", codes)


if __name__ == "__main__":
    unittest.main()


class PreviewTests(unittest.TestCase):
    """Each move played on the preview stage, from the same blocking frames a shot's previs uses."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.moves = {move["id"]: move for move in list_moves(Path(BUILTIN).parent)}

    def ends(self, move_id: str) -> tuple[dict, dict]:
        from cine_toaster.blocking import blocking_frame, public_frame
        from cine_toaster.camera_moves import PREVIEW_STAGE, preview_motion

        motion, _ = preview_motion(self.moves[move_id])
        shot = {"id": move_id, "motion": motion}
        first, last = (public_frame(blocking_frame(PREVIEW_STAGE, shot, t)) for t in (0.0, 1.0))
        return first, last

    def test_every_move_previews(self) -> None:
        from cine_toaster.camera_moves import preview

        for move in self.moves.values():
            result = preview(move)
            self.assertEqual(len(result["frames"]), 25, move["id"])
            self.assertTrue(result["frames"][0].startswith("<svg"), move["id"])

    def test_the_moves_do_what_they_say(self) -> None:
        subject = lambda frame: next(item for item in frame["figures"] if item["subject"] == "A")  # noqa: E731
        first, last = self.ends("push-in")
        self.assertGreater(subject(last)["height_fraction"], subject(first)["height_fraction"])
        first, last = self.ends("zoom-out")
        self.assertLess(last["camera"]["lens_mm"], first["camera"]["lens_mm"])
        for move_id, side in (("pan-left", "right"), ("truck-left", "right"), ("pan-right", "left")):
            _, last = self.ends(move_id)
            self.assertEqual(subject(last)["side"], side, move_id)  # the subject slides the other way
        first, last = self.ends("tilt-up")
        self.assertGreater(last["camera"]["tilt_deg"], first["camera"]["tilt_deg"] + 20)
        first, last = self.ends("dolly-zoom")  # the face holds its size while the camera closes in
        self.assertAlmostEqual(subject(last)["height_fraction"], subject(first)["height_fraction"], delta=0.15)
        self.assertLess(subject(last)["depth"], subject(first)["depth"])

    def test_a_rig_the_plan_cannot_see_is_said(self) -> None:
        from cine_toaster.camera_moves import preview

        self.assertIn("cannot show a handheld's feel", preview(self.moves["handheld"])["note"])
        self.assertEqual(preview(self.moves["push-in"])["note"], "")
