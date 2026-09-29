"""Generation cost is estimated from the provider's own records, each job counted once."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cine_toaster.costs import production_costs
from cine_toaster.takes import discover


def take(job: dict | None = None, generation: dict | None = None) -> dict:
    provenance = {}
    if job:
        provenance["job"] = job
    if generation:
        provenance["generation"] = generation
    return {"id": "T", "provenance": provenance}


def production(*shots_takes: list[dict]) -> dict:
    return {"scenes": [{"id": "S", "shots": [{"id": f"P{i}", "takes": takes} for i, takes in enumerate(shots_takes)]}]}


class CostTests(unittest.TestCase):
    JOB = {"id": "a", "endpoint": "e1", "delayTime": 60_000, "executionTime": 300_000}

    def test_time_and_cost_from_the_record(self) -> None:
        report = production_costs(production([take(self.JOB)]), {"e1": 3.6})
        self.assertEqual((report["seconds"], report["usd"], report["rate"]), (360.0, 0.36, "declared"))

    def test_a_block_generation_is_counted_once_across_its_slices(self) -> None:
        shared = {**self.JOB, "shared_by": 2}
        report = production_costs(production([take(generation=shared)], [take(generation=shared)]), {"e1": 3.6})
        self.assertEqual(report["scenes"][0]["jobs"], 1)
        self.assertEqual(report["usd"], 0.36)

    def test_an_undeclared_rate_is_marked_assumed(self) -> None:
        self.assertEqual(production_costs(production([take(self.JOB)]))["rate"], "assumed")


class DiscoveryTests(unittest.TestCase):
    def test_a_job_record_beside_a_take_is_kept_as_it_is(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            (work / "c02.mp4").write_bytes(b"")
            (work / "c02.mp4.job.json").write_text(json.dumps({"id": "j1", "workerId": "w", "executionTime": 1000}))
            found = discover(work, 2, relative_to=work)
            self.assertEqual(found[0].public_dict()["provenance"]["job"]["id"], "j1")


if __name__ == "__main__":
    unittest.main()
