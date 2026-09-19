from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cine_toaster.web import _safe_project_path


class WebPathTests(unittest.TestCase):
    def test_rejects_paths_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.assertEqual(_safe_project_path(root, "scenes/a.mp4"), root / "scenes/a.mp4")
            self.assertIsNone(_safe_project_path(root, "../secret"))
            self.assertIsNone(_safe_project_path(root, "%2E%2E/secret"))


if __name__ == "__main__":
    unittest.main()
