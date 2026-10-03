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
        self.addCleanup(self.manager.shutdown, wait=False)
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
        self.assertNotIn("generate", reads)

    def test_it_reads_the_film(self) -> None:
        self.assertIn("SC-030", self.call("film_overview"))
        self.assertIn("P3", self.call("read_shot", {"scene": "SC-030", "shot": "P3"}))
        locations = self.call("list_locations")
        self.assertEqual(locations[0]["id"], "LISTENING-STATION")
        self.assertTrue(any(move["id"] == "rise-and-reveal" for move in self.call("list_camera_moves")))
        self.assertTrue(any(sound["id"] == "room-tone" for sound in self.call("list_sounds")))

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
