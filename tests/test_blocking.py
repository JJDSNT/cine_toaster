"""The blocking frame: a shot's camera view, computed from the plan (CT-0025)."""

from __future__ import annotations

import math
import os
import shutil
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from cine_toaster.blocking import blocking_frame, public_frame, render_svg
from cine_toaster.index import ProjectIndex, build_index
from cine_toaster.project import load_production
from cine_toaster.web import ProjectBrowserHandler

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


def echo_chamber() -> dict:
    return next(scene for scene in load_production(DEMO)["scenes"] if scene["id"] == "SC-030")


def figures(scene: dict, shot_id: str, at: str) -> dict[str, dict]:
    shot = next(item for item in scene["shots"] if item["id"] == shot_id)
    frame = public_frame(blocking_frame(scene, shot, at))
    return {figure["subject"]: figure for figure in frame["figures"]}


class EchoChamberGoldenTests(unittest.TestCase):
    """SC-030, measured once by hand against the plan."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.scene = echo_chamber()

    def test_p2_starts_on_the_stack_with_mara_off_right(self) -> None:
        start = figures(self.scene, "P2", "start")
        self.assertAlmostEqual(start["SPEAKER"]["x"], -0.986, places=2)
        self.assertTrue(start["SPEAKER"]["in_frame"])
        self.assertGreater(start["MARA"]["x"], 1.0)
        self.assertFalse(start["MARA"]["in_frame"])
        self.assertEqual(start["MARA"]["side"], "right")

    def test_p2_ends_with_mara_walked_into_the_centre(self) -> None:
        end = figures(self.scene, "P2", "end")
        self.assertAlmostEqual(end["MARA"]["x"], 0.0, places=2)
        self.assertTrue(end["MARA"]["in_frame"])
        # She is 1.8 m from CAM-C: at 28 mm a seated figure fills most of the height.
        self.assertAlmostEqual(end["MARA"]["depth"], 1.82, places=1)
        self.assertAlmostEqual(end["MARA"]["height_fraction"], 0.909, places=2)

    def test_p1_has_mara_behind_the_camera(self) -> None:
        self.assertTrue(figures(self.scene, "P1", "start")["MARA"]["behind"])

    def test_p3_holds_mara_centred_with_the_stack_off_left(self) -> None:
        start = figures(self.scene, "P3", "start")
        self.assertAlmostEqual(start["MARA"]["x"], 0.0, places=2)
        self.assertFalse(start["SPEAKER"]["in_frame"])
        self.assertEqual(start["SPEAKER"]["side"], "left")


class AgreementTests(unittest.TestCase):
    def test_the_frame_agrees_with_the_continuity_checks(self) -> None:
        """Whoever the movement checks call framed has their eyes inside the frame."""

        scene = echo_chamber()
        for shot in scene["shots"]:
            for at in ("start", "end"):
                frame = blocking_frame(scene, shot, at)
                seen = {
                    figure["subject"]: figure["side"]
                    for figure in frame["figures"]
                    if not figure["behind"] and abs(figure["x"]) <= 1.0
                }
                framed = {item["subject"]: item["side"] for item in shot["motion"][at]["framed"]}
                self.assertEqual(seen, framed, f"{shot['id']} {at}")

    def test_the_camera_tilts_toward_the_subject_it_follows(self) -> None:
        scene = echo_chamber()
        shot = next(item for item in scene["shots"] if item["id"] == "P1")
        frame = blocking_frame(scene, shot, "start")
        # CAM-B at 1.05 m aims at the stack's 1.55 m, 1.72 m away on the plan.
        expected = math.degrees(math.atan2(1.55 - 1.05, math.hypot(1.2 - 2.2, 2.4 - 1.0)))
        self.assertAlmostEqual(frame["camera"]["tilt_deg"], expected, places=0)

    def test_a_shot_without_a_camera_has_no_frame(self) -> None:
        self.assertIsNone(blocking_frame({"geometry": {}}, {"id": "P1", "motion": None}))

    def test_the_drawing_names_who_is_in_and_out_of_frame(self) -> None:
        scene = echo_chamber()
        shot = next(item for item in scene["shots"] if item["id"] == "P2")
        svg = render_svg(blocking_frame(scene, shot, "start"))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("Speaker stack</text>", svg)
        self.assertIn("Mara Vale ▸", svg)
        self.assertIn("CAM-C · 28 mm", svg)


class EndpointTests(unittest.TestCase):
    def test_the_control_room_serves_the_frame(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "production"
            shutil.copytree(DEMO, root)
            previous = os.environ.get("XDG_CACHE_HOME")
            os.environ["XDG_CACHE_HOME"] = str(Path(raw) / "cache")
            try:
                build_index(root)
                server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
                server.project_index = ProjectIndex(root)
                server.project_root = root.resolve()
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    url = f"http://127.0.0.1:{server.server_address[1]}/api/blocking-frame?scene=SC-030&shot=P2&at=end"
                    with urllib.request.urlopen(url, timeout=30) as response:
                        self.assertEqual(response.headers.get_content_type(), "image/svg+xml")
                        self.assertIn(b"Mara Vale</text>", response.read())
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
            finally:
                if previous is None:
                    os.environ.pop("XDG_CACHE_HOME", None)
                else:
                    os.environ["XDG_CACHE_HOME"] = previous


if __name__ == "__main__":
    unittest.main()
