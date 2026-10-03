"""A 5.1 mix beside the stereo, in the same version (CT-0052, phase 1)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cine_toaster.assembly import Plan, Segment, render

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run(command, expected_seconds=None, message="", span=None):
    subprocess.run(command, check=True, capture_output=True)


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class SurroundTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def take(self, name: str, sound: str) -> str:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=gray:s=160x90:r=24:d=3",
                        "-f", "lavfi", "-i", f"aevalsrc='{sound}':s=48000:d=3", "-c:v", "libx264", "-pix_fmt",
                        "yuv420p", "-c:a", "aac", "-shortest", str(self.root / name)], check=True)
        return name

    def channel_levels(self, path: Path) -> dict[str, float]:
        """Mean level of each channel of the second (5.1) track, in dB."""

        levels = {}
        for channel in ("FL", "FR", "FC", "LFE", "SL", "SR"):
            completed = subprocess.run(
                ["ffmpeg", "-hide_banner", "-i", str(path), "-map", "0:a:1", "-af",
                 f"pan=mono|c0={channel},volumedetect", "-f", "null", "-"], capture_output=True, text=True)
            levels[channel] = float(completed.stderr.split("mean_volume: ")[1].split(" dB")[0])
        return levels

    def test_a_version_carries_stereo_first_and_a_51_where_dialogue_is_in_the_centre(self) -> None:
        from cine_toaster.sounds import expand, list_sounds, place

        speech = Segment("P1", "A", self.take("a.mp4", "0.4*sin(2*PI*300*t)"), 0.0, 3.0, normalize=False,
                         speech=(0.0, 3.0))
        catalog = {item["id"]: item for item in list_sounds()}
        beds, _ = expand({"id": "rain", "fade_in": 0, "fade_out": 0}, catalog, placed_on="scene")
        plan = Plan(scene="SC-1", segments=[speech], surround="5.1")
        plan.cues, _ = place({"shots": [], "ambience": beds}, plan.segments)
        out = self.root / "cut.mp4"
        render(self.root, plan, out, self.root / "work", run)
        streams = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,channels,channel_layout:"
             "stream_disposition=default:stream_tags=title,handler_name", "-of", "json", str(out)],
            capture_output=True, text=True).stdout)["streams"]
        audio = [stream for stream in streams if stream["codec_type"] == "audio"]
        self.assertEqual([(a["codec_name"], a["channels"]) for a in audio], [("aac", 2), ("ac3", 6)])
        self.assertEqual((audio[0]["disposition"]["default"], audio[1]["disposition"]["default"]), (1, 0))
        self.assertEqual(audio[1]["tags"].get("handler_name") or audio[1]["tags"].get("title"), "5.1")
        levels = self.channel_levels(out)
        # The speaking take is in the centre; the rain is a bed front and back; nothing low enough for the LFE.
        self.assertGreater(levels["FC"], levels["FL"])
        self.assertGreater(levels["SL"], -60)
        self.assertLess(levels["LFE"], -60)
        self.assertEqual(set(plan.loudness), {"stereo", "5.1"})

    def test_effects_reach_the_lfe_below_its_cutoff(self) -> None:
        from cine_toaster.sounds import expand, list_sounds, place

        silent = Segment("P1", "A", self.take("a.mp4", "0"), 0.0, 3.0, normalize=False)
        catalog = {item["id"]: item for item in list_sounds()}
        boom, _ = expand([{"id": "boom", "at": 0.5}], catalog)
        plan = Plan(scene="SC-1", segments=[silent], surround="5.1")
        plan.cues, _ = place({"shots": [{"id": "P1", "sounds": boom}]}, plan.segments)
        out = self.root / "cut.mp4"
        render(self.root, plan, out, self.root / "work", run)
        self.assertGreater(self.channel_levels(out)["LFE"], -60)

    def test_the_scene_asks_for_it_and_off_means_off(self) -> None:
        from cine_toaster.project import load_scene

        demo = Path(__file__).parents[1] / "examples" / "demo-project"
        root = self.root / "film"
        shutil.copytree(demo, root)
        manifest = root / "project.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8") + '\nsurround: "5.1"\n', encoding="utf-8")
        self.assertEqual(load_scene(root, "SC-030")["surround"], "5.1")
        scene_file = root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene_file.write_text(scene_file.read_text(encoding="utf-8").replace("shots:\n", "surround: false\nshots:\n", 1),
                              encoding="utf-8")
        self.assertEqual(load_scene(root, "SC-030")["surround"], "")


if __name__ == "__main__":
    unittest.main()
