"""C8 step 3 (CT-0081): signals estimated by models, as records -- never metric, never downloaded implicitly,
pinned to their weights, their declared confidence apart from what is measured.

Two halves. Without models: the contract around the worker, with a stand-in that writes what a worker writes
(the catalog's refusals, fetching by hash, the record, invalidation by changed weights, repeatability
recorded rather than promised). With the vision environment, the models fetched and Blender: the three
models on a rendered scene whose geometry is known, measured against it."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from cine_toaster import estimates, models, signals
from cine_toaster.errors import ValidationError
from cine_toaster.state import Actor
from cine_toaster.titles import blender_binary

sys.path.insert(0, str(Path(__file__).parent))
from heavy import heavy, needs  # noqa: E402

TOOL = Actor(id="estimator", kind="system")
W, H = 64, 36


def plate(root: Path, frames: int = 4) -> str:
    (root / "plates").mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={W}x{H}:rate=24",
                    "-frames:v", str(frames), "-c:v", "ffv1", str(root / "plates" / "shot.mkv")], check=True)
    return "plates/shot.mkv"


class Fake:
    """What a worker writes, without a model: a depth of the frame's index, or a box of labels."""

    def __init__(self, noisy: bool = False) -> None:
        self.calls, self.noisy = 0, noisy

    def __call__(self, command: list[str]) -> None:
        self.calls += 1
        spec = json.loads(Path(command[2]).read_text())
        frames = np.load(spec["frames"])
        out = Path(spec["output"])
        out.mkdir(parents=True)
        count = len(frames)
        meta = {"python": "3.11", "torch": "fake", "device": "cpu", "threads": 1, "dtype": "float32",
                "determinism": {"seed": 0, "deterministic_algorithms": True}, "seconds": 0.0}
        if spec["runner"] == "sam2_video":
            result = np.zeros(frames.shape[:3], np.int32)
            result[:, 5:15, 5:20] = 1
            meta["declared"] = {"what": "object score", "by_object": {"1": [0.9] * count}}
        else:
            result = np.stack([np.full(frames.shape[1:3], 1.0 + index, np.float32) for index in range(count)])
            if self.noisy:
                result = result + np.float32(self.calls) * 1e-4
        np.save(out / "result.npy", result)
        (out / "meta.json").write_text(json.dumps(meta))


