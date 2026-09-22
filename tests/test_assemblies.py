from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.commands import (
    clear_selection,
    record_assembly,
    restore_assembly,
    review_assembly,
    select_take,
)
from cine_toaster.errors import ResourceNotFoundError, ValidationError
from cine_toaster.events import event_log_path, tail_events
from cine_toaster.project import load_scene
from cine_toaster.state import Actor, load_scene_state


DEMO_PROJECT = Path(__file__).parents[1] / "examples" / "demo-project"
SCENE = "SC-030"
SHOT_A = "P1"
SHOT_B = "P3"
TAKE_B1 = "CUT"
TAKE_B2 = "ONE-BLINK"


class AssemblyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "production"
        shutil.copytree(DEMO_PROJECT, self.root)
        log = event_log_path(self.root)
        if log.exists():
            log.unlink()
        self.actor = Actor(id="director")

    def scene(self) -> dict:
        scene = load_scene(self.root, SCENE)
        assert scene is not None
        return scene

    def state(self):
        return load_scene_state(self.root / "scenes" / "030-echo-chamber", SCENE)

    def cut(self, version: str, **takes: str):
        for shot_id, take_id in takes.items():
            select_take(
                self.root, scene_id=SCENE, shot_id=shot_id, take_id=take_id, actor=self.actor
            )
        return record_assembly(
            self.root,
            scene_id=SCENE,
            assembly_id=version,
            actor=self.actor,
            media=f"renders/{version}.mp4",
            summary=f"cut {version}",
            duration_seconds=74,
        )


class RecordTests(AssemblyTestCase):
    def test_a_version_snapshots_the_current_selections(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT", SHOT_B: TAKE_B2})
        assembly = self.state().assemblies[0]

        self.assertEqual(assembly.id, "v1")
        self.assertEqual(assembly.takes, {SHOT_A: "CUT", SHOT_B: TAKE_B2})
        self.assertEqual(assembly.verdict, "pending")
        self.assertEqual(assembly.media, "renders/v1.mp4")

    def test_a_duplicate_version_id_is_rejected(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT"})
        with self.assertRaises(ValidationError):
            record_assembly(self.root, scene_id=SCENE, assembly_id="v1", actor=self.actor)

    def test_recording_does_not_change_selections(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT"})
        self.assertEqual(self.state().selections[SHOT_A].take_id, "CUT")

    def test_recording_emits_an_event(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT"})
        self.assertEqual(tail_events(self.root)[-1]["type"], "assembly.recorded")


class ReviewTests(AssemblyTestCase):
    def test_a_verdict_and_its_reason_are_recorded(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT"})
        review_assembly(
            self.root,
            scene_id=SCENE,
            assembly_id="v1",
            verdict="rejected",
            actor=self.actor,
            note="the reply arrives too early",
        )
        assembly = self.state().assemblies[0]
        self.assertEqual(assembly.verdict, "rejected")
        self.assertEqual(assembly.note, "the reply arrives too early")
        self.assertEqual(assembly.reviewed_by.id, "director")

    def test_approving_supersedes_the_previous_approved_cut(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT"})
        review_assembly(
            self.root, scene_id=SCENE, assembly_id="v1", verdict="approved", actor=self.actor
        )
        self.cut("v2", **{SHOT_A: "HARD-CUT-IN"})
        review_assembly(
            self.root, scene_id=SCENE, assembly_id="v2", verdict="approved", actor=self.actor
        )

        verdicts = {item.id: item.verdict for item in self.state().assemblies}
        self.assertEqual(verdicts, {"v1": "superseded", "v2": "approved"})
        self.assertEqual(self.scene()["approved_assembly"]["id"], "v2")

    def test_an_unknown_verdict_is_rejected(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT"})
        with self.assertRaises(ValidationError):
            review_assembly(
                self.root, scene_id=SCENE, assembly_id="v1", verdict="lovely", actor=self.actor
            )

    def test_reviewing_an_unknown_version_is_reported(self) -> None:
        with self.assertRaises(ResourceNotFoundError):
            review_assembly(
                self.root, scene_id=SCENE, assembly_id="v9", verdict="approved", actor=self.actor
            )


class RestoreTests(AssemblyTestCase):
    def test_restoring_reapplies_the_takes_of_that_version(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT", SHOT_B: TAKE_B1})
        self.cut("v2", **{SHOT_A: "HARD-CUT-IN", SHOT_B: TAKE_B2})
        self.assertEqual(self.state().selections[SHOT_A].take_id, "HARD-CUT-IN")

        restore_assembly(
            self.root,
            scene_id=SCENE,
            assembly_id="v1",
            actor=self.actor,
            rationale="v1 held the tension better",
        )

        selections = self.state().selections
        self.assertEqual(selections[SHOT_A].take_id, "CUT")
        self.assertEqual(selections[SHOT_B].take_id, TAKE_B1)
        self.assertIn("tension", selections[SHOT_A].rationale)

    def test_restoring_leaves_the_versions_untouched(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT"})
        self.cut("v2", **{SHOT_A: "HARD-CUT-IN"})
        restore_assembly(self.root, scene_id=SCENE, assembly_id="v1", actor=self.actor)

        takes = {item.id: dict(item.takes) for item in self.state().assemblies}
        self.assertEqual(takes["v1"][SHOT_A], "CUT")
        self.assertEqual(takes["v2"][SHOT_A], "HARD-CUT-IN")

    def test_restoring_is_a_new_decision_not_an_undo(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT"})
        self.cut("v2", **{SHOT_A: "HARD-CUT-IN"})
        before = self.state().revision
        restore_assembly(self.root, scene_id=SCENE, assembly_id="v1", actor=self.actor)
        after = self.state()
        self.assertEqual(after.revision, before + 1)
        self.assertEqual(after.decisions[-1]["kind"], "assembly.restored")

    def test_a_version_without_a_snapshot_cannot_be_restored(self) -> None:
        """Imported history keeps its verdict but must not silently wipe selections."""

        record_assembly(self.root, scene_id=SCENE, assembly_id="historic", actor=self.actor)
        select_take(
            self.root, scene_id=SCENE, shot_id=SHOT_A, take_id="HARD-CUT-IN", actor=self.actor
        )
        with self.assertRaises(ValidationError) as caught:
            restore_assembly(
                self.root, scene_id=SCENE, assembly_id="historic", actor=self.actor
            )
        self.assertIn("no take snapshot", str(caught.exception))
        self.assertEqual(self.state().selections[SHOT_A].take_id, "HARD-CUT-IN")

    def test_restoring_a_version_whose_take_disappeared_is_refused(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT"})
        clear_selection(self.root, scene_id=SCENE, shot_id=SHOT_A, actor=self.actor)
        # A take is a file. Removing the file removes the take.
        (self.root / "scenes" / "030-echo-chamber" / "work" / "c01.mp4").unlink()
        with self.assertRaises(ValidationError) as caught:
            restore_assembly(self.root, scene_id=SCENE, assembly_id="v1", actor=self.actor)
        self.assertIn("no longer exist", str(caught.exception))


class DifferenceTests(AssemblyTestCase):
    def test_the_difference_between_two_cuts_is_shot_by_shot(self) -> None:
        self.cut("v1", **{SHOT_A: "CUT", SHOT_B: TAKE_B1})
        self.cut("v2", **{SHOT_B: TAKE_B2})
        first, second = self.state().assemblies
        changes = second.differences_from(first)
        self.assertEqual(changes, [{"shot_id": SHOT_B, "from": TAKE_B1, "to": TAKE_B2}])


if __name__ == "__main__":
    unittest.main()
