"""A master picture made by editing its source with the cast, as a new version (CT-0037)."""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster import jobs, spend
from cine_toaster.errors import ValidationError
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.pictures import picture_versions, plan_picture
from cine_toaster.project import load_production

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"

try:
    from PIL import Image
except ImportError:  # the media extra
    Image = None


def png(path: Path, size: tuple[int, int], colour: str) -> Path:
    Image.new("RGB", size, colour).save(path)
    return path


class FakeEditor:
    def __init__(self, image: bytes) -> None:
        self.image = image
        self.calls: list[tuple[str, dict | None]] = []

    def __call__(self, path: str, body: dict | None) -> dict:
        self.calls.append((path, body))
        if path.endswith("/run"):
            return {"id": "edit-1", "status": "IN_QUEUE"}
        return {"status": "COMPLETED", "delayTime": 1000, "executionTime": 30000,
                "output": {"image": base64.b64encode(self.image).decode()}}


@unittest.skipIf(Image is None, "Pillow is missing (the media extra)")
class PictureTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        keys = ("XDG_CACHE_HOME", "XDG_STATE_HOME", "RUNPOD_QWEN_ENDPOINT_ID")
        self.previous = {key: os.environ.get(key) for key in keys}
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        os.environ["RUNPOD_QWEN_ENDPOINT_ID"] = "test-editor"
        self.addCleanup(self._restore)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        scene = self.root / "scenes" / "030-echo-chamber"
        (scene / "blockout").mkdir()
        png(scene / "blockout" / "cam-a.png", (704, 384), "grey")
        text = (scene / "scene.yaml").read_text(encoding="utf-8")
        text = text.replace("  - n: 3\n", "  - n: 3\n    derive:\n      from: blockout/cam-a.png\n      with: [MARA]\n"
                            "      request: The figure becomes the woman in image 2, in profile.\n", 1)
        (scene / "scene.yaml").write_text(text, encoding="utf-8")
        self.scene_dir = scene
        buffer = io.BytesIO()
        Image.new("RGB", (1280, 704), "grey").save(buffer, "PNG")
        self.result = buffer.getvalue()
        self.manager = JobManager(store=JobStore(base / "state" / "jobs.sqlite"))
        self.addCleanup(self.manager.shutdown, wait=False)

    def _restore(self) -> None:
        jobs.GENERATION_TRANSPORT = None
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_the_plan_keeps_the_source_geometry_and_names_the_face(self) -> None:
        plan = plan_picture(self.root, load_production(self.root), "SC-030", "P3")
        self.assertEqual(plan.source.name, "cam-a.png")
        self.assertEqual(plan.size, (1408, 768))  # twice the render, in its proportion, multiples of 32
        self.assertEqual([(ref["member"], ref["path"].name) for ref in plan.references], [("MARA", "face.png")])
        self.assertTrue(plan.prompt.startswith("IMAGE 1 is the ONLY source of truth"))
        self.assertIn("The figure becomes the woman in image 2", plan.prompt)
        self.assertIn("for identity only", plan.prompt)
        self.assertEqual(plan.stem, "p03")

    def use_the_plate(self, source: str) -> None:
        scene_file = self.scene_dir / "scene.yaml"
        scene_file.write_text(scene_file.read_text(encoding="utf-8").replace("from: blockout/cam-a.png", f"from: {source}"),
                              encoding="utf-8")

    def test_a_picture_can_be_made_from_the_locations_plate(self) -> None:
        from cine_toaster.project import load_scene

        # The empty set, photographed from where CAM-A stands (SPEC-0010).
        location = self.root / "locations" / "listening-station"
        (location / "plates").mkdir()
        png(location / "plates" / "cam-a.png", (640, 352), "navy")
        yaml_file = location / "location.yaml"
        yaml_file.write_text(yaml_file.read_text(encoding="utf-8")
                             + "references:\n  - {path: plates/cam-a.png, kind: plate, camera: CAM-A}\n", encoding="utf-8")
        for source in ("location:CAM-A", "location"):  # named, or the shot's own camera (P3 is CAM-A's)
            self.use_the_plate(source)
            plan = plan_picture(self.root, load_production(self.root), "SC-030", "P3")
            self.assertEqual(plan.source, (location / "plates" / "cam-a.png").resolve())
            self.assertEqual(plan.size, (1280, 704))
            self.assertFalse([f for f in load_scene(self.root, "SC-030")["findings"] if f["code"] == "plate_missing"])
            self.scene_dir.joinpath("scene.yaml").write_text(
                self.scene_dir.joinpath("scene.yaml").read_text(encoding="utf-8").replace(f"from: {source}",
                                                                                           "from: blockout/cam-a.png"),
                encoding="utf-8")

    def test_a_missing_plate_is_said_before_anything_is_paid(self) -> None:
        from cine_toaster.project import load_scene

        self.use_the_plate("location:CAM-B")
        findings = [f for f in load_scene(self.root, "SC-030")["findings"] if f["code"] == "plate_missing"]
        self.assertEqual(len(findings), 1)
        self.assertIn("P3 is made from the plate of CAM-B in LISTENING-STATION, which has none", findings[0]["message"])
        with self.assertRaisesRegex(ValidationError, "made from the plate of CAM-B in LISTENING-STATION"):
            plan_picture(self.root, load_production(self.root), "SC-030", "P3")

    def test_a_shot_that_is_not_derived_is_told_so(self) -> None:
        with self.assertRaisesRegex(ValidationError, "does not say what picture it is made from"):
            plan_picture(self.root, load_production(self.root), "SC-030", "P1")

    def test_an_edit_becomes_a_version_beside_the_picture(self) -> None:
        fake = jobs.GENERATION_TRANSPORT = FakeEditor(self.result)
        spend.set_limit(2)
        work = self.scene_dir / "work"
        png(work / "p03.png", (1280, 704), "black")
        job = self.manager.wait(self.manager.submit("derive_picture", self.root, {"scene": "SC-030", "shot": "P3", "seed": 4})["id"], timeout=60)
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.manager.adopt(job["id"])
        self.assertEqual([path.name for path in picture_versions(work, "p03")], ["p03.png", "p03-1.png"])
        record = json.loads((work / "p03-1.png.provenance.json").read_text())
        self.assertEqual((record["kind"], record["seed"], record["references"][0]["member"]), ("picture-derivation", 4, "MARA"))
        self.assertEqual(record["source"]["path"], "scenes/030-echo-chamber/blockout/cam-a.png")
        self.assertGreater(record["edge_score"], 17)  # a flat grey edit of a flat grey source
        sent = fake.calls[0][1]["input"]
        self.assertEqual(sorted(key for key in sent if key.startswith("image_base64")), ["image_base64", "image_base64_2"])
        self.assertAlmostEqual(spend.spent(), 31 * 1.58 / 3600, places=4)


if __name__ == "__main__":
    unittest.main()
