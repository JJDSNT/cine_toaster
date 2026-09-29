from __future__ import annotations

import unittest

from cine_toaster.errors import ValidationError
from cine_toaster.geometry import parse_geometry
from cine_toaster.movement import Pose, check_movement, derive_kind, shot_motions


def geometry_document(**overrides):
    # Ana on the right, Bo on the left, the line between them running along y = 2.
    # Every camera sits at y < 2, looking "up" the plan.
    document = {
        "room": {"width": 6.0, "depth": 5.0},
        "subjects": [
            {"id": "A", "label": "Ana", "position": [4.0, 2.0]},
            {"id": "B", "label": "Bo", "position": [2.0, 2.0]},
        ],
        "axis": {"between": ["A", "B"]},
        "marks": [
            {"id": "DOOR", "label": "By the door", "position": [5.0, 3.0]},
            {"id": "FAR", "label": "Far side", "position": [3.0, 4.0]},
        ],
        "cameras": [
            {"id": "C1", "position": [3.0, 0.0], "target": [3.0, 2.0], "lens_mm": 35},
            {"id": "C1-IN", "position": [3.0, 1.0], "target": [3.0, 2.0], "lens_mm": 35},
            {"id": "ON-A", "position": [4.0, 0.5], "target": "A", "lens_mm": 50},
        ],
    }
    document.update(overrides)
    return document


def geometry(**overrides):
    return parse_geometry(geometry_document(**overrides))


def codes(findings):
    return [finding.code for finding in findings]


class KindTests(unittest.TestCase):
    """One test per row of the SPEC-0005 kind table."""

    start = Pose(position=(0.0, 0.0), target=(0.0, 2.0), lens_mm=35, height=1.5)

    def kind(self, end, *, target_moves=False):
        return derive_kind(self.start, end, target_moves=target_moves)[:2]

    def test_static(self):
        self.assertEqual(self.kind(self.start), ("static", ""))

    def test_pan_right(self):
        self.assertEqual(self.kind(Pose((0.0, 0.0), (1.0, 2.0), 35, 1.5)), ("pan", "right"))

    def test_zoom_in(self):
        self.assertEqual(self.kind(Pose((0.0, 0.0), (0.0, 2.0), 85, 1.5)), ("zoom", "in"))

    def test_dolly_in_and_out(self):
        self.assertEqual(self.kind(Pose((0.0, 1.0), (0.0, 2.0), 35, 1.5)), ("dolly", "in"))
        self.assertEqual(self.kind(Pose((0.0, -1.0), (0.0, 2.0), 35, 1.5)), ("dolly", "out"))

    def test_truck_left(self):
        # Screen left of a camera looking up the plan is -x.
        self.assertEqual(self.kind(Pose((-1.0, 0.0), (-1.0, 2.0), 35, 1.5)), ("truck", "left"))

    def test_arc_keeps_distance_to_target(self):
        end = Pose((2.0, 2.0), (0.0, 2.0), 35, 1.5)  # a quarter turn about the target
        kind, direction, _, degrees = derive_kind(self.start, end, target_moves=False)
        self.assertEqual((kind, direction), ("arc", "right"))
        self.assertAlmostEqual(degrees, 90.0, places=3)

    def test_pedestal_needs_both_heights(self):
        self.assertEqual(self.kind(Pose((0.0, 0.0), (0.0, 2.0), 35, 2.2)), ("pedestal", "up"))
        unknown = Pose((0.0, 0.0), (0.0, 2.0), 35, None)
        self.assertEqual(derive_kind(unknown, Pose((0.0, 0.0), (0.0, 2.0), 35, 2.2), target_moves=False)[0], "static")

    def test_crane_is_height_with_plan_movement(self):
        self.assertEqual(self.kind(Pose((0.0, 1.0), (0.0, 2.0), 35, 3.0))[0], "crane")

    def test_track_follows_a_moving_subject(self):
        self.assertEqual(
            self.kind(Pose((1.0, 0.0), (1.0, 2.0), 35, 1.5), target_moves=True), ("track", "")
        )

    def test_combined_move_reports_dominant_and_secondary(self):
        kind, direction, secondary, _ = derive_kind(
            self.start, Pose((0.0, 1.0), (0.0, 2.0), 85, 1.5), target_moves=False
        )
        self.assertEqual((kind, direction), ("dolly", "in"))
        self.assertEqual(secondary, ("zoom in",))


