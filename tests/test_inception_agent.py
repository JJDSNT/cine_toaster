"""The Coordinator delegates real bounded work through the existing CoAgent graph."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from cine_toaster.creation import creation_view, load_creation, save_creation_draft
from cine_toaster.creation_review import decide_inception_assessment, record_inception_assessment
from cine_toaster.project import load_production
from cine_toaster.state import Actor

try:
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from cine_toaster.agents.assistant import build
    from cine_toaster.agents.models import ModelUnavailable
    HAS_AGENTS = True
except ImportError:
    HAS_AGENTS = False

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
AGENT = Actor(id="inception", kind="agent")


def respond(reply="Qual intenção você quer explorar?", status="needs_direction"):
    return {"action": "respond", "reply": reply, "status": status}


def concept(text="A child follows a trail of light.", **extra):
    return {"action": "save_concept", "reply": "", "draft": {"title": "Light trail", "text": text, **extra}}


def assessment():
    return {"action": "assess_readiness", "reply": "", "assessment": {
        "title": "Opening direction", "summary": "The opening can be developed.", "references": [],
        "readiness": [{"destination": "screenplay", "status": "ready", "summary": "A concept exists.", "gaps": []}],
        "proposal": {"destination": "screenplay", "question": "Develop this opening?", "scope": "Opening only",
                     "why": "The intention is clear.", "next_step": "Develop a screenplay candidate; no image generation."}}}


class Model:
    name = "provider-independent-test-model"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def ask(self, system, prompt, schema):
        self.calls.append((system, prompt, schema))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer() if callable(answer) else copy.deepcopy(answer)


class Runtime:
    """Real application operations on a disposable film, no model or provider calls."""

    def __init__(self, root):
        self.root = root
        self.writes = []

    def production(self):
        return load_production(self.root)

    def creation(self):
        return creation_view(self.root)

    def budget(self):
        return {"spent_usd": 0, "limit_usd": 0}

    def screenplay(self):
        return {"files": [{"path": name, "text": (self.root / name).read_text()}
                          for name in self.production().get("script_files", [])]}

    def storyboard(self):
        from cine_toaster.storyboard import storyboard_view
        return storyboard_view(self.root)

    def scene(self, scene):
        return next(item for item in self.production()["scenes"] if item["id"] == scene)

    def save_inception_draft(self, payload):
        self.writes.append(copy.deepcopy(payload))
        return save_creation_draft(self.root, actor=AGENT, **payload)

    def assess_inception(self, payload):
        self.writes.append(copy.deepcopy(payload))
        return record_inception_assessment(self.root, actor=AGENT, **payload)


@unittest.skipUnless(HAS_AGENTS, "the agents extra is not installed")
class InceptionAgentTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / "film"
        shutil.copytree(DEMO, self.root)
        self.runtime = Runtime(self.root)

    def turn(self, graph, text="Develop an idea", room="creation", message_id=None, extra=None):
        context = [{"description": "Current room", "value": room}]
        context += extra or []
        return graph.invoke({"messages": [HumanMessage(content=text, id=message_id)], "ag-ui": {"context": context}},
                            {"configurable": {"thread_id": "test-conversation"}})

    def test_creation_routes_to_a_specialist_with_whole_film_and_cross_stage_context(self):
        model = Model(respond())
        state = self.turn(build(model, self.runtime, MemorySaver()))
        self.assertEqual(state["active_role"], "inception")
        self.assertEqual(state["agent_status"]["state"], "needs_direction")
        self.assertIn("Inception specialist", model.calls[0][0])
        self.assertIn("SC-030", model.calls[0][1])
        self.assertIn("screenplay", model.calls[0][1])
        self.assertIn("storyboard", model.calls[0][1])
        self.assertIn(self.runtime.production()["title"], model.calls[0][1])
        self.assertEqual(self.runtime.writes, [])

    def test_blank_film_routes_to_inception_but_imported_screenplay_does_not(self):
        production = {**self.runtime.production(), "scenes": [], "script_files": []}
        model = Model(respond())
        with patch.object(self.runtime, "production", return_value=production):
            state = self.turn(build(model, self.runtime), room="overview")
        self.assertEqual(state["active_role"], "inception")
        production["script_files"] = ["imported.fountain"]
        model = Model({"reply": "Your screenplay is already imported.", "action": "none"})
        with patch.object(self.runtime, "production", return_value=production):
            state = self.turn(build(model, self.runtime), room="overview")
        self.assertEqual(state["active_role"], "coordinator")

    def test_actual_new_production_title_page_is_not_mistaken_for_a_developed_screenplay(self):
        from cine_toaster.new_production import create_production
        root = self.root.parent / "new-film"
        create_production(root, "An untouched new film")
        model = Model(respond())
        state = self.turn(build(model, Runtime(root)), room="overview")
        self.assertEqual(state["active_role"], "inception")

    def test_coordinator_can_delegate_from_another_room(self):
        model = Model({"action": "delegate_inception", "reply": ""}, respond())
        state = self.turn(build(model, self.runtime), room="overview")
        self.assertEqual(state["active_role"], "inception")
        self.assertIn("Production Coordinator", model.calls[0][0])
        self.assertIn("Inception specialist", model.calls[1][0])
        for system, prompt, _ in model.calls:
            self.assertIn('Work/review unit: the canonical sequence', system)
            self.assertIn('Canonical work structure:', prompt)
            self.assertIn('the-reply', prompt)

    def test_coordinator_can_read_a_sequence_by_id_without_narrowing_to_one_scene(self):
        model = Model({'action': 'read', 'reply': '', 'query': 'work_structure', 'sequence': 'the-reply'},
                      {'action': 'none', 'reply': 'The Reply includes SC-010 and SC-030.'})
        state = self.turn(build(model, self.runtime), room='overview')
        self.assertEqual(state['notes'][0]['args'], {'sequence': 'the-reply'})
        records = json.loads(state['notes'][0]['result'])
        self.assertEqual(records['sequences'][0]['scene_ids'], ['SC-010', 'SC-030'])
        self.assertEqual(self.runtime.writes, [])

    def test_it_saves_actual_versions_and_readiness_not_just_a_chat_proposal(self):
        screenplay_bytes = {name: (self.root / name).read_bytes() for name in self.runtime.production()["script_files"]}
        def screenplay():
            concept_id = load_creation(self.root)["drafts"][0]["id"]
            return {"action": "save_screenplay", "reply": "", "draft": {
                "title": "Opening draft", "text": "INT. ROOM - DAY\n\nA child discovers light.", "concept": concept_id}}
        model = Model(concept(), screenplay, assessment(), respond("A versão está pronta para sua revisão.", "needs_review"))
        state = self.turn(build(model, self.runtime, MemorySaver()))
        value = creation_view(self.root)
        self.assertEqual(value["revision"], 3)
        self.assertEqual([item["kind"] for item in value["drafts"]], ["concept", "screenplay"])
        self.assertEqual(value["drafts"][0]["actor"], AGENT.public_dict())
        self.assertEqual(value["drafts"][1]["inputs"][0]["id"], value["drafts"][0]["id"])
        self.assertEqual(value["inception_review"]["current"]["status"], "awaiting_decision")
        self.assertEqual(value["assessment_decisions"], [])
        self.assertEqual(state["agent_status"]["state"], "needs_review")
        self.assertEqual(len(state["inception_receipts"]), 3)
        self.assertTrue(all(item["ok"] for item in state["inception_receipts"]))
        for name, original in screenplay_bytes.items():
            self.assertEqual((self.root / name).read_bytes(), original)

    def test_canonical_human_guidance_produces_a_retained_revision(self):
        first = save_creation_draft(self.root, kind="concept", title="Light", text="Original", expected_revision=0, actor=AGENT)
        saved = record_inception_assessment(self.root, **assessment()["assessment"], expected_revision=1, actor=AGENT)
        decision = decide_inception_assessment(self.root, assessment=saved["assessment"]["id"], outcome="changes_requested",
            guidance="Make the discovery quieter.", expected_revision=2, actor=Actor(id="human", kind="human"))["decision"]
        model = Model(concept("A quieter discovery.", based_on=first["draft"]["id"]), assessment(),
                      respond("Nova versão salva para sua revisão.", "needs_review"))
        state = self.turn(build(model, self.runtime, MemorySaver()), room="overview",
            message_id="decision-" + decision["id"], extra=[{"description": "Inception decision id", "value": decision["id"]}])
        value = creation_view(self.root)
        self.assertEqual(value["drafts"][0], first["draft"])
        self.assertEqual(value["drafts"][1]["based_on"], first["draft"]["id"])
        self.assertIn("Make the discovery quieter", model.calls[0][1])
        self.assertEqual(state["agent_status"]["state"], "needs_review")
        self.assertEqual(len(value["assessment_decisions"]), 1)

    def test_forged_or_stale_decision_handoff_never_runs_the_model(self):
        model = Model()
        state = self.turn(build(model, self.runtime), message_id="decision-invented",
            extra=[{"description": "Inception decision id", "value": "invented"}])
        self.assertEqual(model.calls, [])
        self.assertEqual(state["agent_status"]["state"], "blocked")

    def test_human_approval_can_continue_to_an_exact_concept_linked_screenplay_candidate(self):
        first = save_creation_draft(self.root, kind="concept", title="Light", text="Original", expected_revision=0, actor=AGENT)
        saved = record_inception_assessment(self.root, **assessment()["assessment"], expected_revision=1, actor=AGENT)
        decision = decide_inception_assessment(self.root, assessment=saved["assessment"]["id"], outcome="approved",
            guidance="", expected_revision=2, actor=Actor(id="human", kind="human"))["decision"]
        model = Model({"action": "save_screenplay", "reply": "", "draft": {
            "title": "Opening", "text": "INT. ROOM - DAY\n\nA discovery.", "concept": first["draft"]["id"]}},
            respond("Screenplay candidate saved; storyboard generation is not integrated.", "blocked"))
        state = self.turn(build(model, self.runtime), message_id="decision-" + decision["id"],
            extra=[{"description": "Inception decision id", "value": decision["id"]}])
        self.assertEqual(load_creation(self.root)["drafts"][-1]["kind"], "screenplay")
        self.assertIn("Develop a screenplay candidate", model.calls[0][1])
        self.assertEqual(len(load_creation(self.root)["assessment_decisions"]), 1)
        self.assertEqual(state["agent_status"]["state"], "blocked")

    def test_arbitrary_approval_generation_or_shell_tools_are_not_executed(self):
        for action in ("approve_storyboard", "decide_inception", "generate_reference", "shell", "delete"):
            with self.subTest(action=action):
                model = Model({"reply": "done", "action": action})
                state = self.turn(build(model, self.runtime))
                self.assertEqual(state["agent_status"]["state"], "blocked")
        self.assertEqual(self.runtime.writes, [])

    def test_a_review_request_must_refer_to_an_actual_saved_assessment(self):
        state = self.turn(build(Model(respond("Approve it", "needs_review")), self.runtime))
        self.assertEqual(state["agent_status"]["state"], "blocked")
        self.assertEqual(load_creation(self.root)["revision"], 0)

    def test_reads_are_bounded_and_success_is_not_fabricated(self):
        model = Model(*[{"action": "read", "query": "budget", "reply": ""}] * 5)
        state = self.turn(build(model, self.runtime))
        self.assertEqual(state["agent_status"]["state"], "resource_limit")
        self.assertEqual(len(state["inception_receipts"]), 4)

    def test_writes_are_bounded_and_previous_versions_survive(self):
        model = Model(*[concept(f"Alternative {number}") for number in range(4)])
        state = self.turn(build(model, self.runtime))
        self.assertEqual(state["agent_status"]["state"], "resource_limit")
        self.assertEqual(len(load_creation(self.root)["drafts"]), 3)

    def test_model_failure_stops_without_a_fake_delivery(self):
        state = self.turn(build(Model(ModelUnavailable("test failure")), self.runtime))
        self.assertEqual(state["agent_status"]["state"], "blocked")
        self.assertEqual(load_creation(self.root)["revision"], 0)

    def test_conflict_is_a_failed_receipt_not_a_silent_revision_refresh(self):
        def competing_writer():
            save_creation_draft(self.root, kind="concept", title="Other author", text="Concurrent", expected_revision=0, actor=AGENT)
            return concept()
        model = Model(competing_writer, respond("Outra versão chegou; preciso reler.", "blocked"))
        state = self.turn(build(model, self.runtime))
        self.assertFalse(state["inception_receipts"][0]["ok"])
        self.assertEqual(state["inception_context"]["creation"]["revision"], 0)
        self.assertEqual(load_creation(self.root)["revision"], 1)

    def test_explicit_reread_allows_reasoning_again_after_a_conflict(self):
        def competing_writer():
            save_creation_draft(self.root, kind="concept", title="Other", text="Concurrent", expected_revision=0, actor=AGENT)
            return concept()
        model = Model(competing_writer, {"action": "read", "query": "creation", "reply": ""}, concept(), respond("Saved", "complete"))
        state = self.turn(build(model, self.runtime))
        self.assertEqual([item["ok"] for item in state["inception_receipts"]], [False, True, True])
        self.assertEqual(len(load_creation(self.root)["drafts"]), 2)

    def test_material_change_refuses_assessment_even_when_creation_revision_matches(self):
        def changed_script():
            name = self.runtime.production()["script_files"][0]
            path = self.root / name
            path.write_text(path.read_text() + "\nA changed ending.\n")
            return assessment()
        model = Model(changed_script, respond("O roteiro mudou; preciso reavaliar.", "blocked"))
        state = self.turn(build(model, self.runtime))
        self.assertFalse(state["inception_receipts"][0]["ok"])
        self.assertIn("source material changed", state["inception_receipts"][0]["error"])
        self.assertEqual(load_creation(self.root)["revision"], 0)

    def test_material_change_also_refuses_a_candidate_publication(self):
        def changed_script():
            path = self.root / self.runtime.production()["script_files"][0]
            path.write_text(path.read_text() + "\nA different scene.\n")
            return concept()
        state = self.turn(build(Model(changed_script, respond("Source changed", "blocked")), self.runtime))
        self.assertFalse(state["inception_receipts"][0]["ok"])
        self.assertEqual(load_creation(self.root)["revision"], 0)

    def test_successful_commit_followed_by_failed_refresh_is_not_reported_as_a_failed_write(self):
        original = self.runtime.creation()
        model = Model(concept())
        with patch.object(self.runtime, "creation", side_effect=[original, RuntimeError("test refresh failure")]):
            state = self.turn(build(model, self.runtime))
        self.assertEqual(load_creation(self.root)["revision"], 1)
        self.assertTrue(state["inception_receipts"][0]["ok"])
        self.assertEqual(state["production_update"]["revision"], 1)
        self.assertEqual(state["agent_status"]["state"], "blocked")
        self.assertIn("foi salva", state["messages"][-1].content)

    def test_completed_turn_replay_does_not_append_a_second_candidate(self):
        model = Model(concept(), respond("Saved", "complete"))
        graph = build(model, self.runtime, MemorySaver())
        self.turn(graph, message_id="same-input")
        self.turn(graph, message_id="same-input")
        self.assertEqual(len(load_creation(self.root)["drafts"]), 1)
        self.assertEqual(len(model.calls), 2)

    def test_existing_thread_cannot_switch_project_identity(self):
        model = Model(respond())
        graph = build(model, self.runtime, MemorySaver())
        self.turn(graph)
        with patch.object(self.runtime, "production", return_value={**self.runtime.production(), "id": "another-film"}):
            state = self.turn(graph)
        self.assertEqual(state["agent_status"]["state"], "blocked")
        self.assertEqual(len(model.calls), 1)

    def test_specialist_returns_to_existing_coordinator_navigation(self):
        model = Model({"action": "return_to_coordinator", "reply": ""},
                      {"action": "none", "reply": "Abri o storyboard.", "navigate": {"room": "storyboard"}})
        state = self.turn(build(model, self.runtime))
        self.assertEqual(state["active_role"], "coordinator")
        self.assertEqual(state["navigate"]["room"], "storyboard")

    def test_specialist_runs_over_the_existing_ag_ui_endpoint(self):
        from fastapi.testclient import TestClient
        from cine_toaster.agents import server
        model = Model(concept(), assessment(), respond("Pronto para revisão", "needs_review"))
        with patch.object(server, "RuntimeClient", return_value=self.runtime):
            application = server.app("http://unused", model=model)
        body = {"threadId": "inception-agui", "runId": "r1", "state": {}, "tools": [], "forwardedProps": {},
                "context": [{"description": "Current room", "value": "creation"}],
                "messages": [{"id": "m1", "role": "user", "content": "Develop the opening"}]}
        with TestClient(application) as client:
            response = client.post("/", json=body, headers={"accept": "text/event-stream"})
        events = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:")]
        self.assertIn("RUN_FINISHED", [item["type"] for item in events])
        snapshots = [item["snapshot"] for item in events if item["type"] == "STATE_SNAPSHOT"]
        self.assertEqual(snapshots[-1]["agent_status"]["state"], "needs_review")
        self.assertEqual(load_creation(self.root)["revision"], 2)

    def test_http_tools_use_shared_operations_and_agent_attribution(self):
        from http.server import ThreadingHTTPServer
        from cine_toaster.web import ProjectBrowserHandler
        from cine_toaster.agents.runtime_client import RuntimeClient
        server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
        server.project_root = self.root
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            runtime = RuntimeClient(f"http://127.0.0.1:{server.server_address[1]}")
            model = Model(concept(), assessment(), respond("Review it", "needs_review"))
            state = self.turn(build(model, runtime))
            self.assertEqual(state["agent_status"]["state"], "needs_review")
            self.assertEqual(load_creation(self.root)["drafts"][0]["actor"], AGENT.public_dict())
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
