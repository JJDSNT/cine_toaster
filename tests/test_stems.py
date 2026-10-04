"""The cut's sound in its parts, for a final mix in a DAW (CT-0063)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels,sample_fmt,"
                          "bits_per_raw_sample:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def peak(path: Path) -> float:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True)
    return float(out.stderr.split("max_volume: ")[1].split(" dB")[0])


def lufs(path: Path) -> float:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True)
    return float(out.stderr.rsplit("I:", 1)[1].split("LUFS")[0])


def mean(path: Path, start: float, length: float = 1.0) -> float:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{start:.3f}", "-t", str(length), "-i", str(path),
                          "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    return float(out.stderr.split("mean_volume: ")[1].split(" dB")[0])


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class StemsTest(unittest.TestCase):
    def test_a_version_carries_its_sound_in_parts_that_make_the_mix(self) -> None:
        from cine_toaster.jobs import JobManager, JobStore
        from cine_toaster.project import load_scene

        base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, base, True)
        previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"], os.environ["XDG_STATE_HOME"] = str(base / "cache"), str(base / "state")
        self.addCleanup(lambda: [os.environ.pop(key, None) if value is None else os.environ.__setitem__(key, value)
                                 for key, value in previous.items()])
        root = base / "film"
        shutil.copytree(DEMO, root)
        scene_file = root / "scenes" / "030-echo-chamber" / "scene.yaml"
        text = scene_file.read_text(encoding="utf-8").replace(
            "shots:\n", "ambience: station-hum\nmusic: {id: tension-drone, from: P2}\nshots:\n", 1)
        scene_file.write_text(text.replace("  - n: 2\n", "  - n: 2\n    sounds: [door]\n", 1), encoding="utf-8")
        manager = JobManager(store=JobStore(base / "state" / "jobs.sqlite"))
        self.addCleanup(manager.shutdown, wait=True)
        job = manager.wait(manager.submit("assemble", root, {"scene": "SC-030", "stems": True})["id"], timeout=300)
        self.assertEqual(job["state"], "succeeded", job["error"])
        manager.adopt(job["id"])
        version = load_scene(root, "SC-030")["assemblies"][0]
        folder = root / (version["media"].removesuffix(".mp4") + ".stems")
        manifest = json.loads((folder / "stems.json").read_text())
        names = {item["stem"] for item in manifest["stems"]}
        self.assertTrue({"effects", "ambience", "music"} <= names)
        self.assertTrue(names & {"dialogue", "room"})
        self.assertIn("Ardour", manifest["import"])
        length = float(probe(root / version["media"])["format"]["duration"])
        for item in manifest["stems"]:
            info = probe(folder / item["file"])
            stream = info["streams"][0]
            self.assertEqual((stream["sample_rate"], stream["channels"], stream["sample_fmt"]), ("48000", 2, "s32"))
            self.assertAlmostEqual(float(info["format"]["duration"]), manifest["seconds"], places=2)
            self.assertLess(peak(folder / item["file"]), 0.0)  # not clipped, and not empty
        self.assertAlmostEqual(manifest["seconds"], length, delta=0.1)

        # Laid together at unity, the stems are the version's mix (before its limiter, on the same timeline).
        summed = base / "summed.wav"
        inputs = [part for item in manifest["stems"] for part in ("-i", str(folder / item["file"]))]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
                        f"amix=inputs={len(manifest['stems'])}:normalize=0[a]", "-map", "[a]", str(summed)], check=True)
        # Not sample by sample: the mix passed through AAC twice and a limiter with lookahead. What it sounds like:
        self.assertLess(abs(lufs(summed) - lufs(root / version["media"])), 0.5)
        for start in (0.1, 0.4, 0.7):  # three stretches along the cut (the demo's is short)
            self.assertLess(abs(mean(summed, start * length, length / 5)
                                - mean(root / version["media"], start * length, length / 5)), 0.5)

if __name__ == "__main__":
    unittest.main()