class Contract(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "film"
        self.root.mkdir()
        (self.root / "project.yaml").write_text("id: t\ntitle: T\n")
        self.store = Path(directory.name) / "models"
        environment = mock.patch.dict(os.environ, {"CINE_TOASTER_MODELS": str(self.store)})
        environment.start()
        self.addCleanup(environment.stop)
        for target, value in (("vision_python", Path("/usr/bin/true")), ("vision_unavailable_reason", "")):
            patch = mock.patch.object(models, target, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)

    def install(self, name: str) -> Path:
        """A model as `fetch` leaves it, its files made up but its weights' hashes the catalog's -- so `fetch`
        is given made-up bytes and the catalog's hashes are replaced for the test."""

        entry = models.MODELS[name]
        payload = {relative: f"{name}:{relative}".encode() for relative in entry["files"]}
        pinned = {relative: (hashlib.sha256(data).hexdigest() if expected else None)
                  for relative, data in payload.items() for expected in [entry["files"][relative]]}
        patch = mock.patch.dict(models.MODELS, {name: {**entry, "files": pinned,
                                                       **({"code": None} if entry.get("code") else {})}})
        patch.start()
        self.addCleanup(patch.stop)
        models.fetch(name, download=lambda url: payload[url.rsplit("/", 1)[1]])
        return models.model_directory(name)

    def test_the_catalog_refuses_what_its_licence_forbids_and_what_it_does_not_know(self) -> None:
        with self.assertRaisesRegex(ValidationError, "CC-BY-NC"):
            models.entry("depth-anything-v2-large")
        with self.assertRaisesRegex(ValidationError, "the catalog has"):
            models.entry("midas")
        self.assertTrue(all(entry["licence"] == "Apache-2.0" for entry in models.MODELS.values()))

    def test_nothing_is_downloaded_implicitly(self) -> None:
        plate(self.root)
        with self.assertRaisesRegex(ValidationError, "toast models fetch depth-anything-v2-small"):
            estimates.estimate(self.root, signal_id="d", model="depth-anything-v2-small", media="plates/shot.mkv",
                               actor=TOOL, run=Fake())
        self.assertFalse(self.store.exists())

    def test_fetching_keeps_only_files_of_the_pinned_hash(self) -> None:
        with self.assertRaisesRegex(ValidationError, "nothing kept"):
            models.fetch("depth-anything-v2-small", download=lambda url: b"something else")
        self.assertIsNone(models.installed("depth-anything-v2-small"))
        folder = self.install("depth-anything-v2-small")
        self.assertEqual(models.require("depth-anything-v2-small")["revision"],
                         models.MODELS["depth-anything-v2-small"]["revision"])
        (folder / "model.safetensors").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValidationError, "not the file fetched"):
            models.require("depth-anything-v2-small")

    def test_a_relative_depth_is_recorded_estimated_never_metric_with_what_made_it(self) -> None:
        self.install("depth-anything-v2-small")
        media = plate(self.root)
        made = estimates.estimate(self.root, signal_id="shot-depth", model="depth-anything-v2-small", media=media,
                                  actor=TOOL, first=1, count=2, run=Fake())
        record = signals.load_record(self.root, "shot-depth")
        self.assertEqual((record["kind"], record["origin"]), ("depth_relative", "estimated"))
        self.assertNotIn("camera", record)
        self.assertNotIn("unit", record["depth"])
        self.assertEqual(record["depth"]["quantity"], "inverse_z")
        from fractions import Fraction

        from cine_toaster import timebase

        self.assertEqual(timebase.from_record(record["clock"]["origin"]), Fraction(1, 24))  # frame 1 of the medium
        maker = record["provenance"][-1]["maker"]
        self.assertEqual((maker["name"], maker["version"], maker["licence"]),
                         ("depth-anything-v2-small", models.MODELS["depth-anything-v2-small"]["revision"],
                          "Apache-2.0"))
        self.assertIn("model.safetensors", maker["files"])
        self.assertEqual(maker["stretch"], {"first": 1, "count": 2})
        self.assertEqual(maker["determinism"]["repeat"], "not checked")
        pinned = [item for item in record["provenance"][-1]["inputs"] if "external" in item]
        self.assertTrue(any(item["external"].endswith("model.safetensors") for item in pinned))
        self.assertEqual(signals.status(self.root, "shot-depth")["quality"], "unknown")  # nothing declared
        self.assertEqual(made["frames"], 2)
        np.testing.assert_array_equal(signals.frame(self.root, "shot-depth", 1), np.full((H, W), 2.0, np.float32))

    def test_changed_weights_make_the_signal_stale(self) -> None:
        folder = self.install("depth-anything-v2-small")
        estimates.estimate(self.root, signal_id="shot-depth", model="depth-anything-v2-small",
                           media=plate(self.root), actor=TOOL, run=Fake())
        self.assertEqual(signals.status(self.root, "shot-depth")["stale"], [])
        (folder / "model.safetensors").write_bytes(b"other weights")
        stale = signals.status(self.root, "shot-depth")["stale"]
        self.assertTrue(any("model.safetensors" in reason for reason in stale), stale)
        with self.assertRaisesRegex(ValidationError, "stale"):
            signals.SignalReader(self.root, "shot-depth")
        (folder / "model.safetensors").unlink()
        self.assertTrue(any("not there" in reason for reason in signals.status(self.root, "shot-depth")["stale"]))

    def test_a_second_run_is_recorded_identical_or_not_never_promised(self) -> None:
        self.install("depth-anything-v2-small")
        media = plate(self.root)
        estimates.estimate(self.root, signal_id="same", model="depth-anything-v2-small", media=media, actor=TOOL,
                           repeat=True, run=Fake())
        repeat = signals.load_record(self.root, "same")["provenance"][-1]["maker"]["determinism"]["repeat"]
        self.assertEqual((repeat["identical"], repeat["max_difference"]), (True, 0.0))
        estimates.estimate(self.root, signal_id="drift", model="depth-anything-v2-small", media=media, actor=TOOL,
                           repeat=True, run=Fake(noisy=True))
        repeat = signals.load_record(self.root, "drift")["provenance"][-1]["maker"]["determinism"]["repeat"]
        self.assertFalse(repeat["identical"])
        self.assertAlmostEqual(repeat["max_difference"], 1e-4, places=6)

    def test_objects_are_instances_with_their_prompts_and_declared_scores_apart(self) -> None:
        self.install("sam2.1-hiera-tiny")
        media = plate(self.root)
        with self.assertRaisesRegex(ValidationError, "objects"):
            estimates.estimate(self.root, signal_id="who", model="sam2.1-hiera-tiny", media=media, actor=TOOL,
                               run=Fake())
        with self.assertRaisesRegex(ValidationError, "outside the stretch"):
            estimates.estimate(self.root, signal_id="who", model="sam2.1-hiera-tiny", media=media, actor=TOOL,
                               objects=[{"name": "mara", "frame": 9, "points": [[10, 10]]}], run=Fake())
        estimates.estimate(self.root, signal_id="who", model="sam2.1-hiera-tiny", media=media, actor=TOOL,
                           objects=[{"name": "mara", "points": [[10, 10]]}], run=Fake())
        record = signals.load_record(self.root, "who")
        self.assertEqual((record["labels"], record["labels_are"]), ({0: "nothing", 1: "mara"}, "instances"))
        self.assertEqual(record["provenance"][-1]["maker"]["objects"],
                         [{"label": 1, "name": "mara", "frame": 0, "points": [[10, 10]]}])
        quality = signals.status(self.root, "who")["quality"]
        self.assertEqual((quality["declared"], quality["measured"]), ([0.9] * 4, []))
        # Measured apart, against a person's matte of the same object.
        truth = np.zeros((H, W), np.int32)
        truth[5:15, 5:15] = 1
        signals.record_signal(self.root, signal_id="mara-matte", kind="segmentation", origin="authored",
                              frames=[truth] * 4, rate=24, media=media, labels={0: "nothing", 1: "mara"},
                              labels_are="instances", actor=Actor(id="editor"))
        measured = estimates.compare(self.root, signal_id="who", reference="mara-matte", actor=TOOL)
        self.assertEqual(measured["per_frame"], [{"mara": round(100 / 150, 4)}] * 4)
        quality = signals.status(self.root, "who")["quality"]
        self.assertEqual(quality["declared"], [0.9] * 4)  # untouched by the measurement
        self.assertEqual(quality["measured"][0]["against"], "signal:mara-matte")

    def test_a_medium_outside_the_production_is_refused(self) -> None:
        self.install("depth-anything-v2-small")
        with tempfile.TemporaryDirectory() as elsewhere:
            plate(Path(elsewhere))
            with self.assertRaisesRegex(ValidationError, "outside the production"):
                estimates.estimate(self.root, signal_id="d", model="depth-anything-v2-small",
                                   media=Path(elsewhere) / "plates" / "shot.mkv", actor=TOOL, run=Fake())


