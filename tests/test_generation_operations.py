"""Generation Operations watches a consented job and continues the work that waited for it (ADR 0034)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_art_direction import FilmCase, Model, Runtime, observation
from test_inception_agent import HAS_AGENTS

if HAS_AGENTS:
    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from cine_toaster.agents.assistant import build
    from cine_toaster.agents.operations import Watcher, WaitStore, diagnosis, resumed_job

from cine_toaster.creation import load_creation


@unittest.skipUnless(HAS_AGENTS, "the agents extra is not installed")
class WaitStoreTests(unittest.TestCase):
    def test_a_wait_survives_a_new_store_and_continues_once(self):
        path = Path(tempfile.mkdtemp()) / "waits.json"
        WaitStore(path).add(thread="t1", project_id="p", job="job_1", role="art_direction")
        again = WaitStore(path)
        self.assertEqual([item["job"] for item in again.all("p")], ["job_1"])
        self.assertEqual(again.all("other"), [])
        self.assertEqual(again.take("job_1")["thread"], "t1")
        self.assertIsNone(again.take("job_1"))

    def test_a_lost_or_broken_file_forgets_waits_never_fails(self):
        path = Path(tempfile.mkdtemp()) / "waits.json"
        path.write_text("{not json")
        self.assertEqual(WaitStore(path).all(), [])

    def test_a_resume_names_the_message_that_opened_the_turn(self):
        message = AIMessage(content="ended", id="operations-job_1-abc")
        self.assertEqual(resumed_job({"messages": [message], "resume": {"job": "job_1", "message": message.id}}), "job_1")
        later = HumanMessage(content="hello", id="m2")
        self.assertEqual(resumed_job({"messages": [message, later], "resume": {"job": "job_1", "message": message.id}}), "")


class Jobs:
    """The runtime's job reads, scripted: a job that is running, then ends."""

    def __init__(self, job):
        self.job = job

    def __call__(self, job_id):
        return dict(self.job)


