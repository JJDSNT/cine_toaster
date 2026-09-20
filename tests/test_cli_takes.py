from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from cine_toaster.cli import main
from cine_toaster.project import load_scene


DEMO_PROJECT = Path(__file__).parents[1] / "examples" / "demo-project"
SCENE = "SC-030"
SHOT = "P1"


def run(*arguments: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(arguments))
    return code, out.getvalue(), err.getvalue()


class CliTakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "production"
        shutil.copytree(DEMO_PROJECT, self.root)
        self.project = str(self.root)

    def test_shots_lists_registered_alternatives(self) -> None:
        code, out, _ = run("shots", self.project, "--scene", SCENE)
        self.assertEqual(code, 0)
        self.assertIn("P1", out)
        self.assertIn("LONGER-HOLD", out)
        self.assertIn("Longer hold", out)

    def test_select_commits_and_reports_the_new_revision(self) -> None:
        code, out, _ = run(
            "take", "select", self.project, SCENE, SHOT, "HARD-CUT-IN",
            "--actor", "director", "--rationale", "Louder.",
        )
        self.assertEqual(code, 0)
        self.assertIn("revision 1", out)
        scene = load_scene(self.root, SCENE)
        shot = next(item for item in scene["shots"] if item["id"] == SHOT)
        self.assertEqual(shot["selected_take"], "HARD-CUT-IN")

    def test_select_json_output_is_machine_readable(self) -> None:
        code, out, _ = run(
            "take", "select", self.project, SCENE, SHOT, "CUT", "--actor", "a", "--json"
        )
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["take_id"], "CUT")
        self.assertEqual(payload["type"], "take.selected")

    def test_domain_failures_exit_with_code_three(self) -> None:
        code, _, err = run("take", "select", self.project, SCENE, SHOT, "T99", "--actor", "a")
        self.assertEqual(code, 3)
        self.assertIn("not_found", err)

    def test_clear_requires_an_existing_selection(self) -> None:
        code, _, err = run("take", "clear", self.project, SCENE, SHOT, "--actor", "a")
        self.assertEqual(code, 3)
        self.assertIn("validation_failed", err)

    def test_clear_after_select_succeeds(self) -> None:
        run("take", "select", self.project, SCENE, SHOT, "CUT", "--actor", "a")
        code, out, _ = run("take", "clear", self.project, SCENE, SHOT, "--actor", "a")
        self.assertEqual(code, 0)
        self.assertIn("was CUT", out)

    def test_check_passes_on_a_clean_scene(self) -> None:
        code, out, _ = run("check", self.project)
        self.assertEqual(code, 0)
        self.assertIn("No continuity problems", out)

    def test_check_fails_when_a_camera_crosses_the_line(self) -> None:
        scene_file = self.root / "cenas" / "030-echo-chamber" / "decupagem.yaml"
        scene_file.write_text(
            scene_file.read_text().replace(
                "      x: 2.9\n      y: 0.5",
                "      x: 2.9\n      y: 4.0",
            ),
            encoding="utf-8",
        )
        code, out, _ = run("check", self.project)
        self.assertEqual(code, 1)
        self.assertIn("axis_break", out)

    def test_events_are_listed_after_a_decision(self) -> None:
        run("take", "select", self.project, SCENE, SHOT, "HARD-CUT-IN", "--actor", "director")
        code, out, _ = run("events", self.project)
        self.assertEqual(code, 0)
        self.assertIn("take.selected", out)


if __name__ == "__main__":
    unittest.main()
