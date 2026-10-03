"""A shot's camera as a nerfstudio camera path (CT-0047)."""

from __future__ import annotations

import json
import math
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.nerf import camera_path, export, vertical_fov
from cine_toaster.project import load_scene

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


def matrix(flat: list[float]) -> list[list[float]]:
    return [flat[row * 4:row * 4 + 4] for row in range(4)]


class CameraPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene = load_scene(DEMO, "SC-030")
        self.shot = next(item for item in self.scene["shots"] if item["id"] == "P3")

    def test_the_path_is_what_ns_render_reads(self) -> None:
        path = camera_path(self.scene, self.shot, frames=5, width=640, height=360)
        self.assertEqual((path["camera_type"], path["render_width"], path["render_height"]), ("perspective", 640, 360))
        self.assertEqual(len(path["camera_path"]), 5)
        first = path["camera_path"][0]
        self.assertEqual(len(first["camera_to_world"]), 16)
        # 50 mm on a 36 mm sensor, 16:9: a vertical field of view of about 22.9 degrees.
        self.assertAlmostEqual(first["fov"], vertical_fov(50, 640, 360), places=3)
        self.assertAlmostEqual(first["fov"], 22.9, delta=0.2)

    def test_the_camera_stands_where_the_plan_puts_it_and_looks_at_the_subject(self) -> None:
        first = matrix(camera_path(self.scene, self.shot, frames=2)["camera_path"][0]["camera_to_world"])
        eye = [first[row][3] for row in range(3)]
        self.assertEqual([round(value, 3) for value in eye], [3.4, 0.9, 1.05])  # CAM-A
        look = [-first[row][2] for row in range(3)]  # OpenGL: the camera looks down its -Z
        to_mara = [2.6 - 3.4, 2.3 - 0.9, 1.18 - 1.05]
        length = math.sqrt(sum(value * value for value in to_mara))
        self.assertAlmostEqual(sum(a * b / length for a, b in zip(look, to_mara)), 1.0, places=4)

    def test_the_locations_transform_places_the_plan_in_the_nerfs_world(self) -> None:
        moved = camera_path(self.scene, self.shot, frames=2,
                            transform={"position": [10, 0, 0], "rotation": [0, 0, 90], "scale": 0.5})
        eye = [matrix(moved["camera_path"][0]["camera_to_world"])[row][3] for row in range(3)]
        # Turned a quarter about Z, halved, then moved 10 along x: (3.4, 0.9) -> (-0.45, 1.7) + (10, 0).
        self.assertEqual([round(value, 3) for value in eye], [9.55, 1.7, 0.525])

    def test_export_writes_the_file_and_the_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "film"
            shutil.copytree(DEMO, root)
            made = export(root, self.scene, self.shot, root / "exports" / "nerf" / "P3.json", frames=3)
            self.assertEqual(len(json.loads(Path(made["path"]).read_text())["camera_path"]), 3)
            self.assertIn("ns-render camera-path", made["command"])
            self.assertFalse(made["placed"])


if __name__ == "__main__":
    unittest.main()
