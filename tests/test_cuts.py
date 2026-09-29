from __future__ import annotations

import unittest

from cine_toaster.cuts import scene_cuts
from cine_toaster.geometry import parse_geometry
from cine_toaster.movement import shot_motions


def geometry(**cameras):
    # Ana stands at (3, 3). Cameras are named by where they look from.
    document = {
        "room": {"width": 6.0, "depth": 6.0},
        "subjects": [{"id": "A", "label": "Ana", "position": [3.0, 3.0]}],
        "cameras": [
            {"id": "FRONT", "position": [3.0, 0.5], "target": "A", "lens_mm": 35},
            {"id": "FRONT-NUDGE", "position": [3.3, 0.5], "target": "A", "lens_mm": 35},
            {"id": "SIDE", "position": [0.5, 3.0], "target": "A", "lens_mm": 35},
            {"id": "FRONT-TIGHT", "position": [3.0, 0.5], "target": "A", "lens_mm": 85},
        ],
    }
    return parse_geometry(document)


def run(shots, *, linked=False):
    geo = geometry()
    motions = shot_motions(geo, shots)
    return scene_cuts(shots, motions, geo, scene_id="S", screenplay_linked=linked)


def codes(findings):
    return [finding.code for finding in findings]


def speech(who):
    return {"units": [{"kind": "speech", "speaker": who, "text": "Hello.", "index": 1}], "dialogue": [], "action": []}


def action():
    return {"units": [{"kind": "action", "text": "She waits.", "index": 1}], "dialogue": [], "action": ["She waits."]}


class RecordTests(unittest.TestCase):
    def test_one_record_per_adjacent_pair(self):
        records, _ = run([{"id": "P1", "camera": "FRONT"}, {"id": "P2", "camera": "SIDE"}, {"id": "P3", "camera": "FRONT"}])
        self.assertEqual([(r["from"], r["to"], r["type"]) for r in records], [("P1", "P2", "hard"), ("P2", "P3", "hard")])

    def test_record_carries_exit_and_entry(self):
        shots = [
            {"id": "P1", "camera": "FRONT", "ends_on": "Ana looks down.", "script": speech("ANA")},
            {"id": "P2", "camera": "SIDE", "cut": {"type": "match", "reason": "Her gaze."}, "script": action()},
        ]
        record = run(shots)[0][0]
        self.assertEqual(record["type"], "match")
        self.assertEqual(record["exit"]["ends_on"], "Ana looks down.")
        self.assertEqual(record["exit"]["unit"]["speaker"], "ANA")
        self.assertEqual(record["entry"]["framed"][0]["subject"], "A")


class CheckTests(unittest.TestCase):
    def test_unknown_type_is_an_error(self):
        _, findings = run([{"id": "P1"}, {"id": "P2", "cut": {"type": "wipe-ish"}}])
        self.assertEqual(codes(findings), ["cut_type_unknown"])

    def test_nearly_same_setup_is_a_jump(self):
        _, findings = run([{"id": "P1", "camera": "FRONT"}, {"id": "P2", "camera": "FRONT-NUDGE"}])
        self.assertEqual(codes(findings), ["jump_cut_undeclared"])

    def test_declared_jump_passes(self):
        _, findings = run([{"id": "P1", "camera": "FRONT"}, {"id": "P2", "camera": "FRONT-NUDGE", "cut": {"type": "jump"}}])
        self.assertEqual(findings, [])

    def test_ninety_degrees_is_not_a_jump(self):
        _, findings = run([{"id": "P1", "camera": "FRONT"}, {"id": "P2", "camera": "SIDE"}])
        self.assertEqual(findings, [])

    def test_a_change_of_size_is_not_a_jump(self):
        _, findings = run([{"id": "P1", "camera": "FRONT"}, {"id": "P2", "camera": "FRONT-TIGHT"}])
        self.assertEqual(findings, [])

    def test_chaining_into_another_setup_is_reported(self):
        _, findings = run([{"id": "P1", "camera": "FRONT"}, {"id": "P2", "camera": "SIDE", "cut": {"chain": "frame"}}])
        self.assertEqual(codes(findings), ["chain_pose_mismatch"])

    def test_chaining_the_same_setup_passes(self):
        shots = [{"id": "P1", "camera": "FRONT"}, {"id": "P2", "camera": "FRONT", "cut": {"type": "jump", "chain": "frame"}}]
        self.assertEqual(run(shots)[1], [])

    def test_l_cut_needs_the_outgoing_shot_to_end_on_dialogue(self):
        silent = [{"id": "P1", "script": action()}, {"id": "P2", "cut": {"type": "l"}, "script": action()}]
        spoken = [{"id": "P1", "script": speech("ANA")}, {"id": "P2", "cut": {"type": "l"}, "script": action()}]
        self.assertEqual(codes(run(silent, linked=True)[1]), ["split_edit_without_sound"])
        self.assertEqual(run(spoken, linked=True)[1], [])

    def test_j_cut_needs_the_incoming_shot_to_start_on_dialogue(self):
        silent = [{"id": "P1", "script": speech("ANA")}, {"id": "P2", "cut": {"type": "j"}, "script": action()}]
        spoken = [{"id": "P1", "script": action()}, {"id": "P2", "cut": {"type": "j"}, "script": speech("BO")}]
        self.assertEqual(codes(run(silent, linked=True)[1]), ["split_edit_without_sound"])
        self.assertEqual(run(spoken, linked=True)[1], [])

    def test_split_edit_is_not_judged_without_a_linked_screenplay(self):
        shots = [{"id": "P1"}, {"id": "P2", "cut": {"type": "l"}}]
        self.assertEqual(run(shots, linked=False)[1], [])

    def test_transition_without_reason_is_advice(self):
        shots = [{"id": "P1"}, {"id": "P2", "transition": {"id": "dissolve", "reason": ""}}]
        findings = run(shots)[1]
        self.assertEqual(codes(findings), ["transition_reason_missing"])
        self.assertEqual(findings[0].severity, "advice")

    def test_screen_flip_from_movement_is_listed_on_the_record(self):
        earlier = [{"code": "cut_screen_flip", "shots": ["P1", "P2"], "message": "flip"}]
        geo = geometry()
        shots = [{"id": "P1", "camera": "FRONT"}, {"id": "P2", "camera": "SIDE"}]
        records, _ = scene_cuts(shots, shot_motions(geo, shots), geo, scene_id="S", screenplay_linked=False, earlier=earlier)
        self.assertEqual([f["code"] for f in records[0]["findings"]], ["cut_screen_flip"])


if __name__ == "__main__":
    unittest.main()
