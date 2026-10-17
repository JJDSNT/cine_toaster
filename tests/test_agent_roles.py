"""Roles are declared; models are described, never chosen (ADR 0034)."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cine_toaster.agents.catalog import adapter_for, describe, load, role_models
from cine_toaster.agents.models import ClaudeApi, ClaudeCli, CodexCli, ModelUnavailable, supports
from cine_toaster.agents.roles import ROLES, missing, scratch_fields, scratch_reset
from cine_toaster.errors import ValidationError

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode()


class RoleDeclarationTests(unittest.TestCase):
    def test_reset_is_fresh_every_turn(self):
        first, second = scratch_reset(), scratch_reset()
        first["inception_receipts"].append("x")
        self.assertEqual(second["inception_receipts"], [])
        self.assertNotIn("art_job", first)  # kept across turns: a job outlives the turn that started it
        self.assertIn("art_job", scratch_fields())

    def test_no_two_roles_declare_the_same_field(self):
        seen: dict[str, str] = {}
        for role in ROLES.values():
            for name in [*role.scratch, *role.kept]:
                self.assertNotIn(name, seen, f"{name} declared by {seen.get(name)} and {role.id}")
                seen[name] = role.id

    def test_a_reviewer_names_the_role_it_works_within(self):
        for role in ROLES.values():
            if role.within:
                self.assertIn(role.within, ROLES)

    def test_vision_is_needed_only_where_pixels_are_judged(self):
        text_only = SimpleNamespace(name="t", capabilities=frozenset({"structured_output"}), ask=lambda *a: {})
        self.assertEqual(missing("visual_prevalidation", text_only), ["vision"])
        self.assertEqual(missing("inception", text_only), [])


class CapabilityTests(unittest.TestCase):
    def test_every_adapter_declares_images(self):
        for adapter in (ClaudeCli(), ClaudeApi(), CodexCli()):
            self.assertTrue(supports(adapter, "vision"), adapter.name)
            self.assertFalse(supports(adapter, "web"), adapter.name)

    def test_an_undeclared_double_is_taken_at_its_methods(self):
        self.assertFalse(supports(SimpleNamespace(ask=lambda *a: {}), "vision"))
        self.assertTrue(supports(SimpleNamespace(ask=lambda *a: {}, ask_images=lambda *a: {}), "vision"))

    def test_claude_api_sends_pictures_inside_the_message(self):
        sent = {}

        def create(**kwargs):
            sent.update(kwargs)
            return SimpleNamespace(stop_reason="end_turn", model="m", usage=None,
                                   content=[SimpleNamespace(type="text", text='{"verdict": "inconclusive"}')])

        client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
        model = ClaudeApi(client=client)
        with patch.object(ClaudeApi, "available", return_value=""), \
                patch.dict("sys.modules", {"anthropic": SimpleNamespace(
                    AuthenticationError=OSError, RateLimitError=OSError, APIStatusError=OSError,
                    APIConnectionError=OSError)}):
            answer = model.ask_images("system", "look", {"type": "object"}, [{"mime_type": "image/png", "data": PNG}])
        self.assertEqual(answer, {"verdict": "inconclusive"})
        content = sent["messages"][0]["content"]
        self.assertEqual(content[0], {"type": "text", "text": "look"})
        self.assertEqual(content[1]["source"]["media_type"], "image/png")
        self.assertEqual(content[1]["source"]["data"], PNG)

    def test_claude_cli_streams_pictures_and_grants_no_tool(self):
        def run(command, **kwargs):
            run.command, run.input = command, kwargs["input"]
            result = {"type": "result", "structured_output": {"verdict": "ready_for_human"}}
            return subprocess.CompletedProcess(command, 0, json.dumps({"type": "system"}) + "\n" + json.dumps(result), "")

        with patch("cine_toaster.agents.models.shutil.which", return_value="/bin/claude"), \
                patch("cine_toaster.agents.models.subprocess.run", run):
            answer = ClaudeCli(model="claude-opus-5-5").ask_images(
                "system", "look", {"type": "object"}, [{"mime_type": "image/png", "data": PNG}])
        self.assertEqual(answer, {"verdict": "ready_for_human"})
        self.assertEqual(run.command[run.command.index("--tools") + 1], "")
        self.assertIn("stream-json", run.command)
        self.assertEqual(run.command[run.command.index("--model") + 1], "claude-opus-5-5")
        message = json.loads(run.input)["message"]["content"]
        self.assertEqual(message[1]["source"]["data"], PNG)

    def test_images_are_bounded_whichever_adapter_carries_them(self):
        with patch.object(ClaudeApi, "available", return_value=""), \
                patch.dict("sys.modules", {"anthropic": SimpleNamespace()}):
            with self.assertRaisesRegex(ModelUnavailable, "eight images"):
                ClaudeApi(client=object()).ask_images("s", "p", {}, [{"mime_type": "image/png", "data": PNG}] * 9)
            with self.assertRaisesRegex(ModelUnavailable, "format"):
                ClaudeApi(client=object()).ask_images("s", "p", {}, [{"mime_type": "image/gif", "data": PNG}])


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.file = self.folder / "models.yaml"

    def test_built_in_catalogue_describes_every_adapter(self):
        catalogue = load(self.file)
        self.assertEqual(set(catalogue["adapters"]), {"claude-cli", "claude-api", "codex-cli"})
        self.assertEqual(catalogue["roles"], {})
        for entry in catalogue["models"].values():
            self.assertTrue(set(entry["strengths"]) <= set(catalogue["vocabulary"]))
            self.assertTrue(entry["source"])

    def test_the_persons_file_extends_and_binds(self):
        self.file.write_text("models:\n  claude-haiku-5-5: {source: my trials}\n  mine: {strengths: [planning]}\n"
                             "roles:\n  visual_prevalidation: claude-api:claude-opus-5-5\n", "utf-8")
        catalogue = load(self.file)
        self.assertEqual(catalogue["models"]["claude-haiku-5-5"]["source"], "my trials")
        self.assertEqual(catalogue["models"]["claude-haiku-5-5"]["strengths"], ["fast_extraction"])
        self.assertIn("mine", catalogue["models"])
        default = SimpleNamespace(name="default")
        pick = role_models(default, catalogue)
        self.assertIs(pick("inception"), default)
        bound = pick("visual_prevalidation")
        self.assertIsInstance(bound, ClaudeApi)
        self.assertEqual(bound.model, "claude-opus-5-5")
        self.assertEqual(describe(bound, catalogue)["model_entry"]["cost_class"], "high")

    def test_no_binding_means_one_model_for_every_role(self):
        default = SimpleNamespace(name="default")
        pick = role_models(default, load(self.file))
        self.assertTrue(all(pick(role) is default for role in ROLES))

    def test_unknown_roles_and_adapters_are_refused(self):
        self.file.write_text("roles:\n  producer: claude-api\n", "utf-8")
        with self.assertRaises(ValidationError):
            load(self.file)
        with self.assertRaisesRegex(ModelUnavailable, "Unknown model adapter"):
            adapter_for("installed-cli")

    def test_the_default_file_is_under_the_persons_config(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.folder)}):
            (self.folder / "cine-toaster").mkdir()
            (self.folder / "cine-toaster" / "models.yaml").write_text("roles:\n  inception: codex-cli\n", "utf-8")
            self.assertEqual(load()["roles"], {"inception": "codex-cli"})


if __name__ == "__main__":
    unittest.main()


try:
    from cine_toaster.agents.loop import Loop, step
    HAS_LOOP = True
except ImportError:  # the agents extra
    HAS_LOOP = False


@unittest.skipUnless(HAS_LOOP, "the agents extra is not installed")
class LoopTests(unittest.TestCase):
    SCHEMA = {"properties": {"action": {"enum": ["save", "respond", "delegate_continuity"]}}}

    def loop(self, ready=False):
        return Loop(role="directing", steps="planning_steps", pending="planning_pending", schema=self.SCHEMA,
                    limit="limit", review_ready=lambda state: ready, not_ready="nothing saved")

    def ask(self, answer):
        return SimpleNamespace(ask=lambda system, prompt, schema: answer)

    def test_the_budget_is_checked_before_the_model_is_asked(self):
        model = SimpleNamespace(ask=lambda *a: self.fail("asked past the budget"))
        state = step(self.loop(), {"planning_steps": 8, "turn": "t"}, model, "s", "p")
        self.assertEqual(state["agent_status"]["state"], "resource_limit")
        self.assertEqual(state["completed_turn"], "t")

    def test_an_action_outside_the_role_runs_nothing(self):
        for answer in ({"action": "shell"}, ["save"], None):
            state = step(self.loop(), {}, self.ask(answer), "s", "p")
            self.assertEqual(state["agent_status"]["state"], "blocked")
            self.assertEqual(state["planning_pending"], {})

    def test_needs_review_needs_something_saved(self):
        answer = {"action": "respond", "status": "needs_review", "reply": "Look."}
        self.assertEqual(step(self.loop(), {}, self.ask(answer), "s", "p")["messages"][0].content, "nothing saved")
        self.assertEqual(step(self.loop(ready=True), {}, self.ask(answer), "s", "p")["agent_status"]["state"],
                         "needs_review")

    def test_a_tool_action_waits_and_a_delegation_hands_the_turn_on(self):
        state = step(self.loop(), {"planning_steps": 1}, self.ask({"action": "save", "reply": ""}), "s", "p")
        self.assertEqual((state["planning_pending"]["action"], state["planning_steps"]), ("save", 2))
        state = step(self.loop(), {"planning_scene": "SC-1"}, self.ask({"action": "delegate_continuity"}), "s", "p")
        self.assertEqual((state["active_role"], state["planning_role"], state["planning_scene"]),
                         ("continuity", "continuity", "SC-1"))

    def test_a_failed_model_is_said_not_raised(self):
        def broken(*args):
            raise ModelUnavailable("offline")
        state = step(self.loop(), {}, SimpleNamespace(ask=broken), "s", "p")
        self.assertIn("offline", state["messages"][0].content)


class BoundedTests(unittest.TestCase):
    def test_a_cut_is_valid_json_and_says_what_was_left_out(self):
        from cine_toaster.agents.inception import bounded

        value = {"drafts": [{"id": f"d{i}", "text": "x" * 5000} for i in range(60)], "title": "Light"}
        text = bounded(value, 9000)
        self.assertLessEqual(len(text), 9000)
        cut = json.loads(text)
        self.assertEqual(cut["title"], "Light")
        self.assertEqual(cut["drafts"][0]["id"], "d0")
        self.assertEqual(cut["drafts"][-1]["id"], "d59")  # the newest work survives the cut
        self.assertTrue(any("items cut" in item for item in cut["drafts"] if isinstance(item, str)))
        self.assertIn("characters cut", cut["drafts"][0]["text"])

    def test_what_fits_is_untouched_and_what_never_fits_says_so(self):
        from cine_toaster.agents.inception import bounded

        self.assertEqual(bounded({"a": "b"}), '{"a": "b"}')
        self.assertIn("focused read", json.loads(bounded({f"k{i}": i for i in range(5000)}, 200))["cut"])