class StateTests(unittest.TestCase):
    def test_positions_carry_across_the_cut(self):
        shots = [
            {"id": "P1", "camera": "C1", "subjects_move": [{"subject": "A", "to": "DOOR"}]},
            {"id": "P2", "camera": "C1"},
        ]
        motions = shot_motions(geometry(), shots)
        self.assertEqual(motions[0].start_positions["A"], (4.0, 2.0))
        self.assertEqual(motions[0].end_positions["A"], (5.0, 3.0))
        self.assertEqual(motions[1].start_positions["A"], (5.0, 3.0))

    def test_subjects_at_is_an_explicit_reset(self):
        shots = [
            {"id": "P1", "subjects_move": [{"subject": "A", "to": "DOOR"}]},
            {"id": "P2", "subjects_at": [{"subject": "A", "at": [4.0, 2.0]}]},
        ]
        self.assertEqual(shot_motions(geometry(), shots)[1].start_positions["A"], (4.0, 2.0))

    def test_camera_aimed_at_a_subject_follows_them(self):
        shots = [{"id": "P1", "camera": "ON-A", "subjects_move": [{"subject": "A", "to": "DOOR"}]}]
        motion = shot_motions(geometry(), shots)[0]
        self.assertEqual(motion.end_pose.target, (5.0, 3.0))
        self.assertEqual(motion.kind, "pan")

    def test_move_to_a_named_camera(self):
        shots = [{"id": "P1", "camera": "C1", "move": {"to": "C1-IN", "speed": "slow", "rig": "dolly"}}]
        motion = shot_motions(geometry(), shots)[0]
        self.assertEqual((motion.kind, motion.direction), ("dolly", "in"))
        self.assertEqual((motion.speed, motion.rig), ("slow", "dolly"))

    def test_inline_lens_change_is_a_zoom(self):
        shots = [{"id": "P1", "camera": "C1", "move": {"to": {"lens_mm": 85}, "speed": "snap"}}]
        self.assertEqual(shot_motions(geometry(), shots)[0].kind, "zoom")

    def test_tilt_is_taken_as_declared(self):
        shots = [{"id": "P1", "camera": "C1", "move": {"kind": "tilt_up"}}]
        motion = shot_motions(geometry(), shots)[0]
        self.assertEqual((motion.kind, motion.direction, motion.derived), ("tilt", "up", False))

    def test_duplicate_mark_id_is_rejected(self):
        with self.assertRaises(ValidationError):
            geometry(marks=[{"id": "A", "position": [1.0, 1.0]}])


