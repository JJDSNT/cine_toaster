from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cine_toaster.index import ProjectIndex, build_index, index_path_for


class IndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        base = Path(self.temporary.name)
        self.root = base / "project"
        self.cache = base / "cache"
        (self.root / "cenas" / "1-01").mkdir(parents=True)
        (self.root / "roteiro").mkdir()
        (self.root / "elenco").mkdir()
        (self.root / "cenas" / "1-01" / "decupagem.yaml").write_text(
            "nota: manter o olhar para a direita\n", encoding="utf-8"
        )
        self.environment = patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.cache)})
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary.cleanup()

    def test_builds_cache_outside_project_and_searches_text(self) -> None:
        before = sorted(path.relative_to(self.root) for path in self.root.rglob("*"))
        summary = build_index(self.root)
        after = sorted(path.relative_to(self.root) for path in self.root.rglob("*"))

        self.assertEqual(before, after)
        self.assertTrue(index_path_for(self.root).is_file())
        self.assertNotIn(self.root, index_path_for(self.root).parents)
        self.assertEqual(summary.adapter, "confyui")

        index = ProjectIndex(self.root)
        matches = index.search("olhar para a direita")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["kind"], "scene_specification")
        self.assertIn("olhar para a direita", matches[0]["snippet"])


if __name__ == "__main__":
    unittest.main()

