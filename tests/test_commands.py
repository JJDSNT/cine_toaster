from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.commands import clear_selection, dispatch, select_take
from cine_toaster.errors import (
    PermissionDeniedError,
    ResourceNotFoundError,
    RevisionConflictError,
    TakeNotEligibleError,
    ValidationError,
)
from cine_toaster.events import event_log_path, tail_events
from cine_toaster.project import load_scene
from cine_toaster.state import Actor, load_scene_state


DEMO_PROJECT = Path(__file__).parents[1] / "examples" / "demo-project"
DIRECTOR = Actor(id="director", kind="human")
SCENE = "SC-030"
SHOT = "P1"


class CommandTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / "production"
        shutil.copytree(DEMO_PROJECT, self.root)
        self.addCleanup(self.directory.cleanup)
        log = event_log_path(self.root)
        if log.exists():
            log.unlink()

    def scene(self) -> dict:
        scene = load_scene(self.root, SCENE)
        assert scene is not None
        return scene

    def shot(self, shot_id: str = SHOT) -> dict:
        return next(shot for shot in self.scene()["shots"] if shot["id"] == shot_id)


class SelectTakeTests(CommandTestCase):
    def test_selection_is_committed_and_readable_again(self) -> None:
        result = select_take(
            self.root,
            scene_id=SCENE,
            shot_id=SHOT,
            take_id="HARD-CUT-IN",
            actor=DIRECTOR,
            rationale="Louder reads better against the cut.",
        )

        self.assertEqual(result.revision, 1)
        self.assertIsNone(result.previous_take_id)
        shot = self.shot()
        self.assertEqual(shot["selected_take"], "HARD-CUT-IN")
        self.assertEqual(shot["status"], "selected")
        self.assertEqual(shot["selection"]["actor"]["id"], "director")
        self.assertTrue(next(take for take in shot["takes"] if take["id"] == "HARD-CUT-IN")["selected"])

    def test_superseding_keeps_the_previous_decision_on_record(self) -> None:
        select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="CUT", actor=DIRECTOR)
        result = select_take(
            self.root,
            scene_id=SCENE,
            shot_id=SHOT,
            take_id="LONGER-HOLD",
            actor=DIRECTOR,
            rationale="Needs the extra hold.",
        )

        self.assertEqual(result.previous_take_id, "CUT")
        self.assertEqual(result.revision, 2)
        state = load_scene_state(self.root / "cenas" / "030-echo-chamber", SCENE)
        kinds = [entry["take_id"] for entry in state.decisions]
        self.assertEqual(kinds, ["CUT", "LONGER-HOLD"])

    def test_repeating_a_selection_does_not_add_history(self) -> None:
        select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="CUT", actor=DIRECTOR)
        result = select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="CUT", actor=DIRECTOR)

        self.assertEqual(result.revision, 1)
        state = load_scene_state(self.root / "cenas" / "030-echo-chamber", SCENE)
        self.assertEqual(len(state.decisions), 1)

    def test_stale_revision_is_rejected_and_changes_nothing(self) -> None:
        select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="CUT", actor=DIRECTOR)
        before = (self.root / "cenas" / "030-echo-chamber" / "state.json").read_text()

        with self.assertRaises(RevisionConflictError):
            select_take(
                self.root,
                scene_id=SCENE,
                shot_id=SHOT,
                take_id="HARD-CUT-IN",
                actor=DIRECTOR,
                expected_revision=0,
            )

        after = (self.root / "cenas" / "030-echo-chamber" / "state.json").read_text()
        self.assertEqual(before, after)
        self.assertEqual(self.shot()["selected_take"], "CUT")

    def test_rejected_take_cannot_be_selected(self) -> None:
        """A take in the rejected folder keeps its record but not its eligibility."""

        with self.assertRaises(TakeNotEligibleError):
            select_take(
                self.root,
                scene_id=SCENE,
                shot_id="P2",
                take_id="LOOKS-AT-CAMERA",
                actor=DIRECTOR,
            )

    def test_unknown_scene_shot_and_take_are_reported(self) -> None:
        with self.assertRaises(ResourceNotFoundError):
            select_take(self.root, scene_id="SC-999", shot_id=SHOT, take_id="CUT", actor=DIRECTOR)
        with self.assertRaises(ResourceNotFoundError):
            select_take(self.root, scene_id=SCENE, shot_id="SH-999", take_id="CUT", actor=DIRECTOR)
        with self.assertRaises(ResourceNotFoundError):
            select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="T99", actor=DIRECTOR)

    def test_authored_scene_file_is_never_rewritten(self) -> None:
        authored = self.root / "cenas" / "030-echo-chamber" / "decupagem.yaml"
        before = authored.read_text()
        select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="HARD-CUT-IN", actor=DIRECTOR)
        self.assertEqual(authored.read_text(), before)
        # Comments and prose survive because nothing rewrites this file.
        self.assertIn("# A planta da cena", before)
        self.assertIn("direcao: |", before)

    def test_unrelated_scene_state_is_preserved(self) -> None:
        select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="CUT", actor=DIRECTOR)
        select_take(self.root, scene_id=SCENE, shot_id="P3", take_id="ONE-BLINK", actor=DIRECTOR)
        self.assertEqual(self.shot()["selected_take"], "CUT")
        self.assertEqual(self.shot("P3")["selected_take"], "ONE-BLINK")


