"""Styles: direction, animation techniques and formats, named by a production or a scene (CT-0049)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.styles import KINDS, list_styles

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class CatalogTests(unittest.TestCase):
    def test_every_kind_is_there_and_every_id_a_style_names_exists(self) -> None:
        from cine_toaster.camera_moves import list_moves
        from cine_toaster.cuts import CUT_TYPES
        from cine_toaster.titles import list_titles
        from cine_toaster.transitions import list_transitions

        styles = list_styles()
        self.assertEqual({item["kind"] for item in styles}, set(KINDS))
        self.assertEqual({item["axis"] for item in styles}, {"technique", "direction", "format"})
        moves = {item["id"] for item in list_moves()}
        transitions = {item["id"] for item in list_transitions()}
        titles = {item["id"] for item in list_titles()}
        for item in styles:
            with self.subTest(item["id"]):
                self.assertTrue(item["prompt"] and item["says"])
                self.assertLessEqual(set(item["camera"]["prefer"] + item["camera"]["avoid"]), moves)
                self.assertLessEqual(set(item["editing"]["prefer_transitions"] + item["editing"]["avoid_transitions"]),
                                     transitions)
                self.assertLessEqual(set(item["editing"]["prefer_cuts"] + item["editing"]["avoid_cuts"]), set(CUT_TYPES))
                self.assertLessEqual(set(item["titles"]), titles)
                # A name is for people: the words a model gets never carry one.
                for name in ("Ghibli", "Kubrick", "Anderson", "Wong Kar-wai", "Tarkovsky", "Villeneuve", "Dogme"):
                    self.assertNotIn(name, item["prompt"])

    def test_formats_carry_their_rules(self) -> None:
        catalog = {item["id"]: item for item in list_styles()}
        viral = catalog["viral-vertical"]["format"]
        self.assertEqual((viral["aspect"], viral["hook_seconds"], viral["captions"]), ("9:16", 2.0, True))
        self.assertTrue(catalog["commercial-spot"]["format"]["end_card"])
        self.assertEqual(catalog["stop-motion"]["format"]["frame_rate"], 12)
        self.assertIn("pastoral-anime", catalog)


class FilmTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "film"
        shutil.copytree(DEMO, self.root)
        self.manifest = self.root / "project.yaml"
        self.scene_file = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"

    def style(self, production: str = "", scene: str = "") -> dict:
        from cine_toaster.project import load_scene

        if production:
            self.manifest.write_text(self.manifest.read_text(encoding="utf-8") + f"\nstyle: {production}\n",
                                     encoding="utf-8")
        if scene:
            self.scene_file.write_text(self.scene_file.read_text(encoding="utf-8").replace(
                "shots:\n", f"style: {scene}\nshots:\n", 1), encoding="utf-8")
        return load_scene(self.root, "SC-030")

    def parts(self, scene: dict) -> list[tuple[str, str, str]]:
        return [(part["axis"], part["id"], part["level"]) for part in scene["style"]["parts"]]

    def test_the_axes_combine_and_each_cascades_on_its_own(self) -> None:
        scene = self.style(production="{technique: stop-motion, direction: Wes Anderson, format: viral-vertical}")
        self.assertEqual(self.parts(scene), [("technique", "stop-motion", "project"),
                                             ("direction", "symmetrical-tableau", "project"),
                                             ("format", "viral-vertical", "project")])
        style = scene["style"]
        self.assertTrue(style["prompt"].startswith("stop-motion animation"))  # the technique opens the prompt
        self.assertEqual(style["editing"]["shot_seconds"], [0.5, 4])          # the format decides the lengths
        self.assertEqual((style["format"]["aspect"], style["format"]["frame_rate"]), ("9:16", 12))
        self.assertEqual(style["performance"]["intensity"], "subtle")         # the direction's register
        self.assertNotIn("handheld", style["camera"]["prefer"])               # the technique avoids it
        # A scene changes one axis and keeps the others; `none` takes one away.
        scene = self.style(scene="{direction: noir, format: none}")
        self.assertEqual(self.parts(scene), [("technique", "stop-motion", "project"), ("direction", "noir", "scene")])

    def test_one_per_axis_and_each_on_its_own_axis(self) -> None:
        scene = self.style(scene="[stop-motion, pixel-art]")
        self.assertIn("names two techniques", " ".join(f["message"] for f in scene["findings"]))
        scene = self.style(scene="{format: noir}")
        self.assertIn("as its format, but it is a direction", " ".join(f["message"] for f in scene["findings"]))

    def test_the_nearest_style_wins_and_departures_are_advice(self) -> None:
        scene = self.style(production="contemplative-sci-fi")
        self.assertEqual(self.parts(scene), [("direction", "contemplative-sci-fi", "project")])
        scene = self.style(scene="viral-vertical")
        self.assertEqual(self.parts(scene), [("direction", "contemplative-sci-fi", "project"),
                                             ("format", "viral-vertical", "scene")])
        departures = [finding for finding in scene["findings"] if finding["code"] == "style_departure"]
        self.assertTrue(departures and all(finding["severity"] == "advice" for finding in departures))
        messages = " ".join(finding["message"] for finding in departures)
        self.assertIn("Viral vertical hooks within 2 s", messages)  # P1 holds 6 s before anything changes
        self.assertIn("Viral vertical holds a shot 0.5 to 4 s", messages)

    def test_a_style_is_found_by_the_name_people_know(self) -> None:
        scene = self.style(scene="ghibli")
        self.assertEqual(self.parts(scene), [("technique", "pastoral-anime", "scene")])
        self.assertEqual(scene["style"]["name"], "Pastoral anime (Ghibli-like)")

    def test_an_unknown_style_is_an_error(self) -> None:
        scene = self.style(scene="no-such-style")
        self.assertIn("style_unknown", {finding["code"] for finding in scene["findings"]})

    def test_the_style_sets_the_emotions_register_and_its_ceiling(self) -> None:
        self.scene_file.write_text(self.scene_file.read_text(encoding="utf-8").replace(
            "  - n: 3\n", "  - n: 3\n    emotion: [{id: dread, who: MARA}, {id: fear, who: MARA, intensity: overwhelming}]\n",
            1), encoding="utf-8")
        scene = self.style(scene="slow-cinema")
        feelings = scene["shots"][2]["emotion"]
        self.assertEqual([item["intensity"] for item in feelings], ["subtle", "overwhelming"])
        self.assertTrue(any("goes no further than clear" in finding["message"] for finding in scene["findings"]))

    def test_the_prompt_and_the_brief_carry_it(self) -> None:
        from cine_toaster.brief import scene_brief
        from cine_toaster.providers.ltx_prompt import ShotPrompt, block_prompt

        scene = self.style(scene="pastoral-anime")
        prompt = block_prompt([ShotPrompt("A field", "locked off")], scene["style"]["prompt"])
        self.assertIn("Style: hand-painted pastoral anime style", prompt)
        self.assertNotIn("Ghibli", prompt)
        slot = next(slot for slot in scene_brief(scene).slots() if slot.tag == "STYLE")
        self.assertIn("Pastoral anime", slot.text)


if __name__ == "__main__":
    unittest.main()
