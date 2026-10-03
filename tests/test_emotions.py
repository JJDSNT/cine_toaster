"""Emotions: described, asked of a model, put on a face (CT-0048)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.emotions import ARCS, INTENSITIES, acting, expand, face, list_emotions

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class CatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = {item["id"]: item for item in list_emotions()}

    def test_every_entry_says_what_shows_asks_at_each_intensity_and_has_a_face(self) -> None:
        self.assertGreaterEqual(len(self.catalog), 20)
        for item in self.catalog.values():
            with self.subTest(item["id"]):
                self.assertTrue(all(item["ask"][level] for level in INTENSITIES))
                self.assertTrue(all(item["voice"][level] for level in INTENSITIES))
                self.assertTrue(item["signals"]["face"] and item["signals"]["body"])
                self.assertTrue(item["facs"])
                for near in item["near"]:  # a pointer to a neighbour must land somewhere, or be a word only
                    self.assertIsInstance(near, str)

    def test_the_arc_moves_the_acting_over_the_shot(self) -> None:
        dread = self.catalog["dread"]
        self.assertTrue(acting(dread, "clear", "builds").startswith("at first only a stillness"))
        self.assertTrue(acting(dread, "clear", "fades").endswith("then it eases away"))
        self.assertTrue(acting(dread, "overwhelming", "breaks").startswith("suddenly, partway through"))
        self.assertEqual(set(ARCS), {"holds", "builds", "fades", "breaks"})

    def test_a_face_is_action_units_and_arkit_weights_scaled_by_intensity(self) -> None:
        subtle, full = face(self.catalog["joy"], "subtle"), face(self.catalog["joy"], "overwhelming")
        self.assertEqual([unit["au"] for unit in full["action_units"]], [6, 12, 25])
        self.assertEqual(full["arkit"]["mouthSmileLeft"], 1.0)
        self.assertLess(subtle["arkit"]["mouthSmileLeft"], full["arkit"]["mouthSmileLeft"])
        self.assertIn("browInnerUp", face(self.catalog["sadness"])["arkit"])
        self.assertEqual(face(self.catalog["shame"])["head"], {"head down": 0.42})

    def test_a_placement_is_checked(self) -> None:
        emotions, problems = expand([{"id": "fear", "who": "MARA", "intensity": "subtle"}, "no-such-feeling",
                                     {"id": "fear", "intensity": "huge"}, {"id": "fear", "arc": "spirals"},
                                     {"id": "fear", "who": "NOBODY"}, {"id": "fear", "mood": 3}],
                                    self.catalog, people={"MARA"})
        self.assertEqual([(item["id"], item["intensity"], item["arc"]) for item in emotions], [("fear", "subtle", "holds")])
        self.assertEqual(len(problems), 5)


class FilmTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "film"
        shutil.copytree(DEMO, self.root)
        scene_file = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene_file.write_text(scene_file.read_text(encoding="utf-8").replace(
            "  - n: 3\n", "  - n: 3\n    emotion: {id: dread, who: MARA, arc: builds, reason: the reply is her own voice}\n",
            1), encoding="utf-8")

    def test_the_prompt_asks_for_the_behaviour_and_a_line_takes_the_feelings_voice(self) -> None:
        from cine_toaster.generation import _acting
        from cine_toaster.project import load_production
        from cine_toaster.providers.ltx_prompt import Line, ShotPrompt, block_prompt

        production = load_production(self.root)
        scene = next(item for item in production["scenes"] if item["id"] == "SC-030")
        shot = scene["shots"][2]
        acting_words = _acting(production, scene, shot)
        self.assertEqual(len(acting_words), 1)
        self.assertIn("growing until the face goes still and pale", acting_words[0])
        prompt = block_prompt([ShotPrompt("A woman at a console", "locked off", "", [Line("The woman", "Hello")],
                                          "", acting_words)])
        self.assertIn("Growing until".lower(), prompt.lower())

    def test_the_brief_has_the_acting(self) -> None:
        from cine_toaster.brief import scene_brief
        from cine_toaster.project import load_scene

        brief = scene_brief(load_scene(self.root, "SC-030"))
        slots = [slot for slot in brief.slots() if slot.tag == "ACTING"]
        self.assertEqual(len(slots), 1)
        self.assertIn("MARA: dread, clear, builds", slots[0].text)
        self.assertIn("(the reply is her own voice)", slots[0].text)


if __name__ == "__main__":
    unittest.main()
