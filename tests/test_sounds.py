"""Sound on the cut: a catalog of ambiences, effects, Foley and music, and its sources (CT-0048)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from cine_toaster.sounds import duck_expression, expand, list_sounds, place

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run(command, expected_seconds=None, message="", span=None):
    subprocess.run(command, check=True, capture_output=True)


class CatalogTests(unittest.TestCase):
    def test_the_built_in_catalog_is_generated_and_ours(self) -> None:
        catalog = {item["id"]: item for item in list_sounds()}
        for sound_id in ("room-tone", "station-hum", "hospital-room", "door", "flatline", "tension-drone"):
            self.assertIn(sound_id, catalog)
        self.assertEqual({item["category"] for item in catalog.values()}, {"ambience", "effect", "foley", "music"})
        self.assertTrue(all(item["exists"] and item["licence"] == "ours (generated)" for item in catalog.values()))
        self.assertTrue(catalog["room-tone"]["params"]["loop"])
        self.assertEqual(catalog["tension-drone"]["params"]["duck"], 10.0)

    def test_placements_take_their_defaults_and_bad_ones_are_said(self) -> None:
        catalog = {item["id"]: item for item in list_sounds()}
        sounds, problems = expand(["door", {"id": "alarm", "at": 1.5, "level": -20}], catalog)
        self.assertEqual(problems, [])
        self.assertEqual((sounds[0]["level"], sounds[1]["at"], sounds[1]["level"]), (-28.0, 1.5, -20.0))
        _, problems = expand([{"id": "no-such-sound"}, {"id": "door", "volume": 3}, {"id": "door", "at": -1}], catalog)
        self.assertEqual(len(problems), 3)
        beds, problems = expand({"id": "room-tone", "from": "p2", "until": "P9"}, catalog, placed_on="scene",
                                shots=("P1", "P2", "P3"))
        self.assertEqual((beds, len(problems)), ([], 1))
        self.assertIn("P9, which is not one of its shots", problems[0])

    def test_cues_are_placed_on_the_cut(self) -> None:
        catalog = {item["id"]: item for item in list_sounds()}
        segments = [SimpleNamespace(shot=shot, start=1.0, end=1.0 + length)
                    for shot, length in (("P1", 2.0), ("P2", 3.0), ("P3", 4.0))]
        shot_sounds, _ = expand([{"id": "door", "at": 0.5}, {"id": "beep", "at": 9}], catalog)
        ambience, _ = expand({"id": "room-tone", "until": "P3"}, catalog, placed_on="scene")
        music, _ = expand({"id": "tension-drone", "from": "P2", "at": 1.0}, catalog, placed_on="scene")
        scene = {"shots": [{"id": "P1"}, {"id": "P2", "sounds": shot_sounds}, {"id": "P3"}],
                 "ambience": ambience, "music": music}
        cues, notes = place(scene, segments)
        where = {cue["id"]: (cue["start"], cue["length"]) for cue in cues}
        self.assertEqual(where["door"], (2.5, 1.0))
        self.assertEqual(where["room-tone"], (0.0, 5.0))  # stops where P3 begins
        self.assertEqual(where["tension-drone"], (3.0, 6.0))
        self.assertNotIn("beep", where)
        self.assertTrue(any("starts after the shot is cut" in note for note in notes))

    def test_the_duck_is_a_ramp_under_each_line(self) -> None:
        self.assertEqual(duck_expression([], 10), "1")
        expression = duck_expression([(1.0, 2.0), (4.0, 5.0)], 10)
        self.assertIn("max(", expression)
        self.assertTrue(expression.startswith("1-0.6838*"))


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class MixTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)

    def level(self, path: Path, start: float, length: float) -> float:
        completed = subprocess.run(["ffmpeg", "-hide_banner", "-ss", str(start), "-t", str(length), "-i", str(path),
                                    "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
        return float(completed.stderr.split("mean_volume: ")[1].split(" dB")[0])

    def test_music_is_lowered_under_speech_and_effects_land_where_placed(self) -> None:
        from cine_toaster.sounds import mix

        picture = self.base / "cut.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=black:s=64x36:d=6",
                        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "6", "-c:v", "libx264",
                        "-c:a", "aac", "-shortest", str(picture)], check=True)
        catalog = {item["id"]: item for item in list_sounds()}
        music, _ = expand({"id": "tension-drone", "fade_in": 0, "fade_out": 0}, catalog, placed_on="scene")
        effect, _ = expand({"id": "impact", "at": 5.0}, catalog)
        cues, _ = place({"shots": [{"id": "P1", "sounds": effect}], "music": music},
                        [SimpleNamespace(shot="P1", start=0.0, end=6.0)])
        out = self.base / "mixed.mp4"
        laid = mix(picture, cues, catalog, [(2.0, 3.0)], out, self.base / "work", run)
        self.assertEqual({item["id"] for item in laid}, {"tension-drone", "impact"})
        clear, under = self.level(out, 0.5, 1.0), self.level(out, 2.2, 0.6)
        self.assertGreater(clear - under, 7.0)  # 10 dB down under the line, a little less with the ramps
        self.assertGreater(self.level(out, 5.0, 0.3), self.level(out, 4.4, 0.3) + 3)

    def test_an_assembly_lays_the_scenes_sound_and_the_version_says_so(self) -> None:
        from cine_toaster.jobs import JobManager, JobStore
        from cine_toaster.project import load_scene

        previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"], os.environ["XDG_STATE_HOME"] = str(self.base / "cache"), str(self.base / "state")
        self.addCleanup(lambda: [os.environ.pop(key, None) if value is None else os.environ.__setitem__(key, value)
                                 for key, value in previous.items()])
        root = self.base / "film"
        shutil.copytree(DEMO, root)
        scene_file = root / "scenes" / "030-echo-chamber" / "scene.yaml"
        text = scene_file.read_text(encoding="utf-8").replace(
            "shots:\n", "ambience: station-hum\nmusic: {id: tension-drone, from: P2}\nshots:\n", 1)
        scene_file.write_text(text.replace("  - n: 2\n", "  - n: 2\n    sounds: [door]\n", 1), encoding="utf-8")
        manager = JobManager(store=JobStore(self.base / "state" / "jobs.sqlite"))
        self.addCleanup(manager.shutdown, wait=False)
        job = manager.wait(manager.submit("assemble", root, {"scene": "SC-030"})["id"], timeout=180)
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.assertEqual({item["id"] for item in job["result"]["summary"]["sound"]},
                         {"station-hum", "tension-drone", "door"})
        manager.adopt(job["id"])
        version = load_scene(root, "SC-030")["assemblies"][0]
        self.assertIn("Sound laid: door (shot", version["summary"])
        # Beside the version, where its speech is heard: a sequence's music ducks under it.
        self.assertTrue((root / (version["media"] + ".speech.json")).is_file())


class ProjectTests(unittest.TestCase):
    def test_a_scene_names_its_beds_and_a_provisional_recording_is_said(self) -> None:
        from cine_toaster.project import load_scene
        from cine_toaster.sound_sources import write_item

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "film"
            shutil.copytree(DEMO, root)
            manifest = write_item(root, "hologram", name="Hologram", category="effect", says="A hologram hums",
                                  file="hologram.wav", provenance="Sonniss GDC 2023 (archive.org mirror, unofficial)",
                                  licence="Sonniss GDC royalty-free", status="provisional")
            (manifest.parent / "hologram.wav").write_bytes(b"")
            scene_file = root / "scenes" / "030-echo-chamber" / "scene.yaml"
            text = scene_file.read_text(encoding="utf-8").replace(
                "shots:\n", "ambience: [room-tone, {id: rain, from: P2}]\nmusic: no-such-score\nshots:\n", 1)
            scene_file.write_text(text.replace("  - n: 2\n", "  - n: 2\n    sounds: [hologram]\n", 1),
                                  encoding="utf-8")
            scene = load_scene(root, "SC-030")
            self.assertEqual([bed["id"] for bed in scene["ambience"]], ["room-tone", "rain"])
            codes = {finding["code"]: finding for finding in scene["findings"]}
            self.assertIn("no-such-score", codes["sound_problem"]["message"])
            self.assertIn("archive.org mirror", codes["sound_provisional"]["message"])
            self.assertEqual(scene["shots"][1]["sounds"][0]["id"], "hologram")


class SourceTests(unittest.TestCase):
    def test_a_library_on_disk_is_registered_with_its_licences(self) -> None:
        from cine_toaster.sound_sources import import_library, slug

        self.assertEqual(slug("Câmara médica: bip"), "camara-medica-bip")
        with tempfile.TemporaryDirectory() as directory:
            library, root = Path(directory) / "library", Path(directory) / "film"
            (library / "freesound").mkdir(parents=True)
            (library / "freesound" / "1_door.mp3").write_bytes(b"")
            (library / "room_room tone_boiler.wav").write_bytes(b"")
            # SINGULAR's own manifest columns are read as they are.
            (library / "MANIFESTO.csv").write_text(
                "arquivo,origem,licenca,url,situacao,uso,data\n"
                "freesound/1_door.mp3,\"Freesound, por someone\",CC0 1.0,https://freesound.org/s/1/,previa-hq,porta,x\n"
                "room_room tone_boiler.wav,Sonniss,Sonniss GDC,https://archive.org/x,provisorio,,x\n"
                "missing.wav,Sonniss,Sonniss GDC,,provisorio,gone,x\n", encoding="utf-8")
            made = import_library(root, library, prefix="lib-")
            self.assertEqual(made, ["lib-porta", "lib-room-room-tone-boiler"])
            catalog = {item["id"]: item for item in list_sounds(root)}
            self.assertEqual((catalog["lib-porta"]["status"], catalog["lib-porta"]["licence"]), ("preview-hq", "CC0 1.0"))
            self.assertEqual(catalog["lib-room-room-tone-boiler"]["category"], "ambience")
            self.assertEqual(catalog["lib-room-room-tone-boiler"]["status"], "provisional")
            self.assertTrue(catalog["lib-porta"]["exists"])
            self.assertEqual(import_library(root, library, prefix="lib-"), [])  # nothing registered twice


if __name__ == "__main__":
    unittest.main()
