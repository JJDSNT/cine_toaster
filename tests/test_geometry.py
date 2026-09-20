from __future__ import annotations

import unittest

from cine_toaster.errors import ValidationError
from cine_toaster.geometry import check_geometry, parse_geometry, screen_side


def geometry_document(**overrides):
    document = {
        "units": "m",
        "room": {"width": 5.0, "depth": 4.0, "height": 2.8},
        "subjects": [
            {"id": "A", "label": "Ana", "position": [3.0, 2.0], "eye_height": 1.2},
            {"id": "B", "label": "Bo", "position": [1.0, 2.0], "eye_height": 1.6},
        ],
        "axis": {"between": ["A", "B"]},
        "cameras": [
            {"id": "C1", "label": "On Ana", "position": [2.5, 0.5], "height": 0.9, "target": "A"},
            {"id": "C2", "label": "On Bo", "position": [1.5, 0.5], "height": 1.6, "target": "B"},
        ],
    }
    document.update(overrides)
    return document


def shots(*camera_ids):
    return [{"id": f"SH-{index}", "camera": camera} for index, camera in enumerate(camera_ids, 1)]


class ParseTests(unittest.TestCase):
    def test_empty_geometry_is_allowed(self) -> None:
        geometry = parse_geometry(None)
        self.assertTrue(geometry.is_empty())
        self.assertEqual(check_geometry(geometry, shots("C1")), [])

    def test_heights_are_optional(self) -> None:
        geometry = parse_geometry(
            {
                "room": {"width": 4.0, "depth": 3.0},
                "subjects": [{"id": "A", "position": [2.0, 2.0]}],
                "cameras": [{"id": "C1", "position": [2.0, 0.5], "target": "A"}],
            }
        )
        self.assertIsNone(geometry.subjects["A"].eye_height)
        self.assertIsNone(geometry.cameras["C1"].height)

    def test_duplicate_camera_id_is_rejected(self) -> None:
        document = geometry_document(
            cameras=[
                {"id": "C1", "position": [1.0, 1.0], "target": "A"},
                {"id": "C1", "position": [2.0, 1.0], "target": "A"},
            ]
        )
        with self.assertRaises(ValidationError):
            parse_geometry(document)

    def test_position_must_be_a_pair(self) -> None:
        with self.assertRaises(ValidationError):
            parse_geometry({"subjects": [{"id": "A", "position": [1.0]}]})


class AxisTests(unittest.TestCase):
    def test_cameras_on_one_side_pass(self) -> None:
        geometry = parse_geometry(geometry_document())
        findings = check_geometry(geometry, shots("C1", "C2"))
        self.assertEqual(findings, [])

    def test_camera_across_the_line_is_reported(self) -> None:
        document = geometry_document()
        document["cameras"].append(
            {"id": "C3", "label": "Reverse", "position": [2.0, 3.5], "height": 0.9, "target": "A"}
        )
        geometry = parse_geometry(document)
        findings = check_geometry(geometry, shots("C1", "C2", "C3"), scene_id="SC-1")

        breaks = [finding for finding in findings if finding.code == "axis_break"]
        self.assertEqual(len(breaks), 1)
        self.assertEqual(breaks[0].severity, "error")
        self.assertEqual(breaks[0].cameras, ("C3",))
        self.assertIn("SH-3", breaks[0].shots)
        self.assertIn("1.50 m", breaks[0].message)

    def test_camera_on_the_line_is_not_a_break(self) -> None:
        document = geometry_document()
        document["cameras"].append(
            {"id": "C3", "label": "Along the line", "position": [4.0, 2.05], "target": "A"}
        )
        geometry = parse_geometry(document)
        findings = check_geometry(geometry, shots("C1", "C2", "C3"))
        self.assertEqual([finding.code for finding in findings], [])

    def test_axis_without_geometry_subject_is_reported(self) -> None:
        document = geometry_document(axis={"between": ["A", "MISSING"]})
        geometry = parse_geometry(document)
        findings = check_geometry(geometry, shots("C1"))
        self.assertEqual([finding.code for finding in findings], ["axis_subject_missing"])

    def test_unused_camera_does_not_break_the_axis(self) -> None:
        document = geometry_document()
        document["cameras"].append(
            {"id": "C9", "label": "Never used", "position": [2.0, 3.9], "target": "A"}
        )
        geometry = parse_geometry(document)
        self.assertEqual(check_geometry(geometry, shots("C1", "C2")), [])


