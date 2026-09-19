from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cine_toaster.scanner import detect_adapter, scan_project


class ScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "singular"
        (self.root / "cenas" / "3-01" / "ltx" / "trabalho" / "_tomadas").mkdir(parents=True)
        (self.root / "cenas" / "3-01" / "ltx" / "versoes").mkdir(parents=True)
        (self.root / "roteiro").mkdir()
        (self.root / "elenco").mkdir()
        (self.root / "cenas" / "3-01" / "ltx" / "decupagem.yaml").write_text(
            "situacao: olhar errado aos 49 s\n", encoding="utf-8"
        )
        (self.root / "cenas" / "3-01" / "ltx" / "trabalho" / "_tomadas" / "c13-t23.mp4").write_bytes(b"video")
        (self.root / "cenas" / "3-01" / "ltx" / "versoes" / "cena-3-01-ltx-v12.mp4").write_bytes(b"render")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_detects_confyui_layout(self) -> None:
        self.assertEqual(detect_adapter(self.root), "confyui")

    def test_classifies_scene_take_and_version(self) -> None:
        by_path = {item.relative_path: item for item in scan_project(self.root)}
        self.assertEqual(by_path["cenas/3-01"].kind, "scene")
        self.assertEqual(
            by_path["cenas/3-01/ltx/trabalho/_tomadas/c13-t23.mp4"].kind,
            "take",
        )
        self.assertEqual(
            by_path["cenas/3-01/ltx/versoes/cena-3-01-ltx-v12.mp4"].kind,
            "scene_version",
        )
        self.assertIn(
            "olhar errado",
            by_path["cenas/3-01/ltx/decupagem.yaml"].text_content or "",
        )


if __name__ == "__main__":
    unittest.main()