@unittest.skipUnless(HAS_AGENTS, "the agents extra is not installed")
class OperationsTests(FilmCase):
    def setUp(self):
        super().setUp()
        self.waits = WaitStore(Path(tempfile.mkdtemp()) / "waits.json")
        self.runtime = Runtime(self.root)
        self.config = {"configurable": {"thread_id": "art-thread"}}

    def running(self, brief):
        return {"id": "job_ref_1", "kind": "generate_reference", "state": "running",
                "params": {"art_brief": brief["id"]}}

    def test_a_job_that_outlives_the_turn_is_left_to_operations(self):
        brief = self.brief()
        model = Model({"action": "delegate_art_direction", "reply": ""},
                      {"action": "check_job", "reply": "", "job": "job_ref_1"})
        self.runtime.job = Jobs(self.running(brief))
        graph = build(model, self.runtime, MemorySaver(), waits=self.waits)
        with patch("cine_toaster.agents.art.WAIT_SECONDS", 0):
            state = graph.invoke({"messages": [HumanMessage(content="Check the job", id="h1")], "ag-ui": {}},
                                 self.config)
        self.assertEqual(state["agent_status"]["state"], "waiting_for_job")
        self.assertIn("Operações de geração", state["messages"][-1].content)
        wait = self.waits.all()[0]
        self.assertEqual((wait["job"], wait["thread"], wait["role"]), ("job_ref_1", "art-thread", "art_direction"))

    def test_a_finished_job_continues_the_art_work_without_a_person(self):
        brief = self.brief()
        model = Model({"action": "delegate_art_direction", "reply": ""},
                      {"action": "check_job", "reply": "", "job": "job_ref_1"},
                      # the continuation: inspect what was made, then stop honestly
                      {"action": "inspect", "reply": "", "brief": brief["id"], "references": [self.reference]},
                      {"action": "respond", "reply": "Inspecionado.", "status": "complete"})
        self.runtime.job = Jobs(self.running(brief))
        graph = build(model, self.runtime, MemorySaver(), waits=self.waits)
        with patch("cine_toaster.agents.art.WAIT_SECONDS", 0):
            graph.invoke({"messages": [HumanMessage(content="Check the job", id="h1")], "ag-ui": {}}, self.config)
        self.runtime.job = Jobs({**self.running(brief), "state": "succeeded", "adopted_at": "now",
                                 "result": {"summary": {"reference": self.reference}}})
        watcher = Watcher(graph, self.runtime, self.waits)
        self.assertEqual(watcher.tick(), ["job_ref_1"])
        self.assertEqual(watcher.tick(), [])  # a finished job continues once
        state = graph.get_state(self.config).values
        self.assertEqual(state["agent_status"]["state"], "complete")
        self.assertEqual(len(load_creation(self.root)["visual_reviews"]), 1)
        self.assertTrue(any("Generation Operations" in str(message.content) for message in state["messages"]))
        self.assertFalse(any(isinstance(message, HumanMessage) and "Generation Operations" in str(message.content)
                             for message in state["messages"]))  # it never speaks as the person

    def test_a_continuation_never_starts_new_generation(self):
        brief = self.brief()
        model = Model({"action": "delegate_art_direction", "reply": ""},
                      {"action": "check_job", "reply": "", "job": "job_ref_1"},
                      {"action": "generate", "reply": ""})
        self.runtime.job = Jobs(self.running(brief))
        graph = build(model, self.runtime, MemorySaver(), waits=self.waits)
        with patch("cine_toaster.agents.art.WAIT_SECONDS", 0):
            graph.invoke({"messages": [HumanMessage(content="Check the job", id="h1")], "ag-ui": {}}, self.config)
        self.runtime.job = Jobs({**self.running(brief), "state": "succeeded", "adopted_at": "now",
                                 "result": {"summary": {"reference": self.reference}}})
        Watcher(graph, self.runtime, self.waits).tick()
        state = graph.get_state(self.config)
        self.assertFalse(state.next)  # no consent interrupt is waiting for nobody
        self.assertEqual(state.values["agent_status"]["state"], "blocked")

    def test_a_failed_job_is_diagnosed_and_waits_for_the_person(self):
        brief = self.brief()
        model = Model({"action": "delegate_art_direction", "reply": ""},
                      {"action": "check_job", "reply": "", "job": "job_ref_1"})
        self.runtime.job = Jobs(self.running(brief))
        graph = build(model, self.runtime, MemorySaver(), waits=self.waits)
        with patch("cine_toaster.agents.art.WAIT_SECONDS", 0):
            graph.invoke({"messages": [HumanMessage(content="Check the job", id="h1")], "ag-ui": {}}, self.config)
        self.runtime.job = Jobs({**self.running(brief), "state": "failed", "error": "codex exited 1"})
        Watcher(graph, self.runtime, self.waits).tick()
        state = graph.get_state(self.config).values
        self.assertEqual(state["agent_status"], {"role": "generation_operations", "state": "needs_direction"})
        self.assertIn("codex exited 1", state["messages"][-1].content)
        self.assertIn("consentimento", state["messages"][-1].content)
        self.assertEqual(len(model.calls), 2)  # diagnosis asks no model

    def test_diagnosis_reads_the_endpoint_and_the_measured_failures(self):
        job = {"id": "job_b", "kind": "generate_block", "state": "failed",
               "error": "The worker swapped GPU and failed at 0 s"}
        with patch.dict("os.environ", {"RUNPOD_API_KEY": "k", "RUNPOD_LTX_ENDPOINT_ID": "e"}):
            text = diagnosis(job, transport=lambda path, body: {"workers": {"idle": 0}, "jobs": {"inQueue": 3}})
        self.assertIn("fila 3", text)
        self.assertIn("silent-gpu-swap", text)


if __name__ == "__main__":
    unittest.main()
