from __future__ import annotations

import io
import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from cine_toaster.creation import creation_view, load_creation
from cine_toaster.creation_review import decide_inception_assessment, record_inception_assessment
from cine_toaster.errors import PermissionDeniedError, PersistenceError, RevisionConflictError, ValidationError
from cine_toaster.state import Actor

DEMO = Path(__file__).parents[1] / "examples/demo-project"


class CreationReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "film"
        shutil.copytree(DEMO, self.root)
        self.agent = Actor(id="creative-agent", kind="agent")
        self.human = Actor(id="director", kind="human")
        self.payload = {"title": "Enough to begin", "summary": "Narrative intent is clear; identity work can follow.",
            "readiness": [{"destination": "screenplay", "status": "ready", "summary": "The existing screenplay states the intent.", "gaps": []},
                {"destination": "masters", "status": "needs_work", "summary": "Identity still needs work.",
                 "gaps": [{"description": "No chosen identity.", "owner": "human", "next_action": "Review an agent-proposed identity set before masters."}]}],
            "proposal": {"destination": "screenplay", "question": "Develop this direction?", "scope": "Exploratory writing only.",
                         "why": "No master identity is needed to write.", "next_step": "Develop a screenplay candidate."}, "references": []}

    def assess(self, **changes):
        return record_inception_assessment(self.root, **{**self.payload, "expected_revision": load_creation(self.root)["revision"],
            "actor": self.agent, **changes})

    def decide(self, assessment, **changes):
        return decide_inception_assessment(self.root, assessment=assessment, **{
            "outcome": "approved", "guidance": "", "expected_revision": load_creation(self.root)["revision"],
            "actor": self.human, **changes})

    def test_assessment_and_human_decision_preserve_production_and_do_not_dispatch(self):
        protected = {path: path.read_bytes() for pattern in ("**/*.yaml", "**/*.fountain") for path in self.root.glob(pattern)}
        assessment = self.assess()["assessment"]
        current = creation_view(self.root)["inception_review"]["current"]
        self.assertEqual(current["status"], "awaiting_decision")
        result = self.decide(assessment["id"])
        self.assertEqual(result["decision"]["next_agent_action"]["status"], "not_dispatched")
        view = creation_view(self.root)["inception_review"]
        self.assertEqual(view["current"]["status"], "approved")
        self.assertEqual(view["history"], [assessment])
        self.assertTrue(all(path.read_bytes() == original for path, original in protected.items()))
        with self.assertRaises(ValidationError):
            self.decide(assessment["id"])

    def test_human_and_agent_authority_are_distinct(self):
        with self.assertRaises(PermissionDeniedError):
            self.assess(actor=self.human)
        assessment = self.assess()["assessment"]
        with self.assertRaises(PermissionDeniedError):
            self.decide(assessment["id"], actor=self.agent)
        with self.assertRaises(ValidationError):
            self.decide(assessment["id"], outcome="changes_requested")
        self.assertEqual(load_creation(self.root)["assessment_decisions"], [])

    def test_guided_revision_retains_earlier_assessment_and_decision(self):
        first = self.assess()["assessment"]
        decision = self.decide(first["id"], outcome="changes_requested", guidance="Clarify the transition first.")["decision"]
        self.assertEqual(creation_view(self.root)["inception_review"]["current"]["status"], "changes_requested")
        self.assertEqual(decision["next_agent_action"]["instruction"], "Clarify the transition first.")
        second = self.assess(summary="Transition clarified.")["assessment"]
        view = creation_view(self.root)["inception_review"]
        self.assertEqual(view["current"]["status"], "awaiting_decision")
        self.assertEqual(view["history"], [first, second])
        self.assertEqual(view["decisions"], [decision])
        with self.assertRaises(ValidationError):
            self.decide(first["id"])

    def test_material_drift_prevents_silent_approval(self):
        assessment = self.assess()["assessment"]
        script = next((self.root / "story").glob("*.fountain"))
        script.write_text(script.read_text() + "\nA changed intention.\n")
        self.assertEqual(creation_view(self.root)["inception_review"]["current"]["status"], "needs_reassessment")
        with self.assertRaises(ValidationError):
            self.decide(assessment["id"])
        self.assertEqual(load_creation(self.root)["assessment_decisions"], [])

    def test_failed_commit_preserves_previous_assessment(self):
        first = self.assess()["assessment"]
        path = self.root / "creation/state.json"
        original = path.read_bytes()
        with patch("cine_toaster.creation.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(PersistenceError):
                self.decide(first["id"])
        self.assertEqual(path.read_bytes(), original)

    def test_two_human_decisions_cannot_both_commit(self):
        assessment = self.assess()["assessment"]
        barrier = threading.Barrier(2)
        def decide(_):
            barrier.wait()
            try:
                return self.decide(assessment["id"], expected_revision=1)["revision"]
            except RevisionConflictError:
                return "conflict"
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(list(pool.map(decide, [0, 1])).count("conflict"), 1)
        self.assertEqual(len(load_creation(self.root)["assessment_decisions"]), 1)

    def test_invalid_judgments_and_corrupt_records_are_not_silently_ready(self):
        for readiness in ([], [{"destination": "screenplay", "status": "ready", "summary": "A", "gaps": ["unknown"]}]):
            with self.assertRaises(ValidationError):
                self.assess(readiness=readiness)
        self.assess()
        path = self.root / "creation/state.json"
        value = json.loads(path.read_text())
        value["assessments"][0]["materials"] = {}
        path.write_text(json.dumps(value))
        with self.assertRaises(PersistenceError):
            load_creation(self.root)

    def test_cli_assessment_and_decision_share_the_record(self):
        from cine_toaster.cli import main
        payload = self.base / "assessment.json"
        payload.write_text(json.dumps(self.payload))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["creation", "assess", str(self.root), "--assessment-file", str(payload), "--expected-revision", "0"]), 0)
        assessment = json.loads(output.getvalue())["assessment"]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["creation", "decide", str(self.root), assessment["id"], "--outcome", "approved", "--expected-revision", "1"]), 0)
        self.assertEqual(creation_view(self.root)["inception_review"]["current"]["status"], "approved")

    def test_http_presents_a_real_pending_request_and_records_human_guidance(self):
        from cine_toaster.web import ProjectBrowserHandler
        server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
        server.project_root = self.root
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        def post(path, payload):
            request = urllib.request.Request(origin + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)
        status, saved = post("/api/creation/assessment", {**self.payload, "expected_revision": 0})
        self.assertEqual(status, 200)
        assessment = saved["assessment"]["id"]
        decision = {"assessment": assessment, "outcome": "changes_requested", "guidance": "Show clearer intent.", "expected_revision": 1}
        self.assertEqual(post("/api/creation/direction", {**decision, "guidance": ""})[0], 422)
        self.assertEqual(post("/api/creation/direction", decision)[0], 200)
        self.assertEqual(post("/api/creation/direction", decision)[0], 409)
        with urllib.request.urlopen(origin + "/api/creation") as response:
            current = json.load(response)["inception_review"]["current"]
        self.assertEqual(current["decision"]["actor"]["kind"], "human")
        self.assertEqual(current["status"], "changes_requested")


if __name__ == "__main__":
    unittest.main()
