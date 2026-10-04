"""The Producer's report: where a production stands, read from its records (CT-0057)."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from cine_toaster.cli import main
from cine_toaster.producer import production_status, render_text, scene_status

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


def shot(shot_id: str, status: str, source: str = "generated", out_of_cut: bool = False) -> dict:
    return {"id": shot_id, "status": status, "source": source, "out_of_cut": out_of_cut}


def scene(**overrides) -> dict:
    base = {
        "id": "1", "title": "Opening",
        "shots": [shot("P1", "selected"), shot("P2", "ready"), shot("P3", "needs_review"),
                  shot("P4", "not_started"), shot("P5", "not_started", source="composed"),
                  shot("P6", "not_started", out_of_cut=True)],
        "assemblies": [{"id": "v1", "created_at": "2026-01-01", "verdict": "rejected"},
                       {"id": "v2", "created_at": "2026-01-02", "verdict": "pending"}],
        "approved_assembly": None, "findings": [], "gates": {}, "decisions": [], "blockers": [],
    }
    return {**base, **overrides}


class SceneStatusTest(unittest.TestCase):
    def test_counts_each_shot_in_the_cut_once(self) -> None:
        row = scene_status(scene())
        self.assertEqual(row["shots"], {"in_cut": 5, "chosen": 1, "one_take": 1, "awaiting_choice": 1,
                                        "awaiting_generation": 1, "composed": 1})
        self.assertEqual(row["awaiting_generation"], ["P4"])
        self.assertEqual(row["awaiting_choice"], ["P3"])

    def test_the_latest_version_waits_for_a_verdict(self) -> None:
        row = scene_status(scene())
        self.assertEqual(row["latest_version"], {"id": "v2", "verdict": "pending"})
        self.assertIn("judge version v2", row["next"])
        self.assertIn("choose the take of P3", row["next"])
        self.assertIn("generate P4", row["next"])

    def test_a_judged_version_is_not_asked_again(self) -> None:
        row = scene_status(scene(assemblies=[{"id": "v3", "created_at": "x", "verdict": "approved"}],
                                 approved_assembly={"id": "v3"}))
        self.assertEqual(row["approved_version"], "v3")
        self.assertFalse(any(item.startswith("judge") for item in row["next"]))

    def test_proposals_stay_open_until_the_author_settles_them(self) -> None:
        row = scene_status(scene(decisions=[{"question": "Which voice?", "status": "proposed", "answer": "A calm one"},
                                            {"question": "Night?", "status": "decided", "answer": "Yes"}]))
        self.assertEqual(row["open_questions"], ["Which voice?"])
        self.assertIn("answer 1 open question(s)", row["next"])

    def test_errors_and_waiting_gates_block(self) -> None:
        row = scene_status(scene(findings=[{"code": "line_crossed", "severity": "error"},
                                           {"code": "soft", "severity": "warning"}],
                                 gates={"picture": {"state": "waiting"}, "done": {"state": "passed"}}))
        self.assertEqual(row["blockers"], ["1 error finding(s): line_crossed", "gate picture waits for a person"])


class ProductionStatusTest(unittest.TestCase):
    def production(self) -> dict:
        return {"id": "film", "title": "Film", "scenes": [scene(), scene(id="2", approved_assembly={"id": "v2"})],
                "sequences": [{"id": "a", "label": "A", "scene_ids": ["1", "2"]},
                              {"id": "b", "label": "B", "scene_ids": []}]}

    def test_totals_add_the_scenes_of_a_sequence(self) -> None:
        status = production_status(self.production())
        first = status["sequences"][0]
        self.assertEqual(first["totals"]["in_cut"], 10)
        self.assertEqual(first["totals"]["approved_scenes"], 1)
        self.assertIn("A: 10 shots in the cut", render_text(status))

    def test_one_sequence_only(self) -> None:
        status = production_status(self.production(), "b")
        self.assertEqual([item["id"] for item in status["sequences"]], ["b"])

    def test_the_cli_reports_the_demo(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["status", str(DEMO), "--json"]), 0)
        status = json.loads(out.getvalue())
        self.assertTrue(status["sequences"])
        self.assertTrue(all("totals" in item for item in status["sequences"]))


if __name__ == "__main__":
    unittest.main()