class CheckTests(unittest.TestCase):
    def test_move_across_the_line_is_an_error(self):
        document = geometry_document()
        document["cameras"].append({"id": "BEYOND", "position": [3.0, 4.5], "target": [3.0, 2.0]})
        shots = [{"id": "P1", "camera": "C1", "move": {"to": "BEYOND"}}]
        self.assertIn("move_crosses_axis", codes(check_movement(parse_geometry(document), shots)))

    def test_move_on_one_side_passes(self):
        shots = [{"id": "P1", "camera": "C1", "move": {"to": "C1-IN"}}]
        self.assertEqual(codes(check_movement(geometry(), shots)), [])

    def test_subject_crossing_the_line_is_a_warning(self):
        document = geometry_document()
        document["subjects"].append({"id": "C", "label": "Cy", "position": [3.0, 1.0]})
        shots = [{"id": "P1", "subjects_move": [{"subject": "C", "to": "FAR"}]}]
        findings = check_movement(parse_geometry(document), shots)
        self.assertEqual(codes(findings), ["subject_path_crosses_axis"])
        self.assertEqual(findings[0].severity, "warning")

    def test_subject_staying_on_one_side_passes(self):
        document = geometry_document()
        document["subjects"].append({"id": "C", "label": "Cy", "position": [3.0, 1.0]})
        shots = [{"id": "P1", "subjects_move": [{"subject": "C", "to": [5.0, 1.0]}]}]
        self.assertEqual(codes(check_movement(parse_geometry(document), shots)), [])

    def test_declared_kind_that_disagrees_is_reported(self):
        shots = [{"id": "P1", "camera": "C1", "move": {"to": "C1-IN", "kind": "zoom_in"}}]
        self.assertEqual(codes(check_movement(geometry(), shots)), ["move_kind_mismatch"])

    def test_declared_kind_that_agrees_passes(self):
        shots = [{"id": "P1", "camera": "C1", "move": {"to": "C1-IN", "kind": "dolly_in"}}]
        self.assertEqual(codes(check_movement(geometry(), shots)), [])

    def test_subject_never_in_frame_is_reported(self):
        # C1 at 35 mm looks straight up the plan; the door is well off to its right.
        document = geometry_document()
        document["subjects"].append({"id": "D", "label": "Di", "position": [5.9, 0.3]})
        shots = [{"id": "P1", "camera": "C1", "subject": "D"}]
        self.assertEqual(
            codes(check_movement(parse_geometry(document), shots)), ["framed_subject_missing"]
        )

    def test_subject_who_walks_into_frame_passes(self):
        document = geometry_document()
        document["subjects"].append({"id": "D", "label": "Di", "position": [5.9, 0.3]})
        shots = [
            {
                "id": "P1",
                "camera": "C1",
                "subject": "D",
                "subjects_move": [{"subject": "D", "to": [3.0, 1.5]}],
            }
        ]
        self.assertEqual(codes(check_movement(parse_geometry(document), shots)), [])

    def test_side_flip_across_the_cut_is_reported(self):
        # Ana is right of centre for C1 (26.6 deg). A camera to her right, on the
        # same side of the line, sees her left of centre (33.7 deg): no axis break,
        # and still a jump across the cut.
        document = geometry_document()
        document["cameras"].append({"id": "ACROSS", "position": [5.0, 0.5], "target": [5.0, 2.0], "lens_mm": 24})
        shots = [{"id": "P1", "camera": "C1"}, {"id": "P2", "camera": "ACROSS"}]
        findings = check_movement(parse_geometry(document), shots)
        self.assertIn("cut_screen_flip", codes(findings))

    def test_same_side_across_the_cut_passes(self):
        shots = [{"id": "P1", "camera": "C1"}, {"id": "P2", "camera": "C1-IN"}]
        self.assertEqual(codes(check_movement(geometry(), shots)), [])

    def test_unknown_mark_and_subject_are_errors(self):
        shots = [
            {"id": "P1", "subjects_move": [{"subject": "A", "to": "NOWHERE"}]},
            {"id": "P2", "subjects_move": [{"subject": "GHOST", "to": "DOOR"}]},
        ]
        found = codes(check_movement(geometry(), shots))
        self.assertIn("unknown_mark", found)
        self.assertIn("movement_subject_missing", found)

    def test_value_outside_the_vocabulary_is_an_error(self):
        shots = [{"id": "P1", "camera": "C1", "move": {"to": "C1-IN", "speed": "slwo", "rig": "gimbal"}}]
        self.assertEqual(
            codes(check_movement(geometry(), shots)), ["move_value_unknown", "move_value_unknown"]
        )

    def test_scene_without_movement_is_unchanged(self):
        shots = [{"id": "P1", "camera": "C1"}]
        self.assertEqual(codes(check_movement(geometry(), shots)), [])


if __name__ == "__main__":
    unittest.main()
