"""Conformance (ADR 0022 §7): a renderer is checked against the NumPy reference, never the reverse.

The first case: the `luma` join as an assembly makes it without a shader, against the `luma-wipe`
example graph evaluated by the reference. Measured on 2026-10-14 when FFmpeg filters drew it: the share
revealed agreed within 1 %, pixels more than 0.1 apart under 4 %, all at the edge. Since CT-0071 the
assembly draws it as a graph too; the test now holds the version's encoding (8-bit 4:2:0) to the same
bounds.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml

from cine_toaster.assembly import Plan, Segment, _resolve_join, render
from cine_toaster.compositing.reference import encode_srgb, evaluate, read
from cine_toaster.transitions import list_transitions

EXAMPLES = Path(__file__).parents[1] / "ai-context" / "specs" / "SPEC-0012-examples"
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
SIZE, FPS = (160, 90), 24


def run(command, expected_seconds=None, message="", span=None):
    subprocess.run(command, check=True, capture_output=True)


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class LumaJoinConformance(unittest.TestCase):
    def test_the_ffmpeg_luma_join_agrees_with_the_reference(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name, colour in (("a.mp4", "red"), ("b.mp4", "blue")):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                                f"color={colour}:s=160x90:r=24:d=4", "-f", "lavfi", "-i", "anullsrc", "-shortest",
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(root / name)], check=True)
            catalog = {item["id"]: item for item in list_transitions()}
            plan = Plan(scene="S", segments=[Segment("P1", "A", "a.mp4", 0.0, 4.0, normalize=False)])
            incoming = Segment("P2", "B", "b.mp4", 0.0, 4.0, normalize=False)
            _resolve_join(root, plan, {"transition": {"id": "luma", "duration_ms": 2000}}, incoming,
                          {"catalog": catalog, "gl": "no GL: the FFmpeg matte renderer"})
            plan.segments.append(incoming)
            render(root, plan, root / "cut.mp4", root / "work", run)
            decoded = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(root / "cut.mp4"), "-f", "rawvideo",
                                      "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
            ffmpeg = np.frombuffer(decoded, np.uint8).reshape(-1, 90, 160, 3).astype(np.float32)[48:96] / 255

        graph = yaml.safe_load((EXAMPLES / "luma-wipe.yaml").read_text())
        texture = read(catalog["luma"]["inputs"]["luma"], 1, SIZE, FPS)[0]
        red, blue = np.zeros((90, 160, 4), np.float32), np.zeros((90, 160, 4), np.float32)
        red[..., 0] = red[..., 3] = blue[..., 2] = blue[..., 3] = 1.0
        reference = encode_srgb(evaluate(graph, {"from": red, "to": blue, "texture": texture},
                                         frames=48, size=SIZE, fps=FPS)[..., :3])
        for frame in (6, 12, 24, 36, 42):
            with self.subTest(frame=frame):
                shown = float((ffmpeg[frame, ..., 2] > 0.5).mean())
                expected = float((reference[frame, ..., 2] > 0.5).mean())
                self.assertAlmostEqual(shown, expected, delta=0.02)
                apart = np.abs(ffmpeg[frame] - reference[frame]).max(-1)
                self.assertLess(float((apart > 0.1).mean()), 0.06)


if __name__ == "__main__":
    unittest.main()
