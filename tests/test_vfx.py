"""Visual effects from a catalog: procedural ones FFmpeg draws, and stock elements composited (CT-0031)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cine_toaster.vfx import BLENDS, CATEGORIES, EFFECTS, expand, list_effects, list_elements, preview, render

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_FFMPEG = shutil.which("ffmpeg") is not None
PNG = b"\x89PNG"


def ffmpeg(*arguments: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *arguments], check=True)


def element(root: Path, element_id: str, category: str, blend: str, make) -> None:
    folder = root / "vfx_elements" / element_id
    folder.mkdir(parents=True)
    name = make(folder)
    (folder / "element.toml").write_text(
        f'id = "{element_id}"\ncategory = "{category}"\nblend = "{blend}"\nfile = "{name}"\nloop = true\n'
        f'source = "made in a test"\nlicense = "none"\n', encoding="utf-8")


class CatalogTests(unittest.TestCase):
    def test_every_effect_is_complete(self) -> None:
        effects = list_effects()
        self.assertGreaterEqual(len(effects), 14)
        for item in effects:
            self.assertIn(item["category"], CATEGORIES, item["id"])
            self.assertIn(item["effect"], EFFECTS, item["id"])
            self.assertTrue(item["says"] and item["use_when"], item["id"])
            if item["effect"] == "element":
                self.assertTrue(item["element_category"], item["id"])

    def test_an_element_effect_needs_an_element_the_production_brought(self) -> None:
        catalog = {item["id"]: item for item in list_effects()}
        effects, problems = expand([{"id": "fire-over"}], catalog, {})
        self.assertEqual(effects, [])
        self.assertIn("names none the production has (add one under vfx_elements", problems[0])
        _, problems = expand(["no-such-effect"], catalog, {})
        self.assertIn("not in the effect catalog", problems[0])
        effects, problems = expand([{"id": "film-grain", "strength": 0.2}], catalog, {})
        self.assertEqual((problems, effects[0]["params"]["strength"]), ([], 0.2))


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class DrawingTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_every_procedural_effect_draws(self) -> None:
        for item in list_effects():
            if item["effect"] != "element":
                self.assertTrue(preview(item).startswith(PNG), item["id"])

    def test_elements_are_composited_in_each_form_stock_libraries_deliver(self) -> None:
        # On black (screen), with alpha, and on green (key): the three forms of a stock element.
        element(self.root, "fire-black", "fire", "screen", lambda folder: ffmpeg(
            "-f", "lavfi", "-i", "color=c=black:s=320x320:d=1:r=24,drawbox=x=120:y=120:w=80:h=120:color=orange:t=fill",
            str(folder / "fire.mp4")) or "fire.mp4")
        element(self.root, "smoke-alpha", "smoke", "alpha", lambda folder: ffmpeg(
            "-f", "lavfi", "-i", "color=c=white:s=320x320:d=1:r=24,format=rgba,"
                                 "geq=r=255:g=255:b=255:a='if(between(X,100,220)*between(Y,100,220),230,0)'",
            "-c:v", "qtrle", str(folder / "smoke.mov")) or "smoke.mov")
        element(self.root, "sparks-green", "sparks", "key", lambda folder: ffmpeg(
            "-f", "lavfi", "-i", "color=c=0x00FF00:s=320x320:d=1:r=24,drawbox=x=140:y=140:w=40:h=40:color=yellow:t=fill",
            str(folder / "sparks.mp4")) or "sparks.mp4")
        elements = list_elements(self.root)
        self.assertEqual({item["blend"] for item in elements}, {"screen", "alpha", "key"})
        self.assertTrue(set(item["blend"] for item in elements) <= set(BLENDS))
        catalog = {item["id"]: item for item in list_effects(self.root)}
        for effect_id, element_id in (("fire-over", "fire-black"), ("smoke-over", "smoke-alpha"),
                                      ("sparks-over", "sparks-green")):
            effects, problems = expand([{"id": effect_id, "element": element_id, "scale": 0.5}], catalog,
                                       {item["id"]: item for item in elements})
            self.assertEqual(problems, [], effect_id)
            out = render(effects, 1.0, self.root / f"{effect_id}.mp4", width=640, height=360)
            centre = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(out), "-frames:v", "1", "-vf",
                                     "crop=40:40:300:160,format=rgb24", "-f", "rawvideo", "-"],
                                    capture_output=True, check=True).stdout
            # The element's bright middle is there, over the dark neutral picture.
            self.assertGreater(max(centre), 150, effect_id)
        # The key took the green away: no pure green is left at the element's edge.
        out = self.root / "sparks-over.mp4"
        edge = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(out), "-frames:v", "1", "-vf",
                               "crop=20:20:250:130,format=rgb24", "-f", "rawvideo", "-"], capture_output=True).stdout
        greens = [edge[i + 1] - max(edge[i], edge[i + 2]) for i in range(0, len(edge), 3)]
        self.assertLess(max(greens), 60)


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class AssemblyTests(unittest.TestCase):
    def test_a_shots_effects_are_in_the_version_and_an_unknown_one_is_reported(self) -> None:
        from cine_toaster.jobs import JobManager, JobStore
        from cine_toaster.project import load_scene

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
            os.environ["XDG_CACHE_HOME"], os.environ["XDG_STATE_HOME"] = str(base / "cache"), str(base / "state")
            try:
                root = base / "film"
                shutil.copytree(DEMO, root)
                scene = root / "scenes" / "030-echo-chamber" / "scene.yaml"
                scene.write_text(scene.read_text(encoding="utf-8").replace(
                    "  - n: 2\n", "  - n: 2\n    effects: [{id: film-grain}, {id: vignette}]\n"
                                  "    title: {id: caption, text: \"03:13\"}\n", 1), encoding="utf-8")
                loaded = load_scene(root, "SC-030")
                shot = next(item for item in loaded["shots"] if item["id"] == "P2")
                self.assertEqual([effect["id"] for effect in shot["effects"]], ["film-grain", "vignette"])
                manager = JobManager(store=JobStore(base / "state" / "jobs.sqlite"))
                try:
                    job = manager.wait(manager.submit("assemble", root, {"scene": "SC-030", "version": "v1"})["id"],
                                       timeout=180)
                    self.assertEqual(job["state"], "succeeded", job["error"])
                    segment = next(item for item in job["result"]["summary"]["segments"] if item["shot"] == "P2")
                    self.assertEqual([effect["id"] for effect in segment["effects"]], ["film-grain", "vignette"])
                finally:
                    manager.shutdown(wait=False)
                scene.write_text(scene.read_text(encoding="utf-8").replace("id: vignette", "id: lens-dirt"),
                                 encoding="utf-8")
                codes = [finding["code"] for finding in load_scene(root, "SC-030")["findings"]]
                self.assertIn("effect_problem", codes)
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
