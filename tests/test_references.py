from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import yaml

from cine_toaster.cli import main
from cine_toaster.errors import ValidationError
from cine_toaster.new_production import create_production
from cine_toaster.references import add_reference, load_references


class ReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.root = create_production(self.base / "film", "A Film").root
        self.board = self.base / "board.png"
        self.board.write_bytes(b"not really a png")

    def test_a_reference_keeps_its_files_and_where_they_came_from(self) -> None:
        draft = add_reference(self.root, [self.board], title="The first board", kind="generated",
                              made_by="ChatGPT", made_on="2026-10-16", prompt="a girl crossing the wild")
        probe = self.base / "probe.png"
        probe.write_bytes(b"a probe")
        add_reference(self.root, [probe], title="A probe", kind="generated", made_on="2026-10-16",
                      parents=[draft.name], notes=["the era did not come through"])

        references = load_references(self.root)

        self.assertEqual([item["id"] for item in references],
                         ["2026-10-16-a-probe", "2026-10-16-the-first-board"])
        self.assertEqual(references[0]["from"], ["2026-10-16-the-first-board"])
        self.assertEqual(references[1]["prompt"], "a girl crossing the wild")
        self.assertTrue(all(item["findings"] == [] for item in references))
        self.assertEqual((draft / "board.png").read_bytes(), b"not really a png")

    def test_a_changed_missing_or_unlisted_file_is_reported(self) -> None:
        folder = add_reference(self.root, [self.board], title="Board", kind="made")
        (folder / "board.png").write_bytes(b"painted over")
        (folder / "extra.png").write_bytes(b"x")
        codes = {item["code"] for item in load_references(self.root)[0]["findings"]}
        self.assertEqual(codes, {"reference_changed", "reference_unlisted"})
        (folder / "board.png").unlink()
        codes = {item["code"] for item in load_references(self.root)[0]["findings"]}
        self.assertIn("reference_missing", codes)

    def test_found_without_licence_warns_and_unknown_parents_are_errors(self) -> None:
        folder = add_reference(self.root, [self.board], title="A still", kind="found", source="a book")
        record = yaml.safe_load((folder / "reference.yaml").read_text(encoding="utf-8"))
        record["from"] = ["nowhere"]
        (folder / "reference.yaml").write_text(yaml.safe_dump(record), encoding="utf-8")
        found = {item["code"]: item["severity"] for item in load_references(self.root)[0]["findings"]}
        self.assertEqual(found, {"reference_licence": "warning", "reference_from": "error"})

    def test_never_written_over_and_parents_must_exist(self) -> None:
        add_reference(self.root, [self.board], title="Board", kind="made", made_on="2026-10-16")
        with self.assertRaises(ValidationError):
            add_reference(self.root, [self.board], title="Board", kind="made", made_on="2026-10-16")
        with self.assertRaises(ValidationError):
            add_reference(self.root, [self.board], title="Other", kind="made", parents=["missing"])

    def test_the_cli_adds_and_lists(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            added = main(["references", "add", str(self.root), str(self.board), "--title", "Board",
                          "--kind", "generated", "--made-by", "ChatGPT", "--note", "drift in panel 4"])
            listed = main(["references", "list", str(self.root)])
        self.assertEqual((added, listed), (0, 0))
        self.assertIn("Board", output.getvalue())


if __name__ == "__main__":
    unittest.main()
