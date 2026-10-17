from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import argparse
import re

from cine_toaster.cli import build_parser, main
from cine_toaster.errors import ValidationError
from cine_toaster.new_production import create_production, guide_text
from cine_toaster.project import load_production

SCREENPLAY = """Title: Two Rooms

INT. KITCHEN - DAY

ANA pours coffee.

ANA
Again: the same morning.

EXT. STREET - NIGHT

Rain.

INT. KITCHEN - DAY

The cup is cold.
"""


class NewProductionTests(unittest.TestCase):
    def test_an_empty_production_loads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            created = create_production(Path(directory) / "film", "Um Filme: Primeiro")

            production = load_production(created.root)

            self.assertEqual(production["id"], "um-filme-primeiro")
            self.assertEqual(production["title"], "Um Filme: Primeiro")
            self.assertEqual(production["scenes"], [])

    def test_each_screenplay_scene_becomes_a_linked_breakdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "two-rooms.fountain"
            source.write_text(SCREENPLAY, encoding="utf-8")

            created = create_production(Path(directory) / "film", "Two Rooms", screenplay=source)
            production = load_production(created.root)

            self.assertEqual(created.scenes, ["SC-010", "SC-020", "SC-030"])
            self.assertEqual((created.root / "story/screenplay.fountain").read_text(encoding="utf-8"), SCREENPLAY)
            scenes = {scene["id"]: scene for scene in production["scenes"]}
            self.assertEqual(scenes["SC-030"]["script"]["occurrence"], 2)
            self.assertTrue(all(scene["script"]["linked"] for scene in scenes.values()))
            self.assertTrue(all(scene["shots"] == [] for scene in scenes.values()))
            # Nothing films the line yet: phase 1 starts with the screenplay ahead of the storyboard.
            codes = [finding["code"] for finding in scenes["SC-010"]["findings"]]
            self.assertIn("dialogue_uncovered", codes)

    def test_never_writes_over_a_directory_with_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kept.txt").write_text("mine", encoding="utf-8")

            with self.assertRaises(ValidationError):
                create_production(root, "Over It")

            self.assertEqual([path.name for path in root.iterdir()], ["kept.txt"])

    def test_cli_refuses_the_source_checkout(self) -> None:
        errors = io.StringIO()
        inside = Path(__file__).resolve().parent.parent / "a-film-here"

        with redirect_stderr(errors), redirect_stdout(io.StringIO()):
            result = main(["new", str(inside), "--title", "Inside"])

        self.assertEqual(result, 2)
        self.assertFalse(inside.exists())

    def test_cli_creates_from_a_screenplay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "two-rooms.fountain"
            source.write_text(SCREENPLAY, encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                result = main(["new", str(Path(directory) / "film"), "--title", "Two Rooms",
                               "--screenplay", str(source)])

            self.assertEqual(result, 0)
            self.assertIn("3 scene(s) from the screenplay", output.getvalue())


class GuideTests(unittest.TestCase):
    def test_onboarding_explains_lan_launch_phone_url_and_network_boundaries(self) -> None:
        from cine_toaster.mcp_server import INSTRUCTIONS
        guide = guide_text()
        for text in (guide, INSTRUCTIONS):
            self.assertIn("--host 0.0.0.0", text)
            self.assertIn("<LAN_IP>:8787/app/creation.html", text)
            self.assertIn("WSL", text)
            self.assertIn("firewall", text)
            self.assertIn("internet", text)

    def test_every_command_the_guide_names_exists(self) -> None:
        def actions(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
            found = next((action for action in parser._actions if isinstance(action, argparse._SubParsersAction)), None)
            return dict(found.choices) if found else {}

        commands = actions(build_parser())
        named = re.findall(r"toast ([a-z][a-z-]*)(?: ([a-z][a-z-]*))?", guide_text())
        self.assertTrue(named)
        for command, sub in named:
            self.assertIn(command, commands, f"the guide names `toast {command}`")
            children = actions(commands[command])
            if children and sub:
                self.assertIn(sub, children, f"the guide names `toast {command} {sub}`")


if __name__ == "__main__":
    unittest.main()
