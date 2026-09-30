"""Gaussian splats: a shot's camera through a captured set, and splats as elements (CT-0047)."""

from __future__ import annotations

import math
import os
import tempfile
import unittest
from pathlib import Path

from cine_toaster.splat import ASSETS, available, plan_to_splat, quaternion, shot_poses, turntable_poses

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class PoseTests(unittest.TestCase):
    def test_the_plans_axes_become_three_js(self) -> None:
        # Plan: x right, y deep, z up. three.js: x right, y up, -z deep.
        self.assertEqual(plan_to_splat((1.0, 2.0, 3.0)), [1.0, 3.0, -2.0])

    def test_a_shots_poses_follow_its_move(self) -> None:
        from cine_toaster.project import load_scene

        scene = load_scene(DEMO, "SC-030")
        shot = next(item for item in scene["shots"] if item["id"] == "P3")
        poses = shot_poses(scene, shot, 3)
        self.assertEqual(len(poses), 3)
        first = poses[0]
        self.assertEqual(first["position"], [3.4, 1.05, -0.9])  # CAM-A at (3.4, 0.9), 1.05 m high
        self.assertEqual(first["lens_mm"], 50.0)
        self.assertAlmostEqual(first["target"][1], 1.18)  # aimed at Mara's eyes

    def test_rotations_and_turntables(self) -> None:
        self.assertEqual(quaternion([0, 0, 0, 1]), [0, 0, 0, 1])
        x, y, z, w = quaternion([180, 0, 0])
        self.assertAlmostEqual(abs(x), 1.0, places=6)
        self.assertAlmostEqual(w, 0.0, places=6)
        poses = turntable_poses(5, radius=2.0, degrees=90)
        distances = {round(math.dist(pose["position"][::2], (0, 0)), 6) for pose in poses}
        self.assertEqual(distances, {2.0})


@unittest.skipIf(available() or not (ASSETS / "butterfly.spz").is_file(),
                 "needs Playwright's Chromium and Spark's sample splat")
class RenderTests(unittest.TestCase):
    def test_a_splat_is_drawn_with_a_transparent_background(self) -> None:
        from PIL import Image

        from cine_toaster.splat import render

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            render(ASSETS / "butterfly.spz", turntable_poses(2, radius=2.5, degrees=30), out, width=160, height=90,
                   transform={"rotation": [180, 0, 0], "centre": True})
            pixels = Image.open(out / "f_0001.png")
            self.assertEqual(pixels.mode, "RGBA")
            alpha = pixels.getchannel("A")
            self.assertEqual(alpha.getpixel((0, 0)), 0)  # the corner is empty
            self.assertGreater(max(alpha.getdata()), 200)  # the butterfly is there


if __name__ == "__main__":
    unittest.main()
