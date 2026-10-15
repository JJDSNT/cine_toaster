"""A still is the cut's frame: a shot's graph run at one instant, the same drawing the assembly makes (CT-0072)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from cine_toaster.assembly import _starts, plan_scene, render, still
from cine_toaster.cards import recipe
from cine_toaster.errors import ValidationError
from cine_toaster.project import load_production

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
try:
    import PIL  # noqa: F401

    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

SCENE = textwrap.dedent("""\
    scene: S1
    shots:
      - n: 1
        source: composed
        engine: text
        duration: 1
        label: A card.
        text:
          headline: Cut
          body: The plainest edit there is.
      - n: 2
        duration: 2
        label: Black to white over the shot.
        composite:
          nodes:
            black: {op: generate.solid, colour: [0, 0, 0, 1]}
            white: {op: generate.solid, colour: [1, 1, 1, 1]}
            time:  {op: curve.progress}
            out:   {op: merge.mix, a: black, b: white, by: time}
          output: out
""")


def run(command, expected_seconds=None, message="", span=None):
    subprocess.run(command, check=True, capture_output=True)


def picture(path: Path, frame: int = 0) -> np.ndarray:
    """A film's frame by its number (decoded in order: seeking can land a frame off), or a PNG, 0 to 1."""

    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, 90, 160, 3)[frame].astype(np.float32) / 255.0


class CardRecipeTests(unittest.TestCase):
    def test_a_card_is_a_graph_of_the_looks_colours(self) -> None:
        card = recipe({"text": {"headline": "cut", "body": "plain"}}, {"palette": {"background": "#ffffff"}})
        self.assertEqual(card["nodes"]["background"]["colour"], [1.0, 1.0, 1.0, 1.0])
        self.assertEqual(card["nodes"]["headline"]["text"], "CUT")
        self.assertEqual(card["output"], "body-over")
        self.assertNotIn("subhead", card["nodes"])


@unittest.skipUnless(HAS_FFMPEG and HAS_PILLOW, "FFmpeg or Pillow is missing")
class StillTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\nframe: 160x90@24\npaths:\n  scenes: scenes\n")
        (self.root / "scenes" / "010").mkdir(parents=True)
        (self.root / "scenes" / "010" / "scene.yaml").write_text(SCENE)
        self.scene = load_production(self.root)["scenes"][0]

    def test_a_still_is_the_frame_the_cut_shows_at_that_instant(self) -> None:
        plan = plan_scene(self.root, self.scene)
        self.assertEqual([segment.shot for segment in plan.segments], ["P1", "P2"])
        starts = _starts(plan)
        out = self.root / "cut.mp4"
        render(self.root, plan, out, self.root / "work", run)
        for shot, at in (("P1", 0.5), ("P2", 0.25), ("P2", 1.5)):
            drawn = still(self.root, plan_scene(self.root, self.scene), shot, self.root / f"{shot}-{at}.png", at)
            cut = picture(out, round((starts[[s.shot for s in plan.segments].index(shot)] + at) * 24))
            # The cut is H.264 with its colour subsampled. Measured: the right frame is within 1.3/255 on
            # average, a frame off is 3 to 7/255 on the moving shot; every 10x10 region within 4.6/255, so a
            # local divergence a global mean would hide is caught. A single pixel is x264's at a letter's edge
            # in this 160x90 frame: one encode of the same still at crf 18 gives 28 to 50/255 by the path it
            # takes (CT-0078, the shot drawn once) -- bounded at 64, a pixel off, not a picture off.
            error = np.abs(picture(drawn) - cut)
            self.assertLess(float(error.mean()), 2 / 255, (shot, at))
            regions = error.reshape(9, 10, 16, 10, 3).mean(axis=(1, 3, 4))
            self.assertLess(float(regions.max()), 6 / 255, (shot, at))
            self.assertLess(float(error.max()), 64 / 255, (shot, at))
        early = picture(self.root / "P2-0.25.png").mean()
        late = picture(self.root / "P2-1.5.png").mean()
        self.assertGreater(late, early + 0.3)  # the instant is the shot's own, not its first frame

    def test_the_cut_keeps_the_still_of_each_shot_a_graph_draws(self) -> None:
        plan = plan_scene(self.root, self.scene)
        render(self.root, plan, self.root / "cut.mp4", self.root / "work", run)
        self.assertEqual(sorted(plan.stills), ["P1", "P2"])
        card = picture(Path(plan.stills["P1"]))
        self.assertGreater(card.max(), 0.8)  # the words, in the look's ink
        self.assertLess(float(np.median(card)), 0.05)  # on its dark background
        middle = still(self.root, plan_scene(self.root, self.scene), "P2", self.root / "middle.png")
        self.assertLess(float(np.abs(picture(middle) - picture(Path(plan.stills["P2"]))).max()), 1.5 / 255)

    def test_a_shot_cut_from_a_take_has_no_still_of_its_own(self) -> None:
        plan = plan_scene(self.root, self.scene)
        plan.segments[0].composite = None
        with self.assertRaises(ValidationError):
            still(self.root, plan, "P1", self.root / "x.png")


if __name__ == "__main__":
    unittest.main()
