"""Titles from a catalog, drawn by FFmpeg or Blender, on cards and over takes (CT-0031)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cine_toaster.errors import ValidationError
from cine_toaster.titles import CATEGORIES, EFFECTS, ENGINES, blender_binary, expand, list_titles, preview

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_FFMPEG = shutil.which("ffmpeg") is not None
PNG = b"\x89PNG"


class CatalogTests(unittest.TestCase):
    def test_every_title_is_complete_and_names_an_effect_its_engine_draws(self) -> None:
        titles = list_titles()
        self.assertGreaterEqual(len(titles), 12)
        for item in titles:
            self.assertIn(item["category"], CATEGORIES, item["id"])
            self.assertIn(item["engine"], ENGINES, item["id"])
            self.assertIn(item["effect"], EFFECTS[item["engine"]], item["id"])
            self.assertTrue(item["says"] and item["use_when"], item["id"])

    def test_a_shot_title_takes_the_items_defaults(self) -> None:
        catalog = {item["id"]: item for item in list_titles()}
        title, problem = expand("SINGULARITY", catalog)  # a bare string is a card's text
        self.assertEqual((problem, title["id"], title["text"], title["params"]["spaced"]), ("", "card", "SINGULARITY", True))
        title, _ = expand({"id": "caption", "text": "03:13", "size": 24, "reason": "the time passes"}, catalog)
        self.assertEqual((title["params"]["size"], title["params"]["position"], title["reason"]), (24, "bottom", "the time passes"))
        _, problem = expand({"id": "no-such-title", "text": "x"}, catalog)
        self.assertIn("not in the title catalog", problem)
        _, problem = expand({"id": "card", "text": "x", "position": "sideways"}, catalog)
        self.assertIn("positions are", problem)

    def test_a_production_can_add_its_own_title(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "titles" / "prologue").mkdir(parents=True)
            (root / "titles" / "prologue" / "title.toml").write_text(
                'id = "prologue"\nname = "Prologue"\ncategory = "cards"\nsays = "x"\nuse_when = ["y"]\n'
                '[params]\nsize = 40\nfont = "fontes/Oswald.ttf"\n[render]\nengine = "ffmpeg"\neffect = "fade"\n',
                encoding="utf-8")
            item = next(item for item in list_titles(root) if item["id"] == "prologue")
            self.assertEqual((item["origin"], item["params"]["font"]), ("project", "fontes/Oswald.ttf"))


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class DrawingTests(unittest.TestCase):
    def test_every_ffmpeg_title_draws(self) -> None:
        for item in list_titles():
            if item["engine"] == "ffmpeg":
                self.assertTrue(preview(item, text="It's 03:13, Geneva").startswith(PNG), item["id"])

    @unittest.skipUnless(blender_binary(), "Blender is not installed")
    def test_a_blender_title_draws(self) -> None:
        item = next(item for item in list_titles() if item["id"] == "letters-turn-in")
        self.assertTrue(preview(item, text="SING").startswith(PNG))

    def test_a_missing_engine_is_refused_not_replaced(self) -> None:
        from unittest import mock

        from cine_toaster import titles

        item = next(item for item in list_titles() if item["engine"] == "blender")
        with mock.patch.object(titles, "blender_binary", return_value=None), \
                self.assertRaisesRegex(ValidationError, "needs blender"):
            preview(item, text="X")


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class AssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        self.addCleanup(self._restore)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        text = scene.read_text(encoding="utf-8")
        # A card before the scene, and a caption over P2's take.
        text = text.replace("shots:\n  - n: 1\n",
                            "shots:\n  - n: 0\n    kind: title_card\n    duration: 2\n"
                            "    title: {id: card, text: THE REPLY, fade_in: 0.4, fade_out: 0.4}\n  - n: 1\n", 1)
        text = text.replace("  - n: 2\n", "  - n: 2\n    title: {id: caption, text: \"03:13\"}\n", 1)
        scene.write_text(text, encoding="utf-8")

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_a_card_and_a_caption_are_in_the_version(self) -> None:
        from cine_toaster.assembly import plan_scene, probe
        from cine_toaster.jobs import JobManager, JobStore
        from cine_toaster.project import load_scene

        scene = load_scene(self.root, "SC-030")
        self.assertFalse([f for f in scene["findings"] if f["code"].startswith("title_")])
        plan = plan_scene(self.root, scene)
        self.assertEqual([segment.shot for segment in plan.segments][:2], ["P0", "P1"])
        self.assertEqual(plan.segments[0].method, "title")
        self.assertNotIn("P0", plan.takes)  # a card is drawn, not chosen
        manager = JobManager(store=JobStore(Path(os.environ["XDG_STATE_HOME"]) / "jobs.sqlite"))
        self.addCleanup(manager.shutdown, wait=False)
        job = manager.wait(manager.submit("assemble", self.root, {"scene": "SC-030", "version": "v1"})["id"], timeout=180)
        self.assertEqual(job["state"], "succeeded", job["error"])
        manager.adopt(job["id"])
        media = self.root / load_scene(self.root, "SC-030")["assemblies"][-1]["media"]
        self.assertAlmostEqual(probe(media)["duration"], plan.duration, delta=0.3)
        # The card's words are there, lit, a second in.
        frame = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1.0", "-i", str(media), "-frames:v", "1",
                                "-vf", "crop=iw/2:ih/6:iw/4:ih*5/12,format=gray", "-f", "rawvideo", "-"],
                               capture_output=True, check=True).stdout
        self.assertGreater(max(frame), 150)

    def test_an_unknown_title_is_reported(self) -> None:
        from cine_toaster.project import load_scene

        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene.write_text(scene.read_text(encoding="utf-8").replace("id: caption", "id: no-such-title"), encoding="utf-8")
        codes = [f["code"] for f in load_scene(self.root, "SC-030")["findings"]]
        self.assertIn("title_unknown", codes)


if __name__ == "__main__":
    unittest.main()
