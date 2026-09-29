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
