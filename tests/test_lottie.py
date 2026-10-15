"""C6b stage D (CT-0078): a Lottie animation read as a source, by ThorVG, wherever a file is read."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import numpy as np

from cine_toaster.compositing import lottie
from cine_toaster.compositing.reference import decode_srgb, evaluate, read
from cine_toaster.errors import ValidationError

#: Made for these tests: a red rounded square, 80 by 80 in a 320 by 180 frame, 24 frames at 24 per second; it
#: fades in over the first half second and crosses from x 60 to x 260, eased.
BOX = Path(__file__).parent / "fixtures" / "lottie" / "box.json"
W, H, FPS = 320, 180, 24


def centre_x(frame: np.ndarray) -> float:
    return float(np.nonzero(frame[..., 3] > 0.5)[1].mean())


@unittest.skipUnless(lottie.available() and shutil.which("ffmpeg"), "ThorVG (the motion extra) or FFmpeg is missing")
class LottieTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_a_lottie_file_is_told_from_other_json(self) -> None:
        other = self.root / "data.json"
        other.write_text(json.dumps({"fr": 24, "name": "not an animation"}))
        self.assertTrue(lottie.is_lottie(BOX))
        self.assertFalse(lottie.is_lottie(other))

    def test_it_plays_its_own_animation_with_its_transparency(self) -> None:
        clip = read(BOX, 24, (W, H), FPS)
        self.assertLess(float(clip[0][..., 3].max()), 0.05)  # not yet faded in
        self.assertAlmostEqual(float(clip[6][..., 3].max()), 0.5, delta=0.02)  # half way, eased
        self.assertAlmostEqual(centre_x(clip[12]), 165.6, delta=1.0)
        self.assertAlmostEqual(centre_x(clip[23]), 259.5, delta=1.0)
        self.assertLess(float(clip[23][5, 5, 3]), 1e-6)  # around it, nothing
        red = clip[23][90, 260]
        np.testing.assert_allclose(red[:3], decode_srgb(np.array([1.0, 0.2, 0.1], np.float32)), atol=0.01)

    def test_it_keeps_its_own_frame_rate(self) -> None:
        """At 12 frames a second the film's frame 6 is half a second in: the animation's frame 12."""

        self.assertAlmostEqual(centre_x(read(BOX, 12, (W, H), 12)[6]), 165.6, delta=1.0)

    def test_it_holds_its_last_frame_or_is_gone(self) -> None:
        self.assertAlmostEqual(centre_x(read(BOX, 36, (W, H), FPS)[35]), 259.5, delta=1.0)
        self.assertLess(float(read(BOX, 36, (W, H), FPS, hold=False)[35][..., 3].max()), 1e-6)

    def test_it_can_be_stretched_over_another_length(self) -> None:
        self.assertAlmostEqual(centre_x(read(BOX, 48, (W, H), FPS, stretch_to=2.0)[24]), 165.6, delta=1.5)

    def test_it_is_fitted_to_the_frame_as_any_picture_is(self) -> None:
        clip = read(BOX, 24, (W, 2 * H), FPS)  # a taller frame: the animation fitted across, centred
        ys = np.nonzero(clip[23][..., 3] > 0.5)[0]
        self.assertAlmostEqual(float(ys.mean()), H, delta=1.5)

    def test_a_dotlottie_archive_is_read_too(self) -> None:
        archive = self.root / "box.lottie"
        with zipfile.ZipFile(archive, "w") as packed:
            packed.writestr("manifest.json", json.dumps({"animations": [{"id": "box"}]}))
            packed.writestr("animations/box.json", BOX.read_text())
        self.assertAlmostEqual(centre_x(read(archive, 24, (W, H), FPS)[12]), 165.6, delta=1.0)

    def test_a_layer_takes_it_as_it_takes_any_file(self) -> None:
        from cine_toaster.compositing.layers import compile_layers

        backdrop = self.root / "blue.png"
        from PIL import Image

        Image.new("RGB", (W, H), (0, 0, 255)).save(backdrop)
        graph, problems = compile_layers([{"source": str(backdrop)}, {"source": str(BOX)}])
        self.assertEqual(problems, [])
        frame = evaluate(graph, {}, frames=24, size=(W, H), fps=FPS)[23]
        self.assertGreater(float(frame[90, 260, 0]), 0.9)  # the box over the blue
        self.assertGreater(float(frame[90, 40, 2]), 0.9)  # the blue around it

    def test_without_thorvg_it_says_what_to_install(self) -> None:
        with mock.patch.object(lottie, "available", return_value=False):
            with self.assertRaises(ValidationError) as caught:
                read(BOX, 1, (W, H), FPS)
        self.assertIn("thorvg-python", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
