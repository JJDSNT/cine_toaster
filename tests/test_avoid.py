"""Negative guidance: what a generation must not do, kept apart and carried honestly (docs/generation.md)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class AvoidTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "film"
        shutil.copytree(DEMO, self.root)
        manifest = self.root / "project.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8") + "\navoid: [text or logos on screen]\n", encoding="utf-8")
        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        text = scene.read_text(encoding="utf-8").replace("shots:\n", "avoid: a second person in the room\nshots:\n", 1)
        scene.write_text(text.replace("  - n: 3\n", "  - n: 3\n    avoid: [Mara looking at the camera, Text or logos on screen]\n", 1),
                         encoding="utf-8")

    def test_the_cascade_is_kept_apart_from_the_directing_words(self) -> None:
        from cine_toaster.generation import avoidance
        from cine_toaster.project import load_production

        production = load_production(self.root)
        scene = next(item for item in production["scenes"] if item["id"] == "SC-030")
        shot = next(item for item in scene["shots"] if item["id"] == "P3")
        self.assertEqual(avoidance(production, scene, [shot]),
                         ["text or logos on screen", "a second person in the room", "Mara looking at the camera"])

    def test_the_video_provider_carries_it_natively_and_the_house_text_is_visible(self) -> None:
        from cine_toaster.providers.ltx import NEGATIVE_PROMPT, build_request, negative_text

        text = negative_text(["a second person in the room"])
        self.assertTrue(text.startswith(NEGATIVE_PROMPT) and text.endswith("a second person in the room"))
        frame = self.root / "frame.png"
        from PIL import Image

        Image.new("RGB", (64, 36)).save(frame)
        payload = build_request(image=frame, seconds=2, prompt="A room.", seed=1, avoid=("a second person in the room",))
        workflow = payload["input"]["workflow"] if "input" in payload else payload["workflow"]
        self.assertIn("a second person in the room", str(workflow))

    def test_a_picture_edit_says_it_in_the_prompt_and_the_plan_says_so(self) -> None:
        from cine_toaster.pictures import plan_picture
        from cine_toaster.project import load_production

        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene.write_text(scene.read_text(encoding="utf-8").replace(
            "  - n: 2\n", "  - n: 2\n    derive: {from: '1', with: [MARA], request: She is at the console.}\n", 1),
            encoding="utf-8")
        from PIL import Image

        Image.new("RGB", (64, 36)).save(scene.parent / "work" / "p01.png")  # shot 1's picture, to be edited
        plan = plan_picture(self.root, load_production(self.root), "SC-030", "P2")
        self.assertIn("Avoid: text or logos on screen; a second person in the room.", plan.prompt)
        self.assertEqual(plan.avoid_mechanism, "in the prompt: the edit model has no negative input")


if __name__ == "__main__":
    unittest.main()
