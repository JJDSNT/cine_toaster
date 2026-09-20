from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.application import (
    ProjectIdentityConflictError,
    ProjectLocator,
    ProjectManager,
    UnsupportedProjectSourceError,
)


def write_external_project(root: Path, project_id: str, title: str) -> None:
    root.mkdir(parents=True)
    (root / "project.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                f"id: {project_id}",
                f"titulo: {title}",
                "caminhos:",
                "  cenas: cenas",
            ]
        ),
        encoding="utf-8",
    )
    (root / "scenes").mkdir()


class ProjectManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.first_storage = tempfile.TemporaryDirectory()
        self.second_storage = tempfile.TemporaryDirectory()
        self.first_root = Path(self.first_storage.name) / "Client Film With Spaces"
        self.second_root = Path(self.second_storage.name) / "Independent Documentary"
        write_external_project(self.first_root, "client-film", "Client Film")
        write_external_project(
            self.second_root,
            "independent-documentary",
            "Independent Documentary",
        )

    def tearDown(self) -> None:
        self.first_storage.cleanup()
        self.second_storage.cleanup()

    def test_registers_unrelated_external_projects(self) -> None:
        manager = ProjectManager()

        first = manager.open_project(self.first_root)
        second = manager.open_project(self.second_root)

        self.assertEqual(first.project_id, "client-film")
        self.assertEqual(second.project_id, "independent-documentary")
        self.assertEqual(first.local_root, self.first_root.resolve())
        self.assertIn("Client%20Film%20With%20Spaces", first.locator.uri)
        self.assertEqual(
            [project.project_id for project in manager.list_projects()],
            ["client-film", "independent-documentary"],
        )

    def test_opening_same_project_and_locator_is_idempotent(self) -> None:
        manager = ProjectManager()

        first = manager.open_project(self.first_root)
        reopened = manager.open_project(ProjectLocator.from_path(self.first_root))

        self.assertIs(reopened, first)
        self.assertEqual(len(manager.list_projects()), 1)

    def test_rejects_duplicate_identity_at_another_location(self) -> None:
        duplicate = Path(self.second_storage.name) / "Copied Client Film"
        write_external_project(duplicate, "client-film", "Copied Client Film")
        manager = ProjectManager()
        manager.open_project(self.first_root)

        with self.assertRaises(ProjectIdentityConflictError) as raised:
            manager.open_project(duplicate)

        self.assertEqual(raised.exception.project_id, "client-film")
        self.assertNotEqual(raised.exception.existing, raised.exception.incoming)
        self.assertEqual(len(manager.list_projects()), 1)

    def test_manifest_identity_survives_a_move(self) -> None:
        before = ProjectManager().open_project(self.first_root)
        moved = Path(self.first_storage.name) / "Relocated" / "Client Film"
        moved.parent.mkdir()
        shutil.move(self.first_root, moved)

        after = ProjectManager().open_project(moved)

        self.assertEqual(before.project_id, after.project_id)
        self.assertNotEqual(before.locator, after.locator)

    def test_closes_by_explicit_project_identity(self) -> None:
        manager = ProjectManager()
        project = manager.open_project(self.first_root)

        closed = manager.close_project("client-film")

        self.assertIs(closed, project)
        self.assertEqual(manager.list_projects(), ())
        with self.assertRaisesRegex(KeyError, "Project is not open"):
            manager.get("client-film")

    def test_rejects_unsupported_source_scheme(self) -> None:
        manager = ProjectManager()
        locator = ProjectLocator("s3", "s3://studio/client-film")

        with self.assertRaisesRegex(
            UnsupportedProjectSourceError,
            "Unsupported project source scheme: s3",
        ):
            manager.open_project(locator)


if __name__ == "__main__":
    unittest.main()
