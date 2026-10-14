"""Footage from outside: declared in the breakdown, fetched into a take with its origin (CT-0066)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from cine_toaster.footage import fetch
from cine_toaster.project import load_production
from cine_toaster.state import Actor

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
SCENE = textwrap.dedent("""\
    scene: S1
    shots:
      - n: 1
        source: archival
        duration: 2
        label: A launch.
        footage:
          url: {url}
          page: https://example.org/launch
          in: 1
          height: 54
          licence: {licence}
          credit: An Agency
""")


class FootageTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.root = self.base / "film"
        (self.root / "scenes" / "010").mkdir(parents=True)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
        patcher = mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.base / "cache")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, url: str = "https://example.org/launch.mp4", licence: str = "CC0 1.0") -> None:
        (self.root / "scenes" / "010" / "scene.yaml").write_text(SCENE.format(url=url, licence=licence))

    def findings(self) -> list[tuple[str, str]]:
        return [(f["code"], f["severity"]) for f in load_production(self.root)["scenes"][0]["findings"]]

    def test_declared_footage_is_advice_until_fetched_and_an_error_without_a_licence(self) -> None:
        self.write()
        self.assertEqual(self.findings(), [("footage_not_fetched", "advice")])
        self.write(licence='""')
        self.assertEqual(self.findings(), [("footage_incomplete", "error")])

    def test_footage_that_cannot_be_accounted_for_is_not_fetched(self) -> None:
        self.write(licence='""')
        calls: list = []
        results = fetch(self.root, load_production(self.root), Actor(id="t"), cutter=lambda *a: calls.append(a))
        self.assertEqual(([item.status for item in results], calls), (["refused"], []))

    @unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
    def test_the_stretch_becomes_the_shots_take_with_where_it_came_from(self) -> None:
        public = self.base / "public.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=24:d=5",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(public)], check=True)
        self.write(url=public.as_uri())
        results = fetch(self.root, load_production(self.root), Actor(id="t"))
        self.assertEqual([item.status for item in results], ["fetched"], results)
        take = load_production(self.root)["scenes"][0]["shots"][0]["takes"][0]
        self.assertEqual(take["media"], "scenes/010/work/c01.mp4")
        origin = take["provenance"]["origin"]
        self.assertEqual((origin["kind"], origin["source"], origin["licence"], origin["credit"]),
                         ("archival", "https://example.org/launch", "CC0 1.0", "An Agency"))
        self.assertEqual(origin["excerpt"], {"url": public.as_uri(), "in": 1.0, "duration": 2.0, "height": 54})
        size = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                               str(self.root / take["media"])], capture_output=True, text=True).stdout.strip()
        self.assertEqual(size, "96,54")  # fetched at the height asked, not the file's 90 lines
        seconds = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                        "csv=p=0", str(self.root / take["media"])],
                                       capture_output=True, text=True).stdout)
        self.assertAlmostEqual(seconds, 2.0, delta=0.1)
        self.assertEqual(self.findings(), [])
        # Fetching again leaves the take that is there.
        again = fetch(self.root, load_production(self.root), Actor(id="t"))
        self.assertEqual([item.status for item in again], ["kept"])


    @unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
    def test_footage_with_no_height_is_fetched_to_the_productions_frame(self) -> None:
        public = self.base / "public.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=24:d=5",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(public)], check=True)
        (self.root / "project.yaml").write_text("id: t\ntitle: T\nframe: 64x36@24\npaths:\n  scenes: scenes\n")
        self.write(url=public.as_uri())
        scene = self.root / "scenes" / "010" / "scene.yaml"
        scene.write_text(re.sub(r"\n *height: 54", "", scene.read_text()))
        fetch(self.root, load_production(self.root), Actor(id="t"))
        take = load_production(self.root)["scenes"][0]["shots"][0]["takes"][0]
        size = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                               str(self.root / take["media"])], capture_output=True, text=True).stdout.strip()
        self.assertEqual(size, "64,36")

if __name__ == "__main__":
    unittest.main()
