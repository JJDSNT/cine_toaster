"""The brief is derived from records, and says where each line came from."""

from __future__ import annotations

import unittest
from pathlib import Path

from cine_toaster.brief import production_brief, render_text, sceneflow_project, shot_size, take_review

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


def slots_of(brief, shot=None, tag=None):
    return [
        slot for slot in brief.slots()
        if (shot is None or slot.shot == shot) and (tag is None or slot.tag == tag)
    ]


class EchoChamberBriefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scene, cls.brief = production_brief(DEMO, "SC-030")

    def test_staging_names_its_sources(self) -> None:
        sources = {slot.tag: slot.source for slot in self.brief.staging}
        self.assertEqual(sources, {"INTENT": "authored", "LOGIC": "derived",
                                   "AESTHETIC": "missing", "OPENING": "derived"})

    def test_screen_direction_is_derived_from_the_geometry(self) -> None:
        logic = self.brief.staging[1].text
        self.assertIn("Line of action between Mara Vale and Speaker stack", logic)
        self.assertIn("Speaker stack is always screen left", logic)

    def test_camera_size_is_estimated_from_lens_and_distance(self) -> None:
        self.assertTrue(slots_of(self.brief, "P1", "CAM")[0].text.startswith("MS "))
        self.assertTrue(slots_of(self.brief, "P3", "CAM")[0].text.startswith("MCU "))

    def test_blocking_follows_the_walk(self) -> None:
        block = slots_of(self.brief, "P2", "BLOCK")[0].text
        self.assertIn("Mara Vale off right", block)
        self.assertIn("moves to Two steps short of the stack", block)
        self.assertIn("End: Speaker stack frame left, Mara Vale centre frame", block)

    def test_dialogue_comes_from_the_screenplay(self) -> None:
        lines = slots_of(self.brief, "P3", "DIAL")
        self.assertEqual([slot.speaker for slot in lines], ["SPEAKER STACK", "MARA"])
        self.assertTrue(all(slot.source == "screenplay" for slot in lines))

    def test_the_cut_into_a_shot_is_part_of_its_state(self) -> None:
        cut = slots_of(self.brief, "P3", "CUT IN")[0]
        self.assertEqual(cut.source, "authored")
        self.assertTrue(cut.text.startswith("J-cut: We hear the stack"))

    def test_an_authored_end_state_wins(self) -> None:
        self.assertEqual(slots_of(self.brief, "P2", "STATE OUT")[0].source, "authored")
        self.assertEqual(slots_of(self.brief, "P3", "STATE OUT")[0].source, "derived")

    def test_every_span_points_at_its_slot(self) -> None:
        text, spans = render_text(self.brief)
        for slot, start, end in spans:
            expected = slot.text if slot.source != "missing" else f"<missing> {slot.text}"
            self.assertEqual(text[start:end], expected)


class WithoutGeometryTests(unittest.TestCase):
    def test_what_cannot_be_derived_is_reported_missing(self) -> None:
        _, brief = production_brief(DEMO, "SC-010")
        self.assertEqual(slots_of(brief, "P1", "CAM")[0].source, "missing")
        self.assertEqual(brief.staging[1].source, "missing")
        # The screenplay still gives the shot its words.
        self.assertEqual(slots_of(brief, "P2", "DIAL")[0].speaker, "MARA")


class ShotSizeTests(unittest.TestCase):
    def test_sizes_by_frame_height(self) -> None:
        self.assertEqual(shot_size(0.2)[0], "ECU")
        self.assertEqual(shot_size(1.0)[0], "MS")
        self.assertEqual(shot_size(10.0)[0], "EWS")


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scene, cls.brief = production_brief(DEMO, "SC-030")

    def test_the_review_uses_a_local_video(self) -> None:
        review = take_review(self.scene, self.brief, "P3", "ONE-BLINK")
        self.assertEqual(review["youtubeId"], "")
        self.assertEqual(review["video"], "scenes/030-echo-chamber/work/c03-one-blink.mp4")
        self.assertTrue((DEMO / review["video"]).is_file())

    def test_a_take_review_holds_only_its_shot_from_zero(self) -> None:
        review = take_review(self.scene, self.brief, "P3")
        texts = [cue["selectedText"] for cue in review["cues"]]
        self.assertIn('MARA: "I never sent that."', texts)
        self.assertNotIn("Start: Speaker stack centre frame.", texts)
        self.assertEqual({cue["startTime"] for cue in review["cues"]}, {0.0})
        for cue in review["cues"]:
            self.assertEqual(review["scriptText"][cue["startIndex"]:cue["endIndex"]], cue["selectedText"])

    def test_the_whole_scene_runs_on_the_planned_clock(self) -> None:
        project = sceneflow_project(self.brief)
        dialogue = [cue for cue in project["cues"] if cue["type"] == "dialogue"]
        self.assertEqual(dialogue[0]["startTime"], 15.0)  # after P1 (6 s) and P2 (9 s)

    def test_an_unknown_take_has_no_review(self) -> None:
        self.assertIsNone(take_review(self.scene, self.brief, "P3", "NOPE"))


if __name__ == "__main__":
    unittest.main()
