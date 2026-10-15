"""SPEC-0012's range rule (CT-0077): every source enters the graph in linear light with its whole range."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cine_toaster.compositing.gl import gl_unavailable_reason
from cine_toaster.compositing.reference import conform_box, evaluate, read

HAS_TOOLS = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
try:
    import OpenEXR  # noqa: F401

    HAS_EXR = True
except ImportError:
    HAS_EXR = False


def exr_sequence(folder: Path, value: float, size: tuple[int, int] = (160, 90), frames: int = 3) -> str:
    import OpenEXR

    width, height = size
    pixels = np.zeros((height, width, 4), np.float32)
    pixels[height // 3: 2 * height // 3, width // 3: 2 * width // 3] = (value, value / 2, value / 8, 1.0)
    for index in range(1, frames + 1):
        OpenEXR.File({"type": OpenEXR.scanlineimage, "compression": OpenEXR.ZIP_COMPRESSION},
                     {"RGBA": pixels.astype(np.float16)}).write(str(folder / f"f_{index:04d}.exr"))
    return str(folder / "f_%04d.exr")


@unittest.skipUnless(HAS_TOOLS and HAS_EXR, "FFmpeg or OpenEXR is missing")
class RangeTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_a_float_source_keeps_its_light_above_white(self) -> None:
        clip = read(Path(exr_sequence(self.root, 4.0)), 3, (320, 180), 24)
        frame = clip[1]
        self.assertAlmostEqual(float(frame[..., 0].max()), 4.0, places=2)
        self.assertEqual((clip.colorspace, clip.alpha), ("Linear Rec.709 (sRGB)", "premultiplied"))  # the file's

    def test_a_look_tells_four_times_white_from_white(self) -> None:
        """Clipped on the way in, both would be the same after the look; kept, the brighter rolls off higher."""

        look = {"ports": {"picture": "picture"}, "output": "out",
                "nodes": {"out": {"op": "colour.lut", "in": "picture", "view": "ACES 2.0 - SDR 100 nits (Rec.709)"}}}
        bright = self.root / "bright"
        white = self.root / "white"
        bright.mkdir()
        white.mkdir()
        outputs = []
        for folder, value in ((bright, 4.0), (white, 1.0)):
            picture = read(Path(exr_sequence(folder, value)), 1, (160, 90), 24)
            outputs.append(float(evaluate(look, {"picture": picture}, frames=1, size=(160, 90), fps=24)[0, 45, 80, 0]))
        self.assertGreater(outputs[0], outputs[1] + 0.05)
        self.assertLess(outputs[0], 1.0)  # rolled off, not clipped

    def test_a_float_source_is_fitted_where_an_integer_one_is(self) -> None:
        """One rule for fitting a picture to the frame (`conform_box`): FFmpeg's filter for integer pictures, the
        float path's own resampling for float ones -- the same box."""

        import OpenEXR

        odd = np.ones((61, 100, 4), np.float32)
        OpenEXR.File({"type": OpenEXR.scanlineimage}, {"RGBA": odd.astype(np.float16)}).write(str(self.root / "o.exr"))
        from PIL import Image

        Image.new("RGB", (100, 61), (255, 255, 255)).save(self.root / "o.png")  # odd on purpose
        boxes = []
        for name in ("o.exr", "o.png"):
            alpha = read(self.root / name, 1, (320, 180), 24)[0][..., 3] > 0.5
            ys, xs = np.nonzero(alpha)
            boxes.append((xs.min(), xs.max(), ys.min(), ys.max()))
        for a, b in zip(*boxes):
            self.assertLessEqual(abs(int(a) - int(b)), 1)
        width, height, x, y = conform_box(100, 61, 320, 180)
        self.assertLessEqual(abs(int(boxes[0][0]) - x), 1)
        self.assertLessEqual(abs(int(boxes[0][1]) - (x + width - 1)), 1)

    @unittest.skipIf(gl_unavailable_reason(), "no GL context here")
    def test_gl_keeps_the_light_too(self) -> None:
        from cine_toaster.compositing.gl import renderer_for

        graph = {"ports": {}, "output": "out",
                 "nodes": {"out": {"op": "generate.source", "file": exr_sequence(self.root, 4.0)}}}
        frame = next(iter(renderer_for(graph).evaluate(graph, {}, frames=1, size=(320, 180), fps=24, stream=True)))
        self.assertAlmostEqual(float(frame[..., 0].max()), 4.0, places=2)


if __name__ == "__main__":
    unittest.main()
