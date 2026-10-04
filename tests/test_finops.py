"""What the provider billed, set against the jobs Cine Toaster ran (CT-0061)."""

from __future__ import annotations

import unittest

import json
import os
import tempfile
from pathlib import Path

from cine_toaster.finops import film_jobs, merge, reconcile, render_text
from cine_toaster.providers.runpod_billing import serverless_observations

PAYLOAD = {
    "records": [
        {"startTime": "2026-09-17T10:00:00Z", "endTime": "2026-09-17T11:00:00Z", "serverlessId": "ltx",
         "totalAmount": 0.30, "gpuAmount": 0.29, "cpuAmount": 0, "diskAmount": 0.01, "feeAmount": 0},
        {"startTime": "2026-09-17T12:00:00Z", "endTime": "2026-09-17T13:00:00Z", "serverlessId": "ltx",
         "totalAmount": 2.00, "gpuAmount": 2.00, "cpuAmount": 0, "diskAmount": 0, "feeAmount": 0},
        {"startTime": "2026-09-17T10:00:00Z", "endTime": "2026-09-17T11:00:00Z", "serverlessId": "other",
         "totalAmount": 0.0, "gpuAmount": 0, "cpuAmount": 0, "diskAmount": 0, "feeAmount": 0},
    ],
    "metadata": {"query": {"startTime": "2026-09-17T00:00:00Z", "endTime": "2026-09-18T00:00:00Z",
                           "bucketSize": "hour"}},
}

ENTRIES = [
    {"at": "2026-09-17T10:20:00+00:00", "usd": 0.05, "what": "Block A of 3-01", "remote": "r1",
     "endpoint": "ltx", "seconds": 100},
    {"at": "2026-09-17T10:40:00+00:00", "usd": 0.10, "what": "Block B of 3-01", "remote": "r2",
     "endpoint": "ltx", "seconds": 200},
    {"at": "2026-09-17T09:00:00+00:00", "usd": 0.04, "what": "Picture P3", "remote": "r3"},  # before CT-0061
    {"at": "2026-09-16T09:00:00+00:00", "usd": 0.04, "what": "out of the window", "remote": "r4",
     "endpoint": "ltx", "seconds": 10},
]


def fetch(path: str, query: dict) -> dict:
    assert path == "/billing/serverless" and query["bucketSize"] == "hour"
    return PAYLOAD


class ReconcileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.billing = serverless_observations("2026-09-17T00:00:00Z", "2026-09-18T00:00:00Z", fetch=fetch)
        self.report = reconcile(self.billing, ENTRIES, "2026-10-04T12:00:00+00:00")

    def test_observations_are_provider_neutral(self) -> None:
        first = self.billing["observations"][0]
        self.assertEqual((first["provider"], first["resource"], first["usd"]), ("runpod", "ltx", 0.30))
        self.assertEqual(first["components"]["disk"], 0.01)

    def test_a_billed_hour_is_shared_by_the_seconds_of_its_jobs(self) -> None:
        jobs = {row["remote"]: row for row in self.report["jobs"]}
        self.assertEqual((jobs["r1"]["allocated_usd"], jobs["r2"]["allocated_usd"]), (0.1, 0.2))
        self.assertEqual(jobs["r2"]["overhead_usd"], 0.1)
        self.assertEqual(self.report["attributed_usd"], 0.3)

    def test_an_hour_without_a_job_is_unattributed_never_spread(self) -> None:
        self.assertEqual(self.report["unattributed_usd"], 2.0)
        self.assertEqual(self.report["unattributed"][0]["start"], "2026-09-17T12:00:00Z")
        self.assertEqual(self.report["reconciled_share"], round(0.3 / 2.3, 4))

    def test_a_job_with_no_endpoint_stays_measured_and_says_why(self) -> None:
        r3 = next(row for row in self.report["jobs"] if row["remote"] == "r3")
        self.assertEqual((r3["source"], r3["reason"]), ("unobserved", "no endpoint recorded"))
        self.assertEqual(self.report["unobserved_jobs"], 1)
        self.assertNotIn("r4", {row["remote"] for row in self.report["jobs"]})
        self.assertIn("unattributed US$ 2.00", render_text(self.report))


class FilmJobsTest(unittest.TestCase):
    def test_the_films_records_complete_the_ledger_and_count_once(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "scenes" / "a").mkdir(parents=True)
            (root / "archive").mkdir()
            record = {"id": "r3", "endpoint": "qwen", "delayTime": 1000, "executionTime": 9000}
            (root / "scenes" / "a" / "p3.png.job.json").write_text(json.dumps(record))
            (root / "archive" / "p3.png.job.json").write_text(json.dumps(record))  # a copy of the same job
            (root / "scenes" / "a" / "c1.mp4.job.json").write_text(json.dumps(
                {"id": "r9", "endpoint": "ltx", "delayTime": 0, "executionTime": 60000,
                 "finished_at": "2026-09-17T10:30:00+00:00"}))
            os.utime(root / "scenes" / "a" / "p3.png.job.json", (1758103200, 1758103200))
            jobs = film_jobs(root, {"ltx": 3.6, "qwen": 3.6})
            self.assertEqual(sorted(job["remote"] for job in jobs), ["r3", "r9"])
            r9 = next(job for job in jobs if job["remote"] == "r9")
            self.assertEqual((r9["at_source"], r9["seconds"], r9["usd"]), ("recorded", 60.0, 0.06))
            self.assertEqual(next(job for job in jobs if job["remote"] == "r3")["at_source"], "file_time")
            merged = merge([dict(entry) for entry in ENTRIES], jobs)
            r3 = next(entry for entry in merged if entry["remote"] == "r3")
            self.assertEqual((r3["endpoint"], r3["what"]), ("qwen", "Picture P3"))  # the ledger's, completed
            self.assertEqual(len(merged), len(ENTRIES) + 1)


if __name__ == "__main__":
    unittest.main()
