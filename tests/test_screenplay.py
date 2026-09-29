from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from cine_toaster import screenplay as sp
from cine_toaster.project import load_production

SCRIPT = textwrap.dedent(
    """\
    Title: Test

    INT. ROOM - DAY

    Ana waits by the window.

    Bo comes in.

    ANA
    (quietly)
    You're late.
    Again.

    BO (O.S.)
    I know.

    ANA ^
    Always.

    CUT TO:

    INT. ROOM - DAY #12#

    Later. The room is empty.

    BO
    I know.
    """
)


def codes(findings):
    return [finding.code for finding in findings]


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.play = sp.parse(SCRIPT)

    def test_title_and_scenes(self):
        self.assertEqual(self.play.title, "Test")
        # The parser separates a scene number from the heading text.
        self.assertEqual([scene.heading for scene in self.play.scenes], ["INT. ROOM - DAY", "INT. ROOM - DAY"])
        self.assertEqual(self.play.scenes[1].number, "12")

    def test_repeated_heading_is_found_by_occurrence(self):
        second = self.play.find_scene("int. room - day", 2)
        self.assertEqual(second.occurrence, 2)
        self.assertEqual(second.units[1].text, "Later. The room is empty.")
        self.assertIsNone(self.play.find_scene("INT. ROOM - DAY", 3))

    def test_action_paragraphs_are_separate_units(self):
        scene = self.play.scenes[0]
        actions = [unit.text for unit in scene.units if unit.kind == "action"]
        self.assertEqual(actions, ["Ana waits by the window.", "Bo comes in."])

    def test_a_speech_is_one_unit_with_its_parts(self):
        ana = self.play.scenes[0].speeches()[0]
        self.assertEqual(ana.speaker, "ANA")
        self.assertEqual(ana.text, "You're late. Again.")
        self.assertEqual(ana.parts[0], ("parenthetical", "quietly"))

    def test_extension_and_dual_dialogue(self):
        bo, ana_again = self.play.scenes[0].speeches()[1:3]
        self.assertEqual((bo.speaker, bo.extension), ("BO", "O.S."))
        self.assertTrue(ana_again.dual)


class AnchorTests(unittest.TestCase):
    def setUp(self):
        self.scene = sp.parse(SCRIPT).scenes[0]

    def test_anchor_ignores_case_spacing_and_curly_quotes(self):
        self.assertEqual(len(sp.resolve_anchor(self.scene, "ANA: you’re   LATE")), 1)

    def test_speaker_prefix_restricts_to_that_speaker(self):
        self.assertEqual(len(sp.resolve_anchor(self.scene, "BO: I know")), 1)
        self.assertEqual(sp.resolve_anchor(self.scene, "ANA: I know"), [])

    def test_range_covers_everything_between_in_order(self):
        coverage = sp.shot_coverage(self.scene, {"from": "Bo comes in", "to": "BO: I know"}, scene_id="S", shot_id="P1")
        self.assertEqual([unit.kind for unit in coverage.units], ["action", "speech", "speech"])
        self.assertEqual(coverage.problems, [])

    def test_a_list_of_ranges_may_skip_lines(self):
        coverage = sp.shot_coverage(self.scene, ["Ana waits", "BO: I know"], scene_id="S", shot_id="P1")
        self.assertEqual([unit.text for unit in coverage.units], ["Ana waits by the window.", "I know."])

    def test_missing_anchor_is_an_error(self):
        coverage = sp.shot_coverage(self.scene, "Nobody says this", scene_id="S", shot_id="P1")
        self.assertEqual(codes(coverage.problems), ["script_anchor_missing"])

    def test_ambiguous_anchor_names_the_candidates(self):
        scene = sp.parse("INT. A - DAY\n\nHe waits.\n\nHe waits again.\n").scenes[0]
        coverage = sp.shot_coverage(scene, "He waits", scene_id="S", shot_id="P1")
        self.assertEqual(codes(coverage.problems), ["script_anchor_ambiguous"])
        self.assertIn("He waits again.", coverage.problems[0].message)