def _models_here() -> str:
    if not blender_binary():
        return "Blender is not installed"
    if models.vision_python() is None:
        return "no vision environment (make install-vision)"
    missing = [name for name in models.MODELS if models.installed(name) is None]
    return f"models not fetched: {', '.join(missing)}" if missing else ""


@heavy("renders with Blender and runs three models")
@unittest.skipIf(_models_here(), _models_here())
@needs("OpenEXR")
class OnAKnownScene(unittest.TestCase):
    """The three models on a rendered scene (tests/test_renders.py's: a wall, a ball, a box, a post and a
    drone; the camera dollying in), measured against the render's own depth and object index."""

    @classmethod
    def setUpClass(cls) -> None:
        import sys

        sys.path.insert(0, str(Path(__file__).parent))
        import test_renders
        from cine_toaster import renders

        cls.directory = tempfile.TemporaryDirectory()
        cls.root = root = Path(cls.directory.name)
        test_renders.production(root)
        renders.render_passes(root, render_id="room", camera="cam", first=1, last=3, size=(320, 180), fps=24,
                              recipe="scenes/room.json", samples=16, actor=TOOL)
        reader = renders.RenderReader(root, "room")
        pictures = []
        for index in range(3):  # the render as a viewer sees it, over a grey: a plate
            picture = reader.picture(index)
            rgb = np.clip(picture[..., :3] + (1 - picture[..., 3:]) * 0.18, 0, 1)
            srgb = np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * rgb ** (1 / 2.4) - 0.055)
            pictures.append((srgb * 255 + 0.5).astype(np.uint8))
        (root / "plates").mkdir()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "320x180",
                        "-r", "24", "-i", "-", "-c:v", "ffv1", str(root / "plates" / "room.mkv")],
                       input=np.stack(pictures).tobytes(), check=True)
        cls.table = {name: int(number) for number, name in reader.manifest["objects"].items()}
        cls.made = {
            "da2": estimates.estimate(root, signal_id="room-da2", model="depth-anything-v2-small",
                                      media="plates/room.mkv", actor=TOOL, repeat=True),
            "vda": estimates.estimate(root, signal_id="room-vda", model="video-depth-anything-small",
                                      media="plates/room.mkv", actor=TOOL, parameters={"input_size": 252}),
            "sam": estimates.estimate(root, signal_id="room-sam", model="sam2.1-hiera-tiny", media="plates/room.mkv",
                                      actor=TOOL, repeat=True,
                                      objects=[{"name": "ball", "points": [[66, 90]]},
                                               {"name": "box", "points": [[249, 73]]}]),
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def test_relative_depths_order_the_objects_as_the_geometry_does(self) -> None:
        for name in ("room-da2", "room-vda"):
            depth, objects = signals.SignalReader(self.root, name), signals.SignalReader(self.root, "room-objects")
            for index in range(3):
                values, labels = depth.frame(index), objects.frame(index)
                ball, box, wall = (float(values[labels == self.table[item]].mean()) for item in ("ball", "box", "wall"))
                self.assertGreater(ball, box, (name, index))  # inverse depth: nearer is larger
                self.assertGreater(box, wall, (name, index))
            measured = estimates.compare(self.root, signal_id=name, reference="room-depth", actor=TOOL)
            self.assertGreater(min(measured["per_frame"]), 0.75, (name, measured))

    def test_the_video_model_records_its_windows(self) -> None:
        maker = signals.load_record(self.root, "room-vda")["provenance"][-1]["maker"]
        self.assertEqual(maker["temporal"]["frames_together"], 3)
        self.assertEqual((maker["temporal"]["window"], maker["temporal"]["overlap"]), (32, 10))
        self.assertEqual(maker["code"]["commit"], models.MODELS["video-depth-anything-small"]["code"]["commit"])

    def test_objects_are_followed_through_the_dolly(self) -> None:
        measured = estimates.compare(self.root, signal_id="room-sam", reference="room-objects", actor=TOOL)
        for frame in measured["per_frame"]:
            self.assertGreater(min(frame.values()), 0.95, measured)
        quality = signals.status(self.root, "room-sam")["quality"]
        self.assertTrue(quality["declared"] and quality["measured"])

    def test_a_second_run_was_compared_and_recorded(self) -> None:
        for name in ("room-da2", "room-sam"):
            repeat = signals.load_record(self.root, name)["provenance"][-1]["maker"]["determinism"]["repeat"]
            self.assertIn("identical", repeat)  # whatever it was, it is on record
            if not repeat["identical"]:
                self.assertLess(repeat["max_difference"], 1e-3, name)


if __name__ == "__main__":
    unittest.main()
