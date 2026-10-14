"""A shot whose picture is a composite (SPEC-0012 §4): checked when the scene loads, rendered in its version."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from cine_toaster.assembly import plan_scene, probe, render
from cine_toaster.project import load_production

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

SCENE = textwrap.dedent("""\
    scene: S1
    shots:
      - n: 1
        duration: 2
        label: A room with a window.
        composite:
          nodes:
            room:   {op: generate.source, take: CUT}
            sky:    {op: generate.source, file: plates/sky.mp4}
            window: {op: matte.shape, shape: rectangle, points: [[0.25, 0.25], [0.75, 0.75]]}
            out:    {op: merge.over, front: sky, back: room, matte: window}
          output: out
      - n: 2
        duration: 1
        label: Only a gradient.
        composite:
          nodes:
            out: {op: generate.gradient, kind: radial, colours: [[1, 1, 1, 1], [0, 0, 0, 1]]}
          output: out
""")


def run(command, expected_seconds=None, message="", span=None):
    subprocess.run(command, check=True, capture_output=True)


class CompositeShotTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\nframe: 160x90@24\npaths:\n  scenes: scenes\n")
        (self.root / "scenes" / "010" / "work").mkdir(parents=True)
        (self.root / "scenes" / "010" / "scene.yaml").write_text(SCENE)

    def clip(self, path: Path, colour: str, tone: bool) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        sound = "sine=f=440:d=3" if tone else "anullsrc"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color={colour}:s=160x90:r=24:d=3",
                        "-f", "lavfi", "-i", sound, "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        str(path)], check=True)

    def codes(self) -> list[str]:
        return sorted(f["code"] for f in load_production(self.root)["scenes"][0]["findings"]
                      if f["code"].startswith("composite"))

    def test_a_composite_that_names_what_is_not_there_is_refused_when_the_scene_loads(self) -> None:
        self.assertEqual(self.codes(), ["composite_input_missing", "composite_input_missing"])  # no take, no plate
        scene = self.root / "scenes" / "010" / "scene.yaml"
        scene.write_text(SCENE.replace("front: sky, back: room, matte: window", "front: sky, back: room, matte: 3"))
        self.assertIn("composite_type_mismatch", self.codes())

    @unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
    def test_the_window_shows_the_plate_and_the_take_keeps_its_sound(self) -> None:
        self.clip(self.root / "scenes" / "010" / "work" / "c01.mp4", "red", tone=True)
        self.clip(self.root / "plates" / "sky.mp4", "blue", tone=False)
        self.assertEqual(self.codes(), [])
        scene = load_production(self.root)["scenes"][0]
        plan = plan_scene(self.root, scene)
        self.assertEqual([segment.method for segment in plan.segments][1], "composite")
        out = self.root / "cut.mp4"
        render(self.root, plan, out, self.root / "work", run)
        made = probe(out)
        self.assertEqual((made["width"], made["height"]), (160, 90))
        self.assertAlmostEqual(made["duration"], 3.0, delta=0.1)

        def pixel(at: float, x: int, y: int) -> tuple[int, ...]:
            raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(at), "-i", str(out), "-frames:v", "1",
                                  "-vf", f"crop=4:4:{x - 2}:{y - 2},scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                  "-"], capture_output=True).stdout
            return tuple(raw)

        self.assertGreater(pixel(1.0, 80, 45)[2], 200)  # inside the window: the plate
        self.assertGreater(pixel(1.0, 10, 10)[0], 200)  # outside: the room
        centre, corner = pixel(2.5, 80, 45), pixel(2.5, 4, 4)
        self.assertGreater(centre[0], corner[0] + 60)   # the gradient shot: bright centre, dark corner
        loud = subprocess.run(["ffmpeg", "-hide_banner", "-t", "2", "-i", str(out), "-af", "volumedetect", "-f", "null",
                               "-"], capture_output=True, text=True).stderr
        self.assertGreater(float(loud.split("mean_volume: ")[1].split(" dB")[0]), -40)  # the take's tone is heard


if __name__ == "__main__":
    unittest.main()
