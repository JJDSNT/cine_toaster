"""The assistant knows what the page shows, points at shots, and acts only on a yes (ADR 0017)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

try:
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    from cine_toaster.agents.assistant import build, page_context, scene_digest
    from cine_toaster.agents.models import ModelUnavailable
    HAS_AGENTS = True
except ImportError:  # the `agents` extra
    HAS_AGENTS = False

from cine_toaster.project import load_production

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class FakeModel:
    name = "fake"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def ask(self, system, prompt, schema):
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeRuntime:
    def __init__(self):
        scene = next(item for item in load_production(DEMO)["scenes"] if item["id"] == "SC-030")
        scene["blocks"] = [{"id": "A", "shots": ["P2", "P3"], "versions": []}]
        scene["runs"] = []
        scene["gates"] = {"gate_1": {"id": "gate_1", "state": "waiting", "subject": "P3", "candidates": ["a", "b"]}}
        self.scene_record = scene
        self.commands: list[tuple[str, dict]] = []

    def scene(self, scene_id):
        return self.scene_record

    def command(self, command, payload):
        self.commands.append((command, payload))
        return {"revision": 7}


CONTEXT = [{"description": "Current scene id", "value": "SC-030"},
           {"description": "Selected shot", "value": "P3"}]


@unittest.skipUnless(HAS_AGENTS, "the agents extra is not installed")
class AssistantTests(unittest.TestCase):
    def run_turn(self, graph, text, thread="t1"):
        config = {"configurable": {"thread_id": thread}}
        return graph.invoke({"messages": [HumanMessage(content=text)], "ag-ui": {"context": CONTEXT}}, config), config

    def test_it_answers_from_the_page_and_the_records_and_points_at_a_shot(self) -> None:
        model = FakeModel({"reply": "Você está no P3; o portão da imagem espera você.", "highlight": "P3", "action": "none"})
        runtime = FakeRuntime()
        state, _ = self.run_turn(build(model, runtime, MemorySaver()), "O que falta?")
        self.assertEqual(state["highlight"], "P3")
        self.assertIn("P3", state["messages"][-1].content)
        # The model was told what the page shows and what the records say.
        self.assertIn("Selected shot: P3", model.prompts[0])
        self.assertIn("Gate gate_1 waits for the director", model.prompts[0])
        self.assertEqual(runtime.commands, [])

    def test_an_action_waits_for_a_yes_and_goes_through_a_command(self) -> None:
        model = FakeModel({"reply": "Posso iniciar.", "action": "start_workflow", "block": "A"})
        runtime = FakeRuntime()
        graph = build(model, runtime, MemorySaver())
        state, config = self.run_turn(graph, "Inicie o bloco A")
        interrupts = state["__interrupt__"]
        self.assertIn("Iniciar o workflow do bloco A da cena SC-030?", interrupts[0].value["message"])
        self.assertEqual(runtime.commands, [])  # nothing before the yes
        # What the records say right after: this run stopped at its first step.
        runtime.scene_record["runs"] = [{"id": "wf_1", "subject": {"block": "A"}, "state": "failed", "steps": [
            {"label": "Picture 3", "state": "failed", "note": "needs RUNPOD_API_KEY"},
            {"label": "Generate block A", "state": "pending"}]}]
        state = graph.invoke(Command(resume={"approved": True}), config)
        self.assertEqual(runtime.commands, [("start_workflow", {"scene_id": "SC-030", "block": "A"})])
        self.assertIn("revisão 7", state["messages"][-1].content)
        self.assertIn("parou: Picture 3 falhou — needs RUNPOD_API_KEY", state["messages"][-1].content)

    def test_a_no_changes_nothing(self) -> None:
        model = FakeModel({"reply": "Posso iniciar.", "action": "start_workflow", "block": "A"})
        runtime = FakeRuntime()
        graph = build(model, runtime, MemorySaver())
        _, config = self.run_turn(graph, "Inicie o bloco A")
        state = graph.invoke(Command(resume={"approved": False}), config)
        self.assertEqual(runtime.commands, [])
        self.assertEqual(state["proposal"], {})

    def test_it_cannot_propose_deciding_a_gate(self) -> None:
        model = FakeModel({"reply": "Aprovei.", "action": "decide_gate"})
        runtime = FakeRuntime()
        state, _ = self.run_turn(build(model, runtime, MemorySaver()), "Aprove você")
        self.assertEqual(state["proposal"], {})
        self.assertNotIn("__interrupt__", state)
        self.assertEqual(runtime.commands, [])

    def test_a_missing_model_is_said_in_the_chat(self) -> None:
        model = FakeModel(ModelUnavailable("claude is not on PATH"))
        state, _ = self.run_turn(build(model, FakeRuntime(), MemorySaver()), "Olá")
        self.assertIn("claude is not on PATH", state["messages"][-1].content)

    def test_page_context_reads_dicts_and_objects(self) -> None:
        class Context:
            description, value = "Current scene id", "SC-010"
        self.assertEqual(page_context({"ag-ui": {"context": [Context()]}}), {"Current scene id": "SC-010"})

    def test_the_digest_is_short_and_says_what_waits(self) -> None:
        digest = scene_digest(FakeRuntime().scene_record)
        self.assertIn("Block A: shots P2, P3", digest)
        self.assertIn("among 2 candidate(s)", digest)
        self.assertLess(len(digest), 1500)


@unittest.skipUnless(HAS_AGENTS, "the agents extra is not installed")
class AgUiTests(unittest.TestCase):
    def test_a_turn_over_ag_ui_streams_the_reply_and_the_shared_state(self) -> None:
        from fastapi.testclient import TestClient

        from cine_toaster.agents import server

        model = FakeModel({"reply": "Olhe o P3.", "highlight": "P3", "action": "none"})
        application = server.app("http://127.0.0.1:1", model=model)
        runtime = FakeRuntime()
        # The HTTP client is replaced by the fake runtime inside the compiled graph.
        import cine_toaster.agents.runtime_client as client_module
        original = client_module.RuntimeClient.scene
        client_module.RuntimeClient.scene = lambda self, scene_id: runtime.scene(scene_id)
        self.addCleanup(setattr, client_module.RuntimeClient, "scene", original)
        body = {"threadId": "t1", "runId": "r1", "state": {}, "tools": [], "context": CONTEXT, "forwardedProps": {},
                "messages": [{"id": "m1", "role": "user", "content": "O que falta?"}]}
        with TestClient(application) as client:
            response = client.post("/", json=body, headers={"accept": "text/event-stream"})
        events = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:")]
        types = [event["type"] for event in events]
        self.assertIn("RUN_STARTED", types)
        self.assertIn("RUN_FINISHED", types)
        text = "".join(event.get("delta", "") for event in events if event["type"] == "TEXT_MESSAGE_CONTENT")
        snapshots = [event["snapshot"] for event in events if event["type"] == "STATE_SNAPSHOT"]
        self.assertTrue(text == "Olhe o P3." or any("Olhe o P3." in json.dumps(s) for s in snapshots), types)
        self.assertEqual(snapshots[-1].get("highlight"), "P3")
        self.assertIn("Selected shot: P3", model.prompts[0])


if __name__ == "__main__":
    unittest.main()
