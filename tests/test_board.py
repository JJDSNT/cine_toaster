"""The 3D storyboard: boards to compose from, an animatic to check (CT-0049)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.titles import blender_binary
from cine_toaster.usd_export import available as usd_missing

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class SizeTests(unittest.TestCase):
    """One scale of shot sizes, measured the same way for every shot (CT-0049)."""

    def test_sizes_are_measured_and_a_declared_size_is_checked(self) -> None:
        from cine_toaster.board import canonical, framing, label
        from cine_toaster.project import load_scene

        scene = load_scene(DEMO, "SC-030")
        shots = {shot["id"]: shot for shot in scene["shots"]}
        self.assertEqual(framing(scene, shots["P2"])["size"], "WIDE")
        self.assertEqual(framing(scene, shots["P3"])["size"], "MEDIUM CLOSE-UP")
        self.assertEqual(label(scene, shots["P3"], 3), "3 · MEDIUM CLOSE-UP")
        self.assertEqual((canonical("cu"), canonical("close_up"), canonical("OTS")), ("CLOSE-UP", "CLOSE-UP", "OVER SHOULDER"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "film"
            shutil.copytree(DEMO, root)
            scene_file = root / "scenes" / "030-echo-chamber" / "scene.yaml"
            text = scene_file.read_text(encoding="utf-8").replace("  - n: 3\n", "  - n: 3\n    size: extreme wide\n", 1)
            text = text.replace("  - n: 2\n", "  - n: 2\n    size: banana\n", 1)
            scene_file.write_text(text, encoding="utf-8")
            codes = {finding["code"]: finding for finding in load_scene(root, "SC-030")["findings"]}
            self.assertIn("is declared extreme wide, but its camera frames a medium close-up",
                          codes["shot_size_mismatch"]["message"])
            self.assertIn("shot_size_unknown", codes)


@unittest.skipUnless(blender_binary() and not usd_missing() and shutil.which("ffmpeg"),
                     "needs Blender, usd-core and FFmpeg")
class BoardTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"], os.environ["XDG_STATE_HOME"] = str(base / "cache"), str(base / "state")
        self.addCleanup(self._restore)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def scene(self) -> dict:
        from cine_toaster.project import load_scene

        return load_scene(self.root, "SC-030")

    def test_a_board_per_shot_with_its_depth(self) -> None:
        from PIL import Image

        from cine_toaster.board import board_path, boards

        made = boards(self.root, self.scene(), shots=["P3"], ends=True, width=320, height=180)
        self.assertEqual([(item["shot"], item["moment"]) for item in made], [("P3", "start"), ("P3", "end")])
        picture = Image.open(board_path(self.root, "SC-030", "P3"))
        self.assertEqual(picture.size, (320, 180))
        depth = Image.open(made[0]["depth"])
        # Mara's head, in the middle of the close-up, is nearer than the wall at the frame's edge.
        self.assertGreater(depth.getpixel((160, 70)), depth.getpixel((300, 20)))

    def test_a_master_picture_can_start_from_the_board_and_a_stale_board_is_said(self) -> None:
        from cine_toaster.board import boards
        from cine_toaster.errors import ValidationError
        from cine_toaster.pictures import plan_picture
        from cine_toaster.project import load_production

        scene_file = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene_file.write_text(scene_file.read_text(encoding="utf-8").replace(
            "  - n: 3\n", "  - n: 3\n    derive: {from: board, with: [MARA], request: The mannequin becomes her.}\n", 1),
            encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "its 3D board, which is not drawn yet"):
            plan_picture(self.root, load_production(self.root), "SC-030", "P3")
        boards(self.root, self.scene(), shots=["P3"], width=320, height=180)
        plan = plan_picture(self.root, load_production(self.root), "SC-030", "P3")
        self.assertEqual(plan.source.name, "P3-start.png")
        self.assertFalse(any("drawn before the plan" in note for note in plan.notes))
        # The plan moves on (the mark moves): the board no longer shows it.
        location = self.root / "locations" / "listening-station" / "location.yaml"
        location.write_text(location.read_text(encoding="utf-8").replace("x: 2.6", "x: 2.9", 1), encoding="utf-8")
        plan = plan_picture(self.root, load_production(self.root), "SC-030", "P3")
        self.assertTrue(any("drawn before the plan last changed" in note for note in plan.notes))

    def test_a_sheet_pins_the_boards_up_labelled_with_their_sizes(self) -> None:
        from PIL import Image

        from cine_toaster.board import boards, sheet, shot_size

        scene = self.scene()
        sizes = {shot["id"]: shot_size(scene, shot) for shot in scene["shots"]}
        self.assertEqual(sizes["P2"], "WIDE")  # Mara is out of frame at its start
        self.assertIn("CLOSE-UP", sizes["P3"])
        boards(self.root, scene, width=160, height=90)
        grid = Image.open(sheet(self.root, scene, tile=(160, 90)))
        self.assertGreater(grid.width, 3 * 160)

    def test_boards_are_a_job_adopted_into_the_scenes_renders(self) -> None:
        from cine_toaster.board import listing
        from cine_toaster.jobs import JobManager, JobStore

        manager = JobManager(store=JobStore(Path(os.environ["XDG_STATE_HOME"]) / "jobs.sqlite"))
        self.addCleanup(manager.shutdown, wait=False)
        job = manager.wait(manager.submit("boards", self.root, {"scene": "SC-030"})["id"], timeout=300)
        self.assertEqual(job["state"], "succeeded", job["error"])
        manager.adopt(job["id"])
        listed = listing(self.root, self.scene())
        self.assertEqual(set(listed["shots"]["P3"]["boards"]), {"start"})
        self.assertFalse(listed["shots"]["P3"]["boards"]["start"]["stale"])
        self.assertIn("sheet.png", listed)

    def test_the_animatic_plays_the_scene_through_its_cameras(self) -> None:
        from cine_toaster.assembly import probe
        from cine_toaster.board import animatic

        video = animatic(self.root, self.scene(), width=160, height=90, step=48)
        self.assertTrue(video.is_file())
        self.assertGreater(probe(video)["duration"], 1.0)


if __name__ == "__main__":
    unittest.main()
