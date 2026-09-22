"""A demo that does not build proves nothing."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.build import BuildError, build, draw_card
from cine_toaster.transitions import list_transitions


EXAMPLES = Path(__file__).parents[1] / "examples"
HAS_FFMPEG = shutil.which("ffmpeg") is not None
try:
    import PIL  # noqa: F401

    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


class TransitionRenderingTests(unittest.TestCase):
    def test_every_catalog_item_declares_how_it_renders(self) -> None:
        """A renderer never guesses a substitution the author did not choose."""

        for item in list_transitions(EXAMPLES / "amiga-demo-reel"):
            declared = item.get("render") or {}
            self.assertTrue(declared.get("ffmpeg"), item["id"])
            self.assertTrue(declared.get("ffmpeg_note"), item["id"])

    def test_a_transition_with_no_rendering_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            shutil.copytree(EXAMPLES / "amiga-demo-reel", root / "reel")
            manifest = root / "reel" / "transitions" / "amiga-copper-bars" / "transition.toml"
            text = manifest.read_text(encoding="utf-8")
            manifest.write_text(text.split("[render]")[0], encoding="utf-8")
            with self.assertRaises(BuildError) as caught:
                build(root / "reel")
        self.assertIn("declares no FFmpeg rendering", str(caught.exception))


@unittest.skipUnless(HAS_PILLOW, "the media extra is not installed")
class CardTests(unittest.TestCase):
    def test_a_card_is_drawn_from_the_look(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "card.png"
            draw_card(
                {"engine": "title", "text": {"headline": "Copper Sky"}},
                {"palette": {"background": "#101020", "ink": "#ffffff"}},
                destination,
            )
            with Image.open(destination) as image:
                self.assertEqual(image.size, (1280, 720))
                self.assertEqual(image.getpixel((5, 5)), (16, 16, 32))

    def test_the_same_shot_draws_the_same_card(self) -> None:
        """A card is data, which is what makes a reel reproducible."""

        shot = {"engine": "title", "text": {"headline": "Twice"}}
        with tempfile.TemporaryDirectory() as raw:
            first = draw_card(shot, None, Path(raw) / "a.png").read_bytes()
            second = draw_card(shot, None, Path(raw) / "b.png").read_bytes()
        self.assertEqual(first, second)


@unittest.skipUnless(HAS_FFMPEG and HAS_PILLOW, "ffmpeg or the media extra is missing")
class BuildTests(unittest.TestCase):
    def test_the_reel_renders_to_a_real_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "reel"
            shutil.copytree(EXAMPLES / "amiga-demo-reel", root)
            result = build(root)

            self.assertTrue(result.output.is_file())
            self.assertEqual(result.shots, 7)
            self.assertEqual(result.transitions, 5)
            self.assertGreater(result.duration_seconds, 10)
            # No narration was generated, so the render is silent and says so.
            self.assertFalse(result.audio)
            self.assertEqual(result.output.parent.name, "renders")

            # The cards are kept: a composed shot has no take, so the frame the
            # tool drew is the only visual feedback the scene can have.
            self.assertEqual(result.stills, 7)
            self.assertTrue((root / "stills" / "SC-020" / "P1.png").is_file())
            self.assertFalse((root / "renders" / ".work").exists())

    def test_a_production_with_no_composed_shots_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "scenes" / "010").mkdir(parents=True)
            (root / "project.yaml").write_text("id: x\ntitle: X\n", encoding="utf-8")
            (root / "scenes" / "010" / "scene.yaml").write_text(
                "scene: SC-010\nshots:\n  - n: 1\n    source: generated\n"
                "    duration: 2\n    label: A.\n",
                encoding="utf-8",
            )
            with self.assertRaises(BuildError) as caught:
                build(root)
        self.assertIn("no composed shots", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
