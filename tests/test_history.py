"""A scene keeps every decision ever made, beyond what state.json holds (ADR 0021)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.commands import Actor, clear_selection, select_take
from cine_toaster.state import MAX_DECISION_HISTORY, load_scene_state, read_history

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class HistoryTests(unittest.TestCase):
    def test_the_journal_keeps_what_the_state_lets_go(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "film"
            shutil.copytree(DEMO, root)
            scene_directory = root / "scenes" / "030-echo-chamber"
            for _ in range(MAX_DECISION_HISTORY // 2 + 5):
                select_take(root, scene_id="SC-030", shot_id="P3", take_id="ONE-BLINK", actor=Actor(id="editor"))
                clear_selection(root, scene_id="SC-030", shot_id="P3", actor=Actor(id="editor"))
            state = load_scene_state(scene_directory, "SC-030")
            history = read_history(scene_directory)
            self.assertEqual(len(state.decisions), MAX_DECISION_HISTORY)
            self.assertEqual(len(history), 2 * (MAX_DECISION_HISTORY // 2 + 5))
            self.assertEqual(len({entry["command_id"] for entry in history}), len(history))  # nothing twice
            self.assertEqual(history[-1]["command_id"], state.decisions[-1]["command_id"])


if __name__ == "__main__":
    unittest.main()
