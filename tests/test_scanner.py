from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cine_toaster.scanner import detect_adapter, project_id_for, scan_project


class ScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "production"
        (self.root / "cenas" / "030-echo" / "trabalho").mkdir(parents=True)
        (self.root / "project.yaml").write_text(
            "id: demo\ntitulo: Demo\n", encoding="utf-8"
        )
        (self.root / "cenas" / "030-echo" / "decupagem.yaml").write_text(
            "cena: SC-030\ntitulo: Echo\n", encoding="utf-8"
        )
        (self.root / "cenas" / "030-echo" / "trabalho" / "c03.mp4").write_bytes(b"video")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_detects_cine_toaster_manifest(self) -> None:
        self.assertEqual(detect_adapter(self.root), "cine-toaster")
        self.assertEqual(project_id_for(self.root), "demo")

    def test_generic_directory_identity_remains_path_scoped(self) -> None:
        generic = Path(self.temporary.name) / "generic"
        generic.mkdir()

        self.assertTrue(project_id_for(generic).startswith("prj_"))
        self.assertNotEqual(project_id_for(generic), project_id_for(self.root))

    def test_classifies_open_project_structure(self) -> None:
        by_path = {item.relative_path: item for item in scan_project(self.root)}
        self.assertEqual(by_path["project.yaml"].kind, "project_manifest")
        self.assertEqual(by_path["cenas/030-echo"].kind, "scene_directory")
        self.assertEqual(
            by_path["cenas/030-echo/decupagem.yaml"].kind,
            "scene_manifest",
        )
        self.assertEqual(
            by_path["cenas/030-echo/trabalho/c03.mp4"].kind,
            "shot_asset",
        )


if __name__ == "__main__":
    unittest.main()
