"""The continuity ledger: what holds from scene to scene (CT-0059)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from cine_toaster.continuity import describe, ledger, parse, render_text, state_at
from cine_toaster.project import load_production

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


def scene(scene_id: str, location: str = "ROOM", cast: dict | None = None, continuity: dict | None = None,
          shots: tuple[str, ...] = ("P1", "P2", "P3")) -> dict:
    return {"id": scene_id, "title": scene_id, "location": location, "cast": cast or {},
            "shots": [{"id": shot} for shot in shots], "continuity": parse(continuity, list(shots))}


def codes(report: dict) -> dict[str, list[str]]:
    return {key: [finding.code for finding in value] for key, value in report["findings"].items()}


class ParseTest(unittest.TestCase):
    def test_a_prop_with_one_state_and_a_person_with_several(self) -> None:
        record = parse({"continues": True, "time": "night",
                        "facts": {"KAEL": {"carries": "laptop"}, "window": "closed"}}, ["P1"])
        self.assertEqual(record["facts"], {"KAEL": {"carries": "laptop"}, "window": {"state": "closed"}})
        self.assertTrue(record["continues"])

    def test_what_cannot_be_read_is_a_problem(self) -> None:
        record = parse({"continues": "yes", "changes": [{"at": "P9", "KAEL": {"carries": "x"}}],
                        "exceptions": [{"subject": "KAEL"}]}, ["P1"])
        self.assertEqual(len(record["problems"]), 3)


class LedgerTest(unittest.TestCase):
    def test_a_declared_continuation_that_changes_a_fact_is_a_break(self) -> None:
        film = {"scenes": [scene("1", continuity={"facts": {"KAEL": {"jacket": "none"}}}),
                           scene("2", location="CORRIDOR", continuity={"continues": True,
                                                                        "facts": {"KAEL": {"jacket": "dark"}}})]}
        report = ledger(film)
        self.assertEqual(codes(report), {"2": ["continuity_break"]})
        self.assertIn("'none' to 'dark'", report["findings"]["2"][0].message)

    def test_a_change_declared_during_the_scene_is_not_a_break(self) -> None:
        film = {"scenes": [scene("1", continuity={"facts": {"KAEL": {"jacket": "none"}},
                                                  "changes": [{"at": "P2", "KAEL": {"jacket": "dark"}}]}),
                           scene("2", continuity={"continues": True, "facts": {"KAEL": {"jacket": "dark"}}})]}
        self.assertEqual(codes(ledger(film)), {})

    def test_an_accepted_break_is_kept_with_its_reason(self) -> None:
        film = {"scenes": [scene("1", cast={"KAEL": "kael"}),
                           scene("2", cast={"KAEL": "kael_dream"}, continuity={
                               "continues": True,
                               "exceptions": [{"subject": "Kael", "attribute": "variant", "reason": "the dream"}]})]}
        report = ledger(film)
        self.assertEqual(codes(report), {})
        self.assertEqual(report["scenes"][1]["events"][0]["kind"], "excepted")
        self.assertIn("the dream", render_text(report))

    def test_the_same_place_with_nothing_said_is_a_question_not_a_break(self) -> None:
        film = {"scenes": [scene("1", cast={"KAEL": "kael"}), scene("2", cast={"KAEL": "kael_tired"})]}
        report = ledger(film)
        self.assertEqual(codes(report), {"2": ["continuity_unconfirmed"]})
        self.assertEqual(report["findings"]["2"][0].severity, "advice")

    def test_after_a_gap_a_change_is_only_recorded(self) -> None:
        film = {"scenes": [scene("1", cast={"KAEL": "kael"}),
                           scene("2", cast={"KAEL": "kael_older"}, continuity={"continues": False})]}
        report = ledger(film)
        self.assertEqual(codes(report), {})
        self.assertEqual(report["scenes"][1]["events"][0]["kind"], "between_scenes")

    def test_the_time_of_day_compares_with_the_previous_scene_only(self) -> None:
        film = {"scenes": [scene("1", continuity={"time": "night"}), scene("2", location="ELSEWHERE"),
                           scene("3", continuity={"continues": True, "time": "dawn"})]}
        self.assertEqual(codes(ledger(film)), {})

    def test_facts_carry_forward_until_changed(self) -> None:
        film = {"scenes": [scene("1", continuity={"facts": {"KAEL": {"carries": "laptop"}},
                                                  "changes": [{"at": "P3", "KAEL": {"carries": "nothing"}}]}),
                           scene("2", location="CORRIDOR")]}
        self.assertEqual(state_at(film, "1", "P2")["KAEL"]["carries"]["value"], "laptop")
        self.assertEqual(state_at(film, "1", "P3")["KAEL"]["carries"]["value"], "nothing")
        later = state_at(film, "2", "P1")
        self.assertEqual(later["KAEL"]["carries"]["value"], "nothing")
        self.assertEqual(describe(later, "2"), ["KAEL: carries nothing (1, P3, declared)"])


class ProjectTest(unittest.TestCase):
    def test_a_production_reports_its_breaks_as_findings(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "film"
            shutil.copytree(DEMO, root)
            for name, block in (("010-last-broadcast", {"facts": {"radio": "on"}}),
                                ("030-echo-chamber", {"continues": True, "facts": {"radio": "off"}})):
                path = root / "scenes" / name / "scene.yaml"
                document = yaml.safe_load(path.read_text(encoding="utf-8"))
                document["continuity"] = block
                path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
            production = load_production(root)
            found = [item for scene in production["scenes"] for item in scene["findings"]
                     if item["code"].startswith("continuity_")]
            self.assertEqual([item["code"] for item in found], ["continuity_break"])


if __name__ == "__main__":
    unittest.main()
