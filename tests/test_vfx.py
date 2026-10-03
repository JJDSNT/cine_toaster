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


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class ModalityTests(unittest.TestCase):
    """Each form an element arrives in, composited the same way (CT-0047)."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.previous = os.environ.get("XDG_STATE_HOME")
        os.environ["XDG_STATE_HOME"] = str(self.root / "state")
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        if self.previous is None:
            os.environ.pop("XDG_STATE_HOME", None)
        else:
            os.environ["XDG_STATE_HOME"] = self.previous

    def bright(self, element_id: str) -> int:
        catalog = {item["id"]: item for item in list_effects(self.root)}
        effects, problems = expand([{"id": "sparks-over", "element": element_id}], catalog,
                                   {item["id"]: item for item in list_elements(self.root)})
        self.assertEqual(problems, [], element_id)
        out = render(effects, 0.5, self.root / f"{element_id}.mp4", width=320, height=180)
        centre = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.2", "-i", str(out), "-frames:v", "1", "-vf",
                                 "crop=40:40:140:70,format=gray", "-f", "rawvideo", "-"], capture_output=True,
                                check=True).stdout
        return max(centre)

    def test_png_sequence_video_with_a_matte_and_exr_through_opencolorio(self) -> None:
        import numpy as np

        # A white square, as PNG frames with alpha, as a colour video with a separate matte, and as linear EXR.
        frames = self.root / "vfx_elements" / "square-png" / "frames"
        frames.mkdir(parents=True)
        ffmpeg("-f", "lavfi", "-i", "color=c=white:s=320x180:d=0.5:r=24,format=rgba,"
                                    "geq=r=255:g=255:b=255:a='if(between(X,120,200)*between(Y,50,130),255,0)'",
               str(frames / "f_%04d.png"))
        element(self.root, "square-png-seq", "sparks", "alpha", lambda folder: "../square-png/frames/f_%04d.png")
        element(self.root, "square-matte", "sparks", "alpha", lambda folder: ffmpeg(
            "-f", "lavfi", "-i", "color=c=white:s=320x180:d=0.5:r=24", str(folder / "colour.mp4")) or "colour.mp4")
        ffmpeg("-f", "lavfi", "-i", "color=c=black:s=320x180:d=0.5:r=24,drawbox=x=120:y=50:w=80:h=80:color=white:t=fill",
               str(self.root / "vfx_elements" / "square-matte" / "matte.mp4"))
        manifest = self.root / "vfx_elements" / "square-matte" / "element.toml"
        manifest.write_text(manifest.read_text() + 'matte = "matte.mp4"\n', encoding="utf-8")

        import OpenEXR

        exr = self.root / "vfx_elements" / "square-exr" / "frames"
        exr.mkdir(parents=True)
        pixels = np.zeros((180, 320, 4), np.float32)
        pixels[50:130, 120:200] = (4.0, 4.0, 4.0, 1.0)  # brighter than white: scene-linear light
        for index in range(1, 13):
            OpenEXR.File({"type": OpenEXR.scanlineimage, "compression": OpenEXR.ZIP_COMPRESSION},
                         {"RGBA": pixels.astype(np.float16)}).write(str(exr / f"f_{index:04d}.exr"))
        element(self.root, "square-exr-seq", "sparks", "alpha", lambda folder: "../square-exr/frames/f_%04d.exr")

        formats = {item["id"]: item["format"] for item in list_elements(self.root)}
        self.assertEqual((formats["square-png-seq"], formats["square-exr-seq"], formats["square-matte"]),
                         ("image-sequence", "exr-sequence", "video"))
        for element_id in ("square-png-seq", "square-matte", "square-exr-seq"):
            self.assertGreater(self.bright(element_id), 200, element_id)
        # The matte decided the opacity: outside the square the colour video is not seen.
        catalog = {item["id"]: item for item in list_effects(self.root)}
        effects, _ = expand([{"id": "sparks-over", "element": "square-matte"}], catalog,
                            {item["id"]: item for item in list_elements(self.root)})
        out = render(effects, 0.5, self.root / "matte-edge.mp4", width=320, height=180)
        corner = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.2", "-i", str(out), "-frames:v", "1", "-vf",
                                 "crop=20:20:10:10,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
        self.assertLess(max(corner), 180)

    def test_a_look_is_an_opencolorio_transform_baked_for_ffmpeg(self) -> None:
        from cine_toaster.color import bake_look

        lut = bake_look(self.root / "look.cube", size=9)
        lines = lut.read_text().splitlines()
        self.assertEqual(lines[1], "LUT_3D_SIZE 9")
        self.assertEqual(len(lines), 2 + 9 ** 3)
        black, white = lines[2].split(), lines[-1].split()
        self.assertLess(float(black[0]), 0.05)
        # ACES 2.0's tone scale compresses the highlights: display white comes out below white.
        self.assertTrue(0.6 < float(white[0]) < 0.95, white)

    @unittest.skipUnless(shutil.which("ffmpeg") and __import__("cine_toaster.titles").titles.blender_binary(),
                         "Blender is not installed")
    def test_every_example_modality_is_built_and_composited(self) -> None:
        from cine_toaster.vfx_examples import build

        made = build(self.root, with_downloads=False)
        formats = {item["id"]: item["format"] for item in list_elements(self.root)}
        self.assertEqual({formats[element_id] for element_id in made},
                         {"image-sequence", "exr-sequence", "video", "blender-project"})
        for element_id in made:
            self.assertGreater(self.bright(element_id), 120, element_id)


VDB = Path.home() / ".local" / "share" / "cine-toaster" / "assets" / "openvdb" / "smoke.vdb"


@unittest.skipUnless(HAS_FFMPEG and VDB.is_file() and __import__("cine_toaster.titles").titles.blender_binary(),
                     "needs Blender and OpenVDB's smoke.vdb (toast vfx examples downloads it)")
class OpenVdbTests(unittest.TestCase):
    def test_a_volume_is_rendered_by_blender_and_composited(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = os.environ.get("XDG_STATE_HOME")
            os.environ["XDG_STATE_HOME"] = str(root / "state")
            try:
                folder = root / "vfx_elements" / "smoke"
                folder.mkdir(parents=True)
                (folder / "element.toml").write_text(
                    f'id = "smoke"\ncategory = "smoke"\nblend = "alpha"\nvolume = "{VDB}"\n[params]\ndensity = 3.0\n'
                    f'samples = 4\n', encoding="utf-8")
                [element_] = list_elements(root)
                self.assertEqual((element_["format"], element_["exists"]), ("openvdb", True))
                catalog = {item["id"]: item for item in list_effects(root)}
                effects, problems = expand([{"id": "smoke-over", "element": "smoke"}], catalog, {"smoke": element_})
                self.assertEqual(problems, [])
                out = render(effects, 0.25, root / "smoke.mp4", width=160, height=90)
                frame = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-frames:v", "1", "-vf",
                                        "crop=30:50:65:20,format=gray", "-f", "rawvideo", "-"], capture_output=True,
                                       check=True).stdout
                # The smoke is there, lighter than the neutral picture's dark figure behind it.
                self.assertGreater(max(frame) - min(frame), 20)
            finally:
                if previous is None:
                    os.environ.pop("XDG_STATE_HOME", None)
                else:
                    os.environ["XDG_STATE_HOME"] = previous


@unittest.skipUnless(HAS_FFMPEG and __import__("cine_toaster.vfx").vfx.natron_binary(),
                     "Natron (the OpenFX host) is not installed")
class OpenFxTests(unittest.TestCase):
    def test_openfx_plugins_run_in_natron_before_the_rest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plate = root / "plate.mp4"
            ffmpeg("-f", "lavfi", "-i", "color=c=0x202830:s=320x180:d=0.5:r=24,drawgrid=w=40:h=40:t=1:c=0x506070",
                   "-f", "lavfi", "-i", "sine=f=300:d=0.5", "-shortest", "-pix_fmt", "yuv420p", str(plate))
            catalog = {item["id"]: item for item in list_effects()}
            effects, problems = expand([{"id": "vignette"}, {"id": "ofx-lens-distortion", "k1": 0.3}], catalog, {})
            self.assertEqual(problems, [])
            out = render(effects, 0.5, root / "out.mp4", background=plate, width=320, height=180)
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width",
                                    "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout
            self.assertIn("video,320", probe)
            self.assertIn("audio", probe)  # the sound came through Natron's detour
            # The grid's straight lines are bent: the plate and the result differ along an edge.
            grab = lambda path: subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.2", "-i", str(path), "-frames:v", "1",
                                                "-vf", "crop=320:10:0:5,format=gray", "-f", "rawvideo", "-"],
                                               capture_output=True, check=True).stdout  # noqa: E731
            difference = sum(abs(a - b) for a, b in zip(grab(plate), grab(out))) / 3200
            self.assertGreater(difference, 2)


@unittest.skipUnless(HAS_FFMPEG and __import__("cine_toaster.titles").titles.blender_binary(), "Blender is not installed")
class BlenderEffectTests(unittest.TestCase):
    """Weather, electricity, destruction and liquids, rendered by Blender for the shot (CT-0047)."""

    def test_each_one_renders_and_composites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = os.environ.get("XDG_STATE_HOME")
            os.environ["XDG_STATE_HOME"] = str(root / "state")
            try:
                catalog = {item["id"]: item for item in list_effects()}
                for effect_id, extra in (("rain", {}), ("snow", {}), ("lightning", {"begin": 0.1}),
                                         ("shatter", {"text": "AB"}), ("melt", {"text": "AB"}),
                                         ("liquid-splash", {"resolution": 16}), ("hologram", {}), ("fog", {})):
                    effects, problems = expand([{"id": effect_id, "samples": 2, **extra}], catalog, {})
                    self.assertEqual(problems, [], effect_id)
                    out = render(effects, 0.25, root / f"{effect_id}.mp4", width=160, height=90)
                    self.assertTrue(out.is_file() and out.stat().st_size > 0, effect_id)
            finally:
                if previous is None:
                    os.environ.pop("XDG_STATE_HOME", None)
                else:
                    os.environ["XDG_STATE_HOME"] = previous
