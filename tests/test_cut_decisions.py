"""A cut decided in the runtime stands over the breakdown's, without rewriting it (plan step 13)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.commands import dispatch
from cine_toaster.errors import RevisionConflictError, ValidationError
from cine_toaster.project import load_scene

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HUMAN = {"id": "director", "kind": "human"}


class CutDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        self.addCleanup(self._restore)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        self.scene_file = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        self.authored = self.scene_file.read_bytes()

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def cut_into(self, shot_id: str) -> dict:
        return next(cut for cut in load_scene(self.root, "SC-030")["cuts"] if cut["to"] == shot_id)

    def test_a_decided_cut_is_the_cut_and_the_breakdown_is_untouched(self) -> None:
        self.assertEqual(self.cut_into("P2")["type"], "hard")
        result = dispatch(self.root, "set_cut", {
            "scene_id": "SC-030", "shot_id": "P2", "actor": HUMAN, "rationale": "the walk reads as one gesture",
            "cut": {"type": "match", "reason": "her step matches the channel's light",
                    "transition": {"id": "cross-dissolve", "duration_ms": 400, "reason": "a breath"}}})
        self.assertEqual(result.type, "cut.set")
        cut = self.cut_into("P2")
        self.assertEqual((cut["type"], cut["reason"], cut["transition"]["id"]),
                         ("match", "her step matches the channel's light", "cross-dissolve"))
        shot = next(item for item in load_scene(self.root, "SC-030")["shots"] if item["id"] == "P2")
        self.assertIsNone(shot["authored_cut"])  # the breakdown said nothing: a hard cut
        self.assertEqual(shot["cut_decision"]["decided_by"], HUMAN)
        self.assertEqual(self.scene_file.read_bytes(), self.authored)

    def test_clearing_returns_to_the_breakdown(self) -> None:
        before = self.cut_into("P3")["type"]
        dispatch(self.root, "set_cut", {"scene_id": "SC-030", "shot_id": "P3", "actor": HUMAN, "cut": {"type": "smash"}})
        self.assertEqual(self.cut_into("P3")["type"], "smash")
        dispatch(self.root, "clear_cut", {"scene_id": "SC-030", "shot_id": "P3", "actor": HUMAN})
        self.assertEqual(self.cut_into("P3")["type"], before)
        from cine_toaster.state import load_scene_state

        history = load_scene_state(self.scene_file.parent, "SC-030").decisions
        self.assertEqual([item["kind"] for item in history], ["cut.set", "cut.cleared"])
        self.assertEqual(history[1]["previous"]["type"], "smash")  # what was undone stays known
        with self.assertRaisesRegex(ValidationError, "not decided here"):
            dispatch(self.root, "clear_cut", {"scene_id": "SC-030", "shot_id": "P3", "actor": HUMAN})

    def test_what_cannot_be_a_cut_is_refused(self) -> None:
        with self.assertRaisesRegex(ValidationError, "opens the scene"):
            dispatch(self.root, "set_cut", {"scene_id": "SC-030", "shot_id": "P1", "actor": HUMAN, "cut": {"type": "match"}})
        with self.assertRaisesRegex(ValidationError, "Unknown cut type"):
            dispatch(self.root, "set_cut", {"scene_id": "SC-030", "shot_id": "P2", "actor": HUMAN, "cut": {"type": "wipe"}})
        with self.assertRaisesRegex(ValidationError, "No transition"):
            dispatch(self.root, "set_cut", {"scene_id": "SC-030", "shot_id": "P2", "actor": HUMAN,
                                            "cut": {"type": "hard", "transition": {"id": "star-wipe-deluxe"}}})
        with self.assertRaises(RevisionConflictError):
            dispatch(self.root, "set_cut", {"scene_id": "SC-030", "shot_id": "P2", "actor": HUMAN,
                                            "cut": {"type": "match"}, "expected_revision": 99})

    def test_the_checks_read_the_decided_cut(self) -> None:
        # A continuation without a chain is advised against, whoever declared it.
        dispatch(self.root, "set_cut", {"scene_id": "SC-030", "shot_id": "P2", "actor": HUMAN,
                                        "cut": {"type": "continuation"}})
        codes = [finding["code"] for finding in self.cut_into("P2")["findings"]]
        self.assertIn("continuation_unchained", codes)


if __name__ == "__main__":
    unittest.main()