class EyelineTests(unittest.TestCase):
    def test_one_subject_filmed_from_both_heights_is_reported(self) -> None:
        document = geometry_document()
        document["cameras"].append(
            {"id": "C3", "label": "From above", "position": [2.6, 0.6], "height": 2.2, "target": "A"}
        )
        geometry = parse_geometry(document)
        findings = check_geometry(geometry, shots("C1", "C2", "C3"))

        flips = [finding for finding in findings if finding.code == "eyeline_height_flip"]
        self.assertEqual(len(flips), 1)
        self.assertEqual(flips[0].severity, "warning")
        self.assertEqual(flips[0].subjects, ("A",))

    def test_missing_heights_produce_no_eyeline_finding(self) -> None:
        document = geometry_document()
        for camera in document["cameras"]:
            camera.pop("height", None)
        document["cameras"].append(
            {"id": "C3", "label": "Unknown height", "position": [2.6, 0.6], "target": "A"}
        )
        geometry = parse_geometry(document)
        findings = check_geometry(geometry, shots("C1", "C2", "C3"))
        self.assertEqual([finding.code for finding in findings], [])


class EyelineDirectionTests(unittest.TestCase):
    """The rule a prompt cannot enforce: two people must look at each other."""

    def shots_facing(self, camera_a: str, camera_b: str):
        return [
            {"id": "SH-1", "camera": camera_a, "subject": "A", "looks_at": "B"},
            {"id": "SH-2", "camera": camera_b, "subject": "B", "looks_at": "A"},
        ]

    def test_opposite_sides_pass(self) -> None:
        geometry = parse_geometry(geometry_document())
        findings = check_geometry(geometry, self.shots_facing("C1", "C2"))
        self.assertEqual([finding.code for finding in findings], [])

    def test_both_looking_the_same_way_is_reported(self) -> None:
        document = geometry_document()
        # Placed so that each camera puts the other character on the same side.
        document["cameras"] = [
            {"id": "C1", "label": "On Ana", "position": [3.6, 1.2], "target": "A"},
            {"id": "C2", "label": "On Bo", "position": [1.8, 2.6], "target": "B"},
        ]
        geometry = parse_geometry(document)
        findings = check_geometry(geometry, self.shots_facing("C1", "C2"), scene_id="SC-1")

        mismatches = [f for f in findings if f.code == "eyeline_mismatch"]
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0].severity, "error")
        self.assertEqual(sorted(mismatches[0].shots), ["SH-1", "SH-2"])

    def test_shots_without_declared_subjects_are_not_checked(self) -> None:
        document = geometry_document()
        document["cameras"] = [
            {"id": "C1", "label": "On Ana", "position": [3.6, 1.2], "target": "A"},
            {"id": "C2", "label": "On Bo", "position": [1.8, 2.6], "target": "B"},
        ]
        geometry = parse_geometry(document)
        findings = check_geometry(geometry, shots("C1", "C2"))
        self.assertEqual([f.code for f in findings if f.code == "eyeline_mismatch"], [])

    def test_unknown_subject_is_reported(self) -> None:
        geometry = parse_geometry(geometry_document())
        findings = check_geometry(
            geometry, [{"id": "SH-1", "camera": "C1", "subject": "A", "looks_at": "GHOST"}]
        )
        self.assertEqual([f.code for f in findings], ["eyeline_subject_missing"])

    def test_a_centred_interlocutor_is_not_forced_onto_a_side(self) -> None:
        side, angle = screen_side((0.0, 0.0), (0.0, 4.0), (0.0, 2.0))
        self.assertEqual(side, "centred")
        self.assertAlmostEqual(angle, 0.0, places=6)

    def test_screen_side_is_reported_from_the_camera_point_of_view(self) -> None:
        # Looking north up the plan; a point to the east is on the right of frame.
        side, _ = screen_side((0.0, 0.0), (0.0, 4.0), (2.0, 2.0))
        self.assertEqual(side, "right")
        side, _ = screen_side((0.0, 0.0), (0.0, 4.0), (-2.0, 2.0))
        self.assertEqual(side, "left")


class SanityTests(unittest.TestCase):
    def test_unknown_camera_reference_is_an_error(self) -> None:
        geometry = parse_geometry(geometry_document())
        findings = check_geometry(geometry, shots("C1", "NOPE"))
        codes = [finding.code for finding in findings]
        self.assertIn("unknown_camera", codes)

    def test_camera_outside_the_room_is_a_warning(self) -> None:
        document = geometry_document()
        document["cameras"].append(
            {"id": "C3", "label": "Outside", "position": [9.0, 0.5], "target": "A"}
        )
        geometry = parse_geometry(document)
        findings = check_geometry(geometry, shots("C1", "C2", "C3"))
        outside = [finding for finding in findings if finding.code == "camera_outside_room"]
        self.assertEqual(len(outside), 1)
        self.assertEqual(outside[0].severity, "warning")


if __name__ == "__main__":
    unittest.main()
