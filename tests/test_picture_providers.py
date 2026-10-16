"""Master pictures are not bound to one model: the adapter is chosen production -> scene -> shot (ADR 0025)."""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from cine_toaster import spend
from cine_toaster.errors import ValidationError
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.pictures import picture_versions, plan_picture
from cine_toaster.project import load_production

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
THREAD = "0000-fake-thread"

try:
    from PIL import Image
except ImportError:  # the media extra
    Image = None

# A stand-in for the codex binary: prints the events the real one prints and saves a picture where
# its image_gen does, recording the arguments it was given.
FAKE_CODEX = f"""#!{sys.executable}
import json, os, sys, pathlib
home = pathlib.Path(os.environ["CODEX_HOME"])
if sys.argv[1:] == ["--version"]:
    print("codex-cli 0.0.0-fake"); sys.exit(0)
(home / "argv.json").write_text(json.dumps(sys.argv[1:]))
folder = home / "generated_images" / "{THREAD}"
folder.mkdir(parents=True, exist_ok=True)
from PIL import Image
Image.new("RGB", (1536, 1024), "grey").save(folder / "exec-1.png")
for event in ({{"type": "thread.started", "thread_id": "{THREAD}"}},
              {{"type": "turn.completed", "usage": {{"input_tokens": 1, "output_tokens": 1}}}}):
    print(json.dumps(event))
"""


@unittest.skipIf(Image is None, "Pillow is missing (the media extra)")
class PictureProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        keys = ("XDG_CACHE_HOME", "XDG_STATE_HOME", "CODEX_HOME", "CINE_TOASTER_CODEX", "RUNPOD_QWEN_ENDPOINT_ID")
        self.previous = {key: os.environ.get(key) for key in keys}
        self.addCleanup(self._restore)
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        os.environ.pop("RUNPOD_QWEN_ENDPOINT_ID", None)
        self.codex_home = base / "codex-home"
        self.codex_home.mkdir()
        os.environ["CODEX_HOME"] = str(self.codex_home)
        fake = base / "codex"
        fake.write_text(FAKE_CODEX, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["CINE_TOASTER_CODEX"] = str(fake)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        self.scene_dir = self.root / "scenes" / "030-echo-chamber"
        self.manager = JobManager(store=JobStore(base / "state" / "jobs.sqlite"))
        self.addCleanup(self.manager.shutdown, wait=False)

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def derive(self, lines: str) -> None:
        scene_file = self.scene_dir / "scene.yaml"
        text = scene_file.read_text(encoding="utf-8")
        scene_file.write_text(text.replace("  - n: 3\n", "  - n: 3\n    derive:\n" + lines, 1), encoding="utf-8")

    def set_project(self, text: str) -> None:
        manifest = self.root / "project.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8") + text, encoding="utf-8")

    def test_the_nearest_level_chooses_and_qwen_stays_the_default(self) -> None:
        self.derive("      with: [MARA]\n      request: Mara at the receiver, drawn in ink.\n")
        with self.assertRaisesRegex(ValidationError, "only repaints a picture"):
            plan_picture(self.root, load_production(self.root), "SC-030", "P3")

        self.set_project("\npictures:\n  provider: codex-image\n")
        plan = plan_picture(self.root, load_production(self.root), "SC-030", "P3")
        self.assertEqual((plan.provider, plan.provider_level, plan.cost), ("codex-image", "production", "quota"))
        self.assertIsNone(plan.source)
        self.assertEqual(plan.estimate_usd, 0.0)
        self.assertIn("Image 1 say who each person is", plan.prompt)

        scene_file = self.scene_dir / "scene.yaml"
        scene_file.write_text(scene_file.read_text(encoding="utf-8") + "\npictures:\n  provider: qwen-image-edit\n",
                              encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "only repaints"):
            plan_picture(self.root, load_production(self.root), "SC-030", "P3")

    def test_an_unknown_provider_is_named(self) -> None:
        self.derive("      provider: dream-machine\n      request: anything\n")
        with self.assertRaisesRegex(ValidationError, "No picture provider 'dream-machine' \\(shot\\)"):
            plan_picture(self.root, load_production(self.root), "SC-030", "P3")

    def test_a_codex_master_is_a_version_with_its_lineage_and_spends_no_dollars(self) -> None:
        self.derive("      provider: codex-image\n      with: [MARA]\n      request: Mara at the receiver.\n")
        spend.set_limit(0)  # a quota-paid picture is not held by a dollar budget
        job = self.manager.wait(self.manager.submit("derive_picture", self.root,
                                                    {"scene": "SC-030", "shot": "P3"})["id"], timeout=60)
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.manager.adopt(job["id"])

        work = self.scene_dir / "work"
        self.assertEqual([path.name for path in picture_versions(work, "p03")], ["p03-1.png"])
        record = json.loads((work / "p03-1.png.provenance.json").read_text())
        self.assertEqual((record["provider"], record["provider_level"], record["cost"]), ("codex-image", "shot", "quota"))
        self.assertIsNone(record["source"])
        self.assertIsNone(record["edge_score"])
        self.assertEqual(record["settings"]["thread"], THREAD)
        argv = json.loads((self.codex_home / "argv.json").read_text())
        self.assertEqual(argv[argv.index("-i") + 1:], [str(self.root / "cast" / "mara" / "reference" / "face.png")])
        self.assertEqual(spend.spent(), 0)


if __name__ == "__main__":
    unittest.main()
