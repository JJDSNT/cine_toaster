"""Reads that a view repeats are done once, and never outlive what they describe (the GUI's load time)."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cine_toaster import project
from cine_toaster.read_scope import read_scope
from cine_toaster.references import digest

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class ReadScopeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / "film"
        shutil.copytree(DEMO, self.root)

    def test_inside_a_view_the_production_is_read_once(self):
        with patch.object(project, "_load_production", wraps=project._load_production) as load:
            with read_scope():
                first = project.load_production(self.root)
                self.assertIs(project.load_production(self.root), first)
                with read_scope():  # a nested view joins the outer one
                    project.load_production(self.root)
            self.assertEqual(load.call_count, 1)

    def test_outside_a_view_every_read_is_fresh(self):
        with patch.object(project, "_load_production", wraps=project._load_production) as load:
            project.load_production(self.root)
            project.load_production(self.root)
            self.assertEqual(load.call_count, 2)
        with read_scope():
            project.load_production(self.root)
        with patch.object(project, "_load_production", wraps=project._load_production) as load:
            with read_scope():  # a new view does not see the last one's read
                project.load_production(self.root)
            self.assertEqual(load.call_count, 1)

    def test_the_style_catalogue_is_read_once_per_production_load(self):
        manifest = self.root / "project.yaml"
        manifest.write_text(manifest.read_text() + "style: {format: explainer}\n")
        from cine_toaster import styles

        with patch.object(styles, "list_styles", wraps=styles.list_styles) as catalogue:
            production = project.load_production(self.root)
        self.assertGreater(len(production["scenes"]), 1)
        self.assertEqual(catalogue.call_count, 1)
        self.assertEqual(production["scenes"][0]["style"]["format_by"], "Explainer")


class DigestCacheTests(unittest.TestCase):
    def test_a_changed_file_is_hashed_again(self):
        path = Path(tempfile.mkdtemp()) / "picture.png"
        path.write_bytes(b"first")
        first = digest(path)
        self.assertEqual(digest(path), first)
        path.write_bytes(b"second, longer")
        self.assertNotEqual(digest(path), first)
        # same size, new bytes: the modification time moves with them
        path.write_bytes(b"third, longer!")
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
        self.assertEqual(digest(path), __import__("hashlib").sha256(b"third, longer!").hexdigest())


if __name__ == "__main__":
    unittest.main()