class ReadOnlySourceTests(CommandTestCase):
    """SPEC-0002: a read-only source is browsable, but a command must refuse."""

    def test_command_refuses_before_writing(self) -> None:
        scene_directory = self.root / "cenas" / "030-echo-chamber"
        original = scene_directory.stat().st_mode
        scene_directory.chmod(0o555)
        self.addCleanup(scene_directory.chmod, original)

        with self.assertRaises(PermissionDeniedError) as caught:
            select_take(
                self.root, scene_id=SCENE, shot_id=SHOT, take_id="CUT", actor=DIRECTOR
            )

        self.assertEqual(caught.exception.code, "permission_denied")
        self.assertFalse((scene_directory / "state.json").exists())
        self.assertEqual(tail_events(self.root), [])


class EventTests(CommandTestCase):
    def test_commit_emits_one_event(self) -> None:
        select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="HARD-CUT-IN", actor=DIRECTOR)
        events = tail_events(self.root)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "take.selected")
        self.assertEqual(events[0]["payload"]["take_id"], "HARD-CUT-IN")

    def test_failed_command_emits_nothing(self) -> None:
        with self.assertRaises(ResourceNotFoundError):
            select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="T99", actor=DIRECTOR)
        self.assertEqual(tail_events(self.root), [])


class ClearSelectionTests(CommandTestCase):
    def test_clearing_returns_the_shot_to_undecided(self) -> None:
        select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="HARD-CUT-IN", actor=DIRECTOR)
        result = clear_selection(self.root, scene_id=SCENE, shot_id=SHOT, actor=DIRECTOR)

        self.assertEqual(result.previous_take_id, "HARD-CUT-IN")
        shot = self.shot()
        self.assertEqual(shot["selected_take"], "")
        self.assertEqual(shot["status"], "needs_review")

    def test_clearing_an_undecided_shot_is_a_validation_error(self) -> None:
        with self.assertRaises(ValidationError):
            clear_selection(self.root, scene_id=SCENE, shot_id=SHOT, actor=DIRECTOR)


class DispatchTests(CommandTestCase):
    def test_dispatch_matches_the_direct_call(self) -> None:
        result = dispatch(
            self.root,
            "select_take",
            {
                "scene_id": SCENE,
                "shot_id": SHOT,
                "take_id": "LONGER-HOLD",
                "actor": {"id": "agent-01", "kind": "agent"},
                "rationale": "Proposed by the agent.",
            },
        )
        self.assertEqual(result.take_id, "LONGER-HOLD")
        self.assertEqual(self.shot()["selection"]["actor"]["kind"], "agent")

    def test_unknown_command_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            dispatch(self.root, "delete_everything", {"scene_id": SCENE, "shot_id": SHOT})

    def test_missing_identifiers_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            dispatch(self.root, "select_take", {"scene_id": SCENE})

    def test_actor_kind_is_validated(self) -> None:
        with self.assertRaises(ValidationError):
            dispatch(
                self.root,
                "select_take",
                {
                    "scene_id": SCENE,
                    "shot_id": SHOT,
                    "take_id": "CUT",
                    "actor": {"id": "x", "kind": "robot"},
                },
            )


class StateFileTests(CommandTestCase):
    def test_state_file_is_valid_json_with_a_schema_version(self) -> None:
        select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="CUT", actor=DIRECTOR)
        document = json.loads(
            (self.root / "cenas" / "030-echo-chamber" / "state.json").read_text(encoding="utf-8")
        )
        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(document["revision"], 1)
        self.assertEqual(document["selections"][SHOT]["take_id"], "CUT")

    def test_state_written_by_an_older_build_still_loads(self) -> None:
        scene_directory = self.root / "cenas" / "030-echo-chamber"
        (scene_directory / "state.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "scene_id": SCENE,
                    "revision": 3,
                    "selections": {SHOT: {"take_id": "HARD-CUT-IN", "actor": {"id": "old"}}},
                    "decisions": [],
                }
            ),
            encoding="utf-8",
        )
        state = load_scene_state(scene_directory, SCENE)
        self.assertEqual(state.revision, 3)
        self.assertEqual(state.selections[SHOT].take_id, "HARD-CUT-IN")
        self.assertEqual(state.assemblies, [])

    def test_a_future_schema_version_is_refused(self) -> None:
        scene_directory = self.root / "cenas" / "030-echo-chamber"
        (scene_directory / "state.json").write_text(
            json.dumps({"schema_version": 99, "scene_id": SCENE}), encoding="utf-8"
        )
        with self.assertRaises(Exception) as caught:
            load_scene_state(scene_directory, SCENE)
        self.assertIn("schema version 99", str(caught.exception))

    def test_no_temporary_file_is_left_behind(self) -> None:
        select_take(self.root, scene_id=SCENE, shot_id=SHOT, take_id="CUT", actor=DIRECTOR)
        leftovers = list((self.root / "cenas" / "030-echo-chamber").glob(".state.json.tmp*"))
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
