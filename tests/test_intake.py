"""Format intake: an agent asks what a format needs, a person answers (SPEC-0020)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from cine_toaster.creation import load_creation
from cine_toaster.decision_inbox import decision_inbox
from cine_toaster.errors import PermissionDeniedError, PersistenceError, ValidationError
from cine_toaster.intake import MAX_OPEN, answer_intake, ask_intake, intake_view
from cine_toaster.state import Actor

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
AGENT = Actor(id="inception", kind="agent")
HUMAN = Actor(id="director", kind="human")


def question(item, text="?", why="It matters."):
    return {"item": item, "question": text, "why": why}


class IntakeCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / "film"
        shutil.copytree(DEMO, self.root)

    def declare(self, style):
        path = self.root / "project.yaml"
        value = yaml.safe_load(path.read_text())
        value["style"] = style
        path.write_text(yaml.safe_dump(value, allow_unicode=True))

    def revision(self):
        return load_creation(self.root)["revision"]


class IntakeTests(IntakeCase):
    def test_an_unknown_format_is_the_first_question(self):
        view = intake_view(self.root)
        self.assertIsNone(view["format"])
        self.assertEqual([row["id"] for row in view["items"]], ["format"])
        self.assertEqual(view["missing_required"], ["format"])
        self.assertEqual(view["production_says"], "Short film · 8 minutes")  # evidence the agent must weigh

    def test_a_declared_format_brings_its_sheet(self):
        self.declare({"format": "music-video"})
        view = intake_view(self.root)
        self.assertEqual(view["format"], {"id": "music-video", "name": "Music video", "source": "declared"})
        ids = [row["id"] for row in view["items"]]
        self.assertNotIn("format", ids)
        self.assertIn("track", ids)
        track = next(row for row in view["items"] if row["id"] == "track")
        self.assertTrue(track["why"] and track["unlocks"] == "assembly")

    def test_an_agent_asks_a_person_answers_and_neither_does_the_other(self):
        asked = ask_intake(self.root, questions=[question("format", "Que tipo de filme é?")],
                           expected_revision=0, actor=AGENT)["questions"][0]
        with self.assertRaises(PermissionDeniedError):
            ask_intake(self.root, questions=[question("x")], expected_revision=1, actor=HUMAN)
        with self.assertRaises(PermissionDeniedError):
            answer_intake(self.root, question=asked["id"], answer="Um videoclipe", expected_revision=1, actor=AGENT)
        answer_intake(self.root, question=asked["id"], answer="Um videoclipe", expected_revision=1, actor=HUMAN)
        with self.assertRaises(ValidationError):
            answer_intake(self.root, question=asked["id"], answer="Outro", expected_revision=2, actor=HUMAN)
        row = intake_view(self.root)["items"][0]
        self.assertEqual((row["status"], row["answer"]["answer"]), ("answered", "Um videoclipe"))

    def test_an_answer_naming_a_format_brings_its_sheet_without_editing_the_production(self):
        asked = ask_intake(self.root, questions=[question("format")], expected_revision=0, actor=AGENT)["questions"][0]
        answer_intake(self.root, question=asked["id"], answer="music video", expected_revision=1, actor=HUMAN)
        view = intake_view(self.root)
        self.assertEqual(view["format"]["source"], "answered")
        self.assertIn("track", [row["id"] for row in view["items"]])
        self.assertNotIn("style", yaml.safe_load((self.root / "project.yaml").read_text()))

    def test_a_few_questions_at_a_time_and_none_twice(self):
        self.declare({"format": "music-video"})
        with self.assertRaises(ValidationError):
            ask_intake(self.root, questions=[question(f"q{i}") for i in range(MAX_OPEN + 1)],
                       expected_revision=0, actor=AGENT)
        ask_intake(self.root, questions=[question("track")], expected_revision=0, actor=AGENT)
        with self.assertRaises(ValidationError):
            ask_intake(self.root, questions=[question("track")], expected_revision=1, actor=AGENT)
        with self.assertRaises(ValidationError):
            ask_intake(self.root, questions=[question("lyrics", why="")], expected_revision=1, actor=AGENT)

    def test_asking_an_answered_item_again_names_the_answer(self):
        asked = ask_intake(self.root, questions=[question("format")], expected_revision=0, actor=AGENT)["questions"][0]
        answer = answer_intake(self.root, question=asked["id"], answer="A short", expected_revision=1, actor=HUMAN)["answer"]
        with self.assertRaises(ValidationError):
            ask_intake(self.root, questions=[question("format")], expected_revision=2, actor=AGENT)
        again = ask_intake(self.root, questions=[{**question("format", "Short, but how long?"), "based_on": answer["id"]}],
                           expected_revision=2, actor=AGENT)
        self.assertEqual(again["questions"][0]["based_on"], answer["id"])
        self.assertEqual(intake_view(self.root)["items"][0]["status"], "open")

    def test_open_questions_wait_in_the_inbox(self):
        ask_intake(self.root, questions=[question("format", "Que tipo de filme é?", "Decide a ficha.")],
                   expected_revision=0, actor=AGENT)
        item = next(item for item in decision_inbox(self.root)["items"] if item["kind"] == "question")
        self.assertEqual((item["question"], item["why"], item["actions"]), ("Que tipo de filme é?", "Decide a ficha.", ["answer"]))

    def test_a_forged_answer_is_refused_on_reading(self):
        asked = ask_intake(self.root, questions=[question("format")], expected_revision=0, actor=AGENT)["questions"][0]
        answer_intake(self.root, question=asked["id"], answer="A short", expected_revision=1, actor=HUMAN)
        path = self.root / "creation" / "state.json"
        state = json.loads(path.read_text())
        state["intake_answers"][0]["actor"] = AGENT.public_dict()
        path.write_text(json.dumps(state))
        with self.assertRaises(PersistenceError):
            load_creation(self.root)


class IntakeCliTests(IntakeCase):
    def test_the_person_answers_at_the_terminal(self):
        import io
        from contextlib import redirect_stdout

        from cine_toaster.cli import main

        asked = ask_intake(self.root, questions=[question("format", "Que tipo de filme é?")],
                           expected_revision=0, actor=AGENT)["questions"][0]
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["intake", str(self.root)]), 0)
        self.assertIn(asked["id"], out.getvalue())
        with redirect_stdout(io.StringIO()):
            main(["intake", str(self.root), "--answer", asked["id"], "Um videoclipe"])
        answer = load_creation(self.root)["intake_answers"][0]
        self.assertEqual((answer["answer"], answer["actor"]["kind"]), ("Um videoclipe", "human"))


try:
    from langchain_core.messages import HumanMessage
    from cine_toaster.agents.assistant import build
    from test_inception_agent import Model, Runtime
    HAS_AGENTS = True
except ImportError:
    HAS_AGENTS = False


@unittest.skipUnless(HAS_AGENTS, "the agents extra is not installed")
class InterviewTests(IntakeCase):
    def test_inception_interviews_then_waits_for_the_person(self):
        self.declare({"format": "music-video"})

        class Interviewing(Runtime):
            def ask_intake(self, payload):
                return ask_intake(self.root, actor=AGENT, **payload)

        model = Model({"action": "ask_questions", "reply": "", "questions": [
                          question("track", "Qual é a música?", "A música é a linha do tempo.")]},
                      {"action": "respond", "reply": "Qual é a música?", "status": "needs_direction"})
        state = build(model, Interviewing(self.root)).invoke(
            {"messages": [HumanMessage(content="Quero fazer um videoclipe", id="m1")],
             "ag-ui": {"context": [{"description": "Current room", "value": "creation"}]}},
            {"configurable": {"thread_id": "interview"}})
        self.assertEqual(state["agent_status"]["state"], "needs_direction")
        self.assertIn('"track"', model.calls[0][1])          # the sheet is in what the role is shown
        self.assertIn("Interview before advancing", model.calls[0][0])
        view = intake_view(self.root)
        self.assertEqual(view["open_count"], 1)
        self.assertIn("Qual é a música?", model.calls[1][1])  # the receipt is seen before answering

    def test_an_answered_interview_continues_in_inception(self):
        asked = ask_intake(self.root, questions=[question("format")], expected_revision=0, actor=AGENT)["questions"][0]
        answer = answer_intake(self.root, question=asked["id"], answer="Um videoclipe", expected_revision=1,
                               actor=HUMAN)["answer"]
        model = Model({"action": "respond", "reply": "Entendido: um videoclipe.", "status": "complete"})
        message = "intake-" + answer["id"]
        state = build(model, Runtime(self.root)).invoke(
            {"messages": [HumanMessage(content="I answered your interview questions.", id=message)],
             "ag-ui": {"context": [{"description": "Current room", "value": "decisions"}]},
             "resume": {"intake": answer["id"], "message": message}},
            {"configurable": {"thread_id": "answered"}})
        self.assertEqual(state["routing_reason"], "Interview answered")
        self.assertIn("Inception specialist", model.calls[0][0])
        self.assertIn("Um videoclipe", model.calls[0][1])


if __name__ == "__main__":
    unittest.main()
