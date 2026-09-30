"""A scene's plan as OpenUSD, and USD scenes as elements (CT-0047)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.usd_export import available

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


@unittest.skipIf(available(), "usd-core is not installed (make install-usd)")
class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        from cine_toaster.project import load_scene
        from cine_toaster.usd_export import export

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.scene = load_scene(DEMO, "SC-030")
        self.path = Path(directory.name) / "sc030.usda"
        self.summary = export(self.scene, self.path)

    def test_the_stage_holds_the_plan(self) -> None:
        from pxr import Usd, UsdGeom

        stage = Usd.Stage.Open(str(self.path))
        self.assertEqual(UsdGeom.GetStageUpAxis(stage), UsdGeom.Tokens.z)
        self.assertEqual(UsdGeom.GetStageMetersPerUnit(stage), 1.0)
        self.assertEqual(stage.GetTimeCodesPerSecond(), 24)
        for path in ("/Scene/Room/Floor", "/Scene/Room/Wall_north", "/Scene/SetPieces/CONSOLE",
                     "/Scene/SetPieces/RACK", "/Scene/Subjects/MARA", "/Scene/Subjects/SPEAKER",
                     "/Scene/Cameras/P1", "/Scene/Cameras/P2", "/Scene/Cameras/P3"):
            self.assertTrue(stage.GetPrimAtPath(path).IsValid(), path)
        self.assertEqual([item["shot"] for item in self.summary["shots"]], ["P1", "P2", "P3"])
        self.assertEqual(stage.GetEndTimeCode(), self.summary["frames"])

    def test_each_camera_frames_what_the_blocking_frame_frames(self) -> None:
        from pxr import Gf, Usd, UsdGeom

        stage = Usd.Stage.Open(str(self.path))
        first = next(item["first_frame"] for item in self.summary["shots"] if item["shot"] == "P3")
        time = Usd.TimeCode(first)
        camera = UsdGeom.Camera(stage.GetPrimAtPath("/Scene/Cameras/P3"))
        # 50 mm on a 36 mm sensor, in USD's tenths of a stage unit.
        self.assertAlmostEqual(camera.GetFocalLengthAttr().Get(time), 0.5, places=3)
        self.assertAlmostEqual(camera.GetHorizontalApertureAttr().Get(), 0.36, places=3)
        world = UsdGeom.Xformable(camera).ComputeLocalToWorldTransform(time)
        mara = UsdGeom.Xformable(stage.GetPrimAtPath("/Scene/Subjects/MARA")).ComputeLocalToWorldTransform(time)
        eyes = mara.ExtractTranslation() + Gf.Vec3d(0, 0, 1.18 - (1.18 + 0.12) / 2)
        local = world.GetInverse().Transform(eyes)
        # In front of the camera (-Z), centred left to right and top to bottom, as the frame draws her.
        self.assertLess(local[2], 0)
        self.assertLess(abs(local[0] / -local[2]), 0.02)
        self.assertLess(abs(local[1] / -local[2]), 0.05)
        # And the subject moved with the shot: at P2's start she is still at the console.
        start = next(item["first_frame"] for item in self.summary["shots"] if item["shot"] == "P2")
        at_start = UsdGeom.Xformable(stage.GetPrimAtPath("/Scene/Subjects/MARA")).ComputeLocalToWorldTransform(
            Usd.TimeCode(start)).ExtractTranslation()
        self.assertAlmostEqual(at_start[0], 4.1, places=2)
        self.assertAlmostEqual(mara.ExtractTranslation()[0], 2.6, places=2)


USD_TEAPOT = Path.home() / ".local/share/cine-toaster/assets/usd-wg-assets/full_assets/Teapot/Teapot.usd"


@unittest.skipUnless(shutil.which("ffmpeg") and USD_TEAPOT.is_file()
                     and __import__("cine_toaster.titles").titles.blender_binary(),
                     "needs Blender, FFmpeg and the USD-WG Teapot sample")
class ImportTests(unittest.TestCase):
    def test_a_usd_stage_is_rendered_as_an_element(self) -> None:
        from cine_toaster.vfx import expand, list_effects, list_elements, render

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = os.environ.get("XDG_STATE_HOME")
            os.environ["XDG_STATE_HOME"] = str(root / "state")
            try:
                folder = root / "vfx_elements" / "teapot"
                folder.mkdir(parents=True)
                (folder / "element.toml").write_text(
                    f'id = "teapot"\ncategory = "other"\nblend = "alpha"\nusd = "{USD_TEAPOT}"\n[params]\nsamples = 4\n',
                    encoding="utf-8")
                [element] = list_elements(root)
                self.assertEqual((element["format"], element["exists"]), ("openusd", True))
                effects, problems = expand([{"id": "explosion-over", "element": "teapot"}],
                                           {item["id"]: item for item in list_effects(root)}, {"teapot": element})
                self.assertEqual(problems, [])
                out = render(effects, 0.25, root / "teapot.mp4", width=160, height=90)
                self.assertTrue(out.is_file())
            finally:
                if previous is None:
                    os.environ.pop("XDG_STATE_HOME", None)
                else:
                    os.environ["XDG_STATE_HOME"] = previous


if __name__ == "__main__":
    unittest.main()