class LineTests(unittest.TestCase):
    def setUp(self):
        self.speeches = sp.parse(SCRIPT).scenes[0].speeches()

    def test_matching_line_carries_its_metadata(self):
        dialogue, findings = sp.compare_lines(
            [{"who": "BO", "text": "I know.", "delivery": "flat"}], self.speeches[1:2], scene_id="S", shot_id="P1"
        )
        self.assertEqual(findings, [])
        self.assertEqual(dialogue[0]["delivery"], "flat")

    def test_drifted_line_is_reported_and_screenplay_wins(self):
        dialogue, findings = sp.compare_lines(
            [{"who": "ANA", "text": "You're late. Again and again."}], self.speeches[:1], scene_id="S", shot_id="P1"
        )
        self.assertEqual(codes(findings), ["line_drift"])
        self.assertEqual(dialogue[0]["text"], "You're late. Again.")

    def test_unscripted_line_is_advice(self):
        _, findings = sp.compare_lines(
            [{"who": "CY", "text": "Hello?"}], self.speeches, scene_id="S", shot_id="P1"
        )
        self.assertEqual(codes(findings), ["line_unscripted"])
        self.assertEqual(findings[0].severity, "advice")

    def test_uncovered_dialogue_is_a_warning(self):
        scene = sp.parse(SCRIPT).scenes[0]
        findings = sp.uncovered_dialogue(scene, {scene.speeches()[0].index}, scene_id="S")
        self.assertEqual(codes(findings), ["dialogue_uncovered", "dialogue_uncovered"])

    def test_link_suggestions_come_from_authored_lines(self):
        scene = sp.parse(SCRIPT).scenes[0]
        shots = [{"id": "P1", "lines": [{"who": "ANA", "text": "You're late. Again."}, {"who": "BO", "text": "I know."}]}]
        suggestion = sp.suggest_links(scene, shots)[0]
        self.assertTrue(suggestion["from"].startswith("ANA: You're late"))
        self.assertTrue(suggestion["to"].startswith("BO: I know"))
        self.assertTrue(suggestion["exact"])


class ProjectTests(unittest.TestCase):
    """Coverage through the real loader, on a production written to disk."""

    def production(self, scene_yaml: str) -> dict:
        directory = Path(tempfile.mkdtemp())
        (directory / "project.yaml").write_text(
            "id: t\ntitle: T\npaths:\n  scenes: scenes\n  script: script.fountain\n"
        )
        (directory / "script.fountain").write_text(SCRIPT)
        (directory / "scenes" / "010").mkdir(parents=True)
        (directory / "scenes" / "010" / "scene.yaml").write_text(textwrap.dedent(scene_yaml))
        return load_production(directory)["scenes"][0]

    def test_each_shot_knows_its_dialogue(self):
        scene = self.production(
            """\
            scene: SC-1
            script: {heading: INT. ROOM - DAY}
            shots:
              - n: 1
                covers: {from: Ana waits, to: "ANA: You're late"}
              - n: 2
                covers: {from: "BO: I know", to: "ANA: Always"}
            """
        )
        first, second = scene["shots"]
        self.assertEqual([d["who"] for d in first["script"]["dialogue"]], ["ANA"])
        self.assertEqual([d["who"] for d in second["script"]["dialogue"]], ["BO", "ANA"])
        self.assertEqual(codes_of(scene), [])
        self.assertEqual(scene["script"]["units"][1]["shots"], ["P1"])

    def test_unlinked_heading_is_an_error(self):
        scene = self.production("scene: SC-1\nscript: INT. NOWHERE - DAY\nshots:\n  - n: 1\n")
        self.assertEqual(codes_of(scene), ["script_scene_missing"])

    def test_scene_without_script_is_unchanged(self):
        scene = self.production("scene: SC-1\nshots:\n  - n: 1\n")
        self.assertIsNone(scene["script"])
        self.assertIsNone(scene["shots"][0]["script"])

    def test_uncovered_line_is_reported_on_the_scene(self):
        scene = self.production(
            "scene: SC-1\nscript: {heading: INT. ROOM - DAY}\nshots:\n  - n: 1\n    covers: \"ANA: You're late\"\n"
        )
        self.assertEqual(codes_of(scene), ["dialogue_uncovered", "dialogue_uncovered"])


def codes_of(scene):
    return [finding["code"] for finding in scene["findings"]]


if __name__ == "__main__":
    unittest.main()
