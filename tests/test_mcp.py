"""Claude Code on a film through Cine Toaster's MCP server (CT-0045)."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.project import load_scene

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_MCP = importlib.util.find_spec("mcp") is not None
HAS_FFMPEG = shutil.which("ffmpeg") is not None


@unittest.skipUnless(HAS_MCP, "the mcp extra is not installed (make install-mcp)")
class McpTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        self.addCleanup(self._restore)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        self.manager = JobManager(store=JobStore(base / "state" / "jobs.sqlite"))
        self.addCleanup(self.manager.shutdown, wait=True)  # its threads finish before the folder goes
        from cine_toaster.mcp_server import build

        self.server = build(self.root, self.manager)

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def call(self, name: str, arguments: dict | None = None):
        import anyio

        result = anyio.run(self.server.call_tool, name, arguments or {})
        self.assertFalse(result.is_error, result.content)
        structured = result.structured_content or {}
        return structured.get("result", structured) if set(structured) == {"result"} else structured

    def test_the_tools_are_the_products_and_the_directors_decisions_are_not_among_them(self) -> None:
        import anyio

        names = {tool.name for tool in anyio.run(self.server.list_tools)}
        self.assertTrue({"film_overview", "read_shot", "set_cut", "set_cuts", "set_reference", "start_workflow",
                         "assemble_scene", "generate", "wait_for_job"} <= names)
        # Gates, takes and the storyboard stay the director's (SPEC-0009); no tool writes authored files.
        for forbidden in ("decide_gate", "select_take", "approve_storyboard", "write_file", "edit_breakdown"):
            self.assertNotIn(forbidden, names)
        reads = {tool.name for tool in anyio.run(self.server.list_tools) if tool.annotations.read_only_hint}
        self.assertIn("plan_generation", reads)
        self.assertIn("read_work_structure", reads)
        self.assertIn('read_production_work', reads)
        self.assertNotIn('request_sequence_review', reads)
        # An agent asks the format interview; answering it is the person's (SPEC-0020).
        self.assertIn("read_intake", reads)
        self.assertTrue({"list_generation_recipes", "generation_health"} <= reads)
        self.assertIn("ask_intake_questions", names - reads)
        self.assertFalse({name for name in names if "answer" in name})
        self.assertTrue({"production_status", "continuity_ledger"} <= reads)
        self.assertNotIn("generate", reads)

    def test_it_reads_the_film(self) -> None:
        self.assertIn("SC-030", self.call("film_overview"))
        self.assertIn("P3", self.call("read_shot", {"scene": "SC-030", "shot": "P3"}))
        self.assertEqual(self.call("read_storyboard_candidates")["revision"], 0)
        locations = self.call("list_locations")
        self.assertEqual(locations[0]["id"], "LISTENING-STATION")
        self.assertTrue(any(move["id"] == "rise-and-reveal" for move in self.call("list_camera_moves")))
        self.assertTrue(any(sound["id"] == "room-tone" for sound in self.call("list_sounds")))
        self.assertTrue(any(item["id"] == "dread" for item in self.call("list_emotions")))

    def test_work_structure_and_guide_preserve_the_sequence_as_review_unit(self) -> None:
        value = self.call('read_work_structure', {'sequence': 'the-reply', 'scene': 'SC-010'})
        self.assertEqual(value['review_unit'], 'sequence')
        self.assertEqual(value['scene_sequences'], ['the-reply'])
        self.assertEqual(value['sequences'][0]['scene_ids'], ['SC-010', 'SC-030'])
        self.assertNotIn('approved', value)
        guide = self.call('how_to_make_a_film')
        self.assertIn('The sequence is the work and review unit', guide)
        self.assertIn('1-02A', guide)
        self.assertIn('work_structure', guide)

    def test_explicit_review_work_uses_shared_command_without_approval_or_dispatch(self) -> None:
        context = self.call('read_production_work')
        result = self.call('request_sequence_review', {'sequence': 'the-reply', 'title': 'Review the sequence',
            'rationale': 'The director requested the comparison.', 'expected_revision': context['revision'],
            'expected_source_digest': context['source_digest']})
        task = self.call('read_production_work')['items'][0]
        self.assertEqual(task['id'], result['request']['id'])
        self.assertEqual(task['owner'], 'coordinator')
        self.assertEqual(task['dispatch_status'], 'not_dispatched')
        self.assertFalse(task['human_action_required'])
        self.assertEqual(self.call('read_creation').get('assessment_decisions', []), [])

    def test_storyboard_import_is_project_scoped_and_not_an_approval(self) -> None:
        import base64
        image = self.root / "drawing.png"
        image.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a81sAAAAASUVORK5CYII="))
        arguments = {"scene": "SC-010", "shot": "P1", "image": "drawing.png", "title": "A draft", "expected_revision": 0}
        self.assertEqual(self.call("save_storyboard_candidate", arguments)["revision"], 1)
        self.assertIn("refused", self.call("save_storyboard_candidate", arguments))
        self.assertIn("refused", self.call("save_storyboard_candidate", {**arguments, "image": "../outside.png", "expected_revision": 1}))
        result = self.call("read_storyboard_candidates", {"scene": "SC-010"})
        self.assertEqual(result["candidates"][0]["review"], "not_recorded")
        self.assertEqual(result["revision"], 1)
        self.assertTrue(any(item["id"] == "viral-vertical" for item in self.call("list_styles")))

    def test_creation_candidates_are_shared_records_not_screenplay_replacements(self) -> None:
        from cine_toaster.creation import load_creation
        original = (self.root / "story/screenplay.fountain").read_bytes()
        self.assertEqual(self.call("read_creation")["revision"], 0)
        first = self.call("save_creation_candidate", {"kind": "concept", "title": "Premise", "text": "A new possibility.", "expected_revision": 0})
        second = self.call("save_creation_candidate", {"kind": "screenplay", "title": "Trial", "text": "Title: Trial\n\nA start.",
                           "concept": first["draft"]["id"], "expected_revision": 1})
        self.assertEqual(second["draft"]["inputs"][0]["id"], first["draft"]["id"])
        self.assertEqual(load_creation(self.root)["revision"], 2)
        self.assertEqual((self.root / "story/screenplay.fountain").read_bytes(), original)
        self.assertIn("refused", self.call("save_creation_candidate", {"kind": "concept", "title": "Conflict", "text": "No silent overwrite.", "expected_revision": 0}))
        from cine_toaster.references import add_reference
        picture = self.root / "exploration-fixture.png"
        picture.write_bytes(b"test reference")
        reference = add_reference(self.root, [picture], title="MCP exploration", kind="made")
        recorded = self.call("record_exploration_round", {"title": "First pass", "references": [reference.name],
                            "expected_revision": 2, "rationale": "Explore the age", "source": "Director's statement"})
        self.assertEqual(load_creation(self.root)["rounds"][0], recorded["round"])
        self.assertEqual(recorded["round"]["actor"]["kind"], "agent")

    def test_agent_assesses_inception_but_does_not_approve_its_own_direction(self) -> None:
        import anyio
        result = self.call("assess_inception", {"title": "Ready to write", "summary": "The intention is defined.",
            "readiness": [{"destination": "screenplay", "status": "ready", "summary": "We can explore the story.", "gaps": []}],
            "proposal": {"destination": "screenplay", "question": "Develop this direction?", "scope": "Draft writing.",
                         "why": "Enough context to begin.", "next_step": "Develop a retained screenplay candidate."},
            "references": [], "expected_revision": 0})
        self.assertEqual(result["assessment"]["actor"]["kind"], "agent")
        current = self.call("read_creation")["inception_review"]["current"]
        self.assertEqual(current["status"], "awaiting_decision")
        names = {tool.name for tool in anyio.run(self.server.list_tools)}
        self.assertNotIn("decide_inception_assessment", names)

    def test_an_agent_learns_the_flow_and_the_practices_from_the_product(self) -> None:
        import anyio

        self.assertIn("phase", self.server.instructions or "")
        guide = self.call("how_to_make_a_film")
        self.assertIn("Phase 1", guide)
        self.assertIn("toast storyboard approve", guide)
        practices = self.call("list_practices")
        self.assertTrue(any(item["id"] == "every-line-is-filmed" for item in practices))
        practice = self.call("read_practice", {"practice": "every-line-is-filmed"})
        self.assertIn("dialogue_uncovered", practice["enforced_by"])
        self.assertIn("refused", self.call("read_practice", {"practice": "no-such-practice"}))
        self.assertEqual(self.call("list_references"), [])
        reads = {tool.name for tool in anyio.run(self.server.list_tools) if tool.annotations.read_only_hint}
        self.assertTrue({"how_to_make_a_film", "list_practices", "read_practice", "list_references"} <= reads)
        self.assertNotIn("generate_reference", reads)

    def test_a_decision_is_recorded_as_claude_codes_and_a_refusal_is_an_answer(self) -> None:
        answer = self.call("set_cut", {"scene": "SC-030", "shot": "P2", "cut_type": "match", "why": "the stack's light"})
        self.assertEqual((answer["type"], answer["revision"]), ("cut.set", 1))
        entry = load_scene(self.root, "SC-030")["decision_log"][0]
        self.assertEqual(entry["actor"], {"id": "claude-code", "kind": "agent"})
        self.assertEqual(entry["rationale"], "the stack's light")
        refused = self.call("set_cut", {"scene": "SC-030", "shot": "P1", "cut_type": "match"})
        self.assertIn("opens the scene", refused["refused"])
        together = self.call("set_cuts", {"scene": "SC-030", "cuts": [{"shot": "P2", "cut_type": "l"},
                                                                     {"shot": "P3", "cut_type": "wipe"}]})
        self.assertIn("none of the set was applied", together["refused"])

    def test_paid_generation_needs_a_cap_that_covers_the_estimate(self) -> None:
        from types import SimpleNamespace
        from unittest import mock

        from cine_toaster import mcp_server

        planned = SimpleNamespace(estimate_usd=0.31)
        with mock.patch.object(mcp_server, "_generation_plan", return_value=(planned, False)), \
                mock.patch.object(self.manager, "submit") as submit:
            refused = self.call("generate", {"scene": "SC-030", "target": "A", "max_usd": 0.2})
        self.assertIn("above the US$ 0.200 this call allows; nothing was sent", refused["refused"])
        submit.assert_not_called()

    @unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
    def test_a_job_is_followed_and_its_version_joins_the_film(self) -> None:
        job = self.call("assemble_scene", {"scene": "SC-030", "summary": "from Claude Code"})
        self.assertEqual(job["kind"], "assemble")
        done = self.call("wait_for_job", {"job_id": job["id"], "seconds": 120})
        self.assertEqual(done["state"], "succeeded", json.dumps(done))
        self.assertIn("P3", done["result"]["takes"])
        versions = load_scene(self.root, "SC-030")["assemblies"]
        self.assertEqual(versions[-1]["summary"].split(".")[0], "from Claude Code")
        self.assertTrue((self.root / versions[-1]["media"]).is_file())


if __name__ == "__main__":
    unittest.main()
