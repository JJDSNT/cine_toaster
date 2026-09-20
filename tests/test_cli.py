from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cine_toaster.cli import main
from cine_toaster.project import load_production


class DemoCommandTests(unittest.TestCase):
    def test_lists_available_templates(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(["demo", "--list"])

        self.assertEqual(result, 0)
        self.assertIn("the-last-signal\tThe Last Signal (default)", output.getvalue())
        self.assertIn("amiga-demo-reel\tAmiga Demo Reel", output.getvalue())

    def test_creates_selected_demo_projects_independently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            last_signal_path = root / "last-signal"
            amiga_reel_path = root / "amiga-reel"

            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["demo", str(last_signal_path)]), 0)
                self.assertEqual(
                    main(
                        [
                            "demo",
                            str(amiga_reel_path),
                            "--template",
                            "amiga-demo-reel",
                        ]
                    ),
                    0,
                )

            last_signal = load_production(last_signal_path)
            amiga_reel = load_production(amiga_reel_path)

            self.assertEqual(last_signal["id"], "the-last-signal")
            self.assertEqual(amiga_reel["id"], "amiga-demo-reel")
            self.assertNotEqual(last_signal_path, amiga_reel_path)

    def test_requires_destination_when_not_listing(self) -> None:
        errors = io.StringIO()

        with redirect_stderr(errors):
            result = main(["demo", "--template", "amiga-demo-reel"])

        self.assertEqual(result, 2)
        self.assertIn("Destination is required", errors.getvalue())

    def test_protects_source_checkout_without_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / "cine-toaster-source"
            checkout.mkdir()
            (checkout / ".git").mkdir()
            (checkout / "pyproject.toml").write_text("", encoding="utf-8")
            destination = checkout / "projects" / "film"
            errors = io.StringIO()

            with (
                patch("cine_toaster.cli.SOURCE_REPOSITORY_ROOT", checkout),
                redirect_stderr(errors),
            ):
                result = main(["demo", str(destination)])

            self.assertEqual(result, 2)
            self.assertFalse(destination.exists())
            self.assertIn("Refusing to create a runtime project", errors.getvalue())

            with (
                patch("cine_toaster.cli.SOURCE_REPOSITORY_ROOT", checkout),
                redirect_stdout(io.StringIO()),
            ):
                result = main(
                    [
                        "demo",
                        str(destination),
                        "--allow-inside-repository",
                    ]
                )

            self.assertEqual(result, 0)
            self.assertTrue((destination / "project.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
