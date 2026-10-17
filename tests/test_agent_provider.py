"""Provider selection is explicit host configuration, never a filmmaking role."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from cine_toaster.agents.models import ClaudeApi, ClaudeCli, CodexCli, ModelUnavailable, model_from_env
from cine_toaster.assistant_host import AssistantHost, unavailable_reason
from cine_toaster.cli import main


class ProviderSelectionTests(unittest.TestCase):
    def test_missing_provider_never_calls_an_adapter_even_when_credentials_exist(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "not-a-real-key"}, clear=True), \
                patch("cine_toaster.agents.models.ADAPTERS", {"installed-cli": Mock()}) as adapters:
            with self.assertRaisesRegex(ModelUnavailable, "No agent provider selected"):
                model_from_env()
            adapters["installed-cli"].assert_not_called()

    def test_existing_adapters_remain_explicit_choices(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(model_from_env("claude-cli"), ClaudeCli)
            self.assertIsInstance(model_from_env("claude-api"), ClaudeApi)
            self.assertIsInstance(model_from_env("codex-cli"), CodexCli)

    def test_missing_configuration_falls_back_to_the_current_codex_cli(self):
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "opaque-session-marker"}, clear=True):
            self.assertIsInstance(model_from_env(), CodexCli)

    def test_missing_configuration_falls_back_to_the_current_claude_cli(self):
        with patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True):
            self.assertIsInstance(model_from_env(), ClaudeCli)

    def test_explicit_configuration_takes_precedence_over_current_cli(self):
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "opaque", "CINE_TOASTER_MODEL": "claude-api"}, clear=True):
            self.assertIsInstance(model_from_env(), ClaudeApi)
            self.assertIsInstance(model_from_env("claude-cli"), ClaudeCli)

    def test_ambiguous_current_cli_requires_choice_but_explicit_choice_still_works(self):
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "opaque", "CLAUDECODE": "1"}, clear=True):
            with self.assertRaisesRegex(ModelUnavailable, "Ambiguous current CLI"):
                model_from_env()
            self.assertIsInstance(model_from_env("codex-cli"), CodexCli)

    def test_cli_installation_or_generic_environment_is_not_a_current_session(self):
        with patch.dict(os.environ, {"CODEX_HOME": "/codex", "CODEX_CI": "1", "CLAUDECODE": "0"}, clear=True), \
                patch("cine_toaster.agents.models.shutil.which", return_value="/installed-cli"):
            with self.assertRaisesRegex(ModelUnavailable, "no current CLI detected"):
                model_from_env()

    def test_invalid_explicit_choice_never_falls_back_to_current_cli(self):
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "opaque", "CINE_TOASTER_MODEL": "invalid"}, clear=True):
            with self.assertRaisesRegex(ModelUnavailable, "Unknown model adapter"):
                model_from_env()

    def test_host_selection_overrides_environment_without_changing_it(self):
        with patch.dict(os.environ, {"CINE_TOASTER_MODEL": "claude-api"}, clear=True):
            self.assertIsInstance(model_from_env("claude-cli"), ClaudeCli)
            self.assertEqual(os.environ["CINE_TOASTER_MODEL"], "claude-api")
            self.assertIsInstance(model_from_env(), ClaudeApi)

    def test_blank_or_unknown_selection_does_not_fall_back_to_environment(self):
        with patch.dict(os.environ, {"CINE_TOASTER_MODEL": "claude-cli"}, clear=True):
            for selection in ("", "  ", "not-an-adapter"):
                with self.subTest(selection=selection), self.assertRaises(ModelUnavailable):
                    model_from_env(selection)

    def test_provider_factory_does_not_require_a_claude_role_or_name(self):
        adapter = Mock(name="another-provider")
        factory = Mock(return_value=adapter)
        with patch("cine_toaster.agents.models.ADAPTERS", {"another-provider": factory}):
            self.assertIs(model_from_env("another-provider"), adapter)
        factory.assert_called_once_with()

    def test_host_injects_the_selected_adapter_into_the_existing_agent_server(self):
        agent_server = ModuleType("cine_toaster.agents.server")
        agent_server.serve_in_thread = Mock()
        adapter = Mock()
        with patch.dict(sys.modules, {agent_server.__name__: agent_server}), \
                patch("cine_toaster.agents.models.model_from_env", return_value=adapter) as factory, \
                patch("cine_toaster.assistant_host.threading.Thread") as thread:
            host = AssistantHost("http://runtime", 8788, 8789, provider="another-provider")
            host.start()
            factory.assert_called_once_with("another-provider")
            agent_server.serve_in_thread.assert_called_once_with("http://runtime", 8788, model=adapter)
            thread.return_value.start.assert_called_once_with()

    def test_preflight_checks_the_explicit_provider_and_reports_missing_selection(self):
        optional_modules = {name: ModuleType(name) for name in ("ag_ui_langgraph", "langgraph")}
        with patch.dict(sys.modules, optional_modules), \
                patch("cine_toaster.assistant_host.shutil.which", return_value="/node"), \
                patch("cine_toaster.assistant_host.BUNDLE") as bundle, \
                patch.dict(os.environ, {}, clear=True):
            bundle.is_file.return_value = True
            self.assertIn("No agent provider selected", unavailable_reason())
            with patch("cine_toaster.agents.models.ClaudeCli.available", return_value=""):
                self.assertEqual(unavailable_reason("claude-cli"), "")

    def test_cli_passes_selection_to_host_without_launching_a_provider(self):
        with patch("cine_toaster.cli._ensure_index"), patch("cine_toaster.cli.serve_project") as serve:
            result = main(["serve", "/film", "--assistant", "--agent-provider", "claude-api"])
        self.assertEqual(result, 0)
        serve.assert_called_once_with(Path("/film"), host="127.0.0.1", port=8787,
                                      assistant=True, agent_provider="claude-api")

    def test_cli_rejects_provider_without_assistant_before_indexing(self):
        errors = io.StringIO()
        with patch("cine_toaster.cli._ensure_index") as index, redirect_stderr(errors):
            result = main(["serve", "/film", "--agent-provider", "claude-cli"])
        self.assertEqual(result, 3)
        self.assertIn("--agent-provider requires --assistant", errors.getvalue())
        index.assert_not_called()


class CodexCliAdapterTests(unittest.TestCase):
    def test_structured_answer_uses_an_isolated_model_request_not_the_development_thread(self):
        seen = {}
        schema = {"type": "object", "properties": {
            "reply": {"type": "string"}, "optional": {"type": "string"}}, "required": ["reply"]}

        def run(command, **kwargs):
            seen.update(command=command, **kwargs)
            schema_file = Path(command[command.index("--output-schema") + 1])
            seen["schema"] = json.loads(schema_file.read_text())
            answer_file = Path(command[command.index("--output-last-message") + 1])
            answer_file.write_text('{"reply":"ok","optional":null}')
            return SimpleNamespace(returncode=0, stdout='{"type":"turn.completed","usage":{"output_tokens":12}}', stderr="")

        adapter = CodexCli(executable="codex-test", timeout=12)
        with patch.object(adapter, "available", return_value=""), \
                patch("cine_toaster.agents.models.subprocess.run", side_effect=run):
            self.assertEqual(adapter.ask("role instructions", "film context", schema), {"reply": "ok", "optional": None})
        command = seen["command"]
        for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check"):
            self.assertIn(flag, command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertIn("shell_tool", command)
        self.assertIn("plugins", command)
        self.assertIn("apps", command)
        self.assertNotIn("resume", command)
        self.assertNotIn("--last", command)
        self.assertIn('developer_instructions="role instructions"', command)
        self.assertIn("project_doc_max_bytes=0", command)
        self.assertEqual(seen["input"], "film context")
        self.assertEqual(seen["timeout"], 12)
        self.assertFalse(Path(seen["cwd"]).exists())  # disposable request files cleaned up
        self.assertEqual(seen["schema"]["required"], ["reply", "optional"])
        self.assertEqual(seen["schema"]["properties"]["optional"]["anyOf"][-1], {"type": "null"})
        self.assertFalse(seen["schema"]["additionalProperties"])
        self.assertEqual(adapter.last, {"usage": {"output_tokens": 12}})

    def test_failure_does_not_expose_raw_stderr_or_try_another_provider(self):
        adapter = CodexCli()
        with patch.object(adapter, "available", return_value=""), \
                patch("cine_toaster.agents.models.subprocess.run",
                      return_value=SimpleNamespace(returncode=1, stdout="", stderr="private-token")) as run:
            with self.assertRaises(ModelUnavailable) as caught:
                adapter.ask("role", "film", {"type": "object", "properties": {}})
        self.assertNotIn("private-token", str(caught.exception))
        self.assertEqual(run.call_count, 1)

    def test_timeout_is_a_visible_model_failure(self):
        adapter = CodexCli(timeout=1)
        with patch.object(adapter, "available", return_value=""), \
                patch("cine_toaster.agents.models.subprocess.run", side_effect=subprocess.TimeoutExpired("codex", 1)):
            with self.assertRaisesRegex(ModelUnavailable, "longer than 1 s"):
                adapter.ask("role", "film", {"type": "object", "properties": {}})

    def test_missing_or_invalid_structured_result_is_not_success(self):
        adapter = CodexCli()
        with patch.object(adapter, "available", return_value=""), \
                patch("cine_toaster.agents.models.subprocess.run",
                      return_value=SimpleNamespace(returncode=0, stdout="", stderr="")):
            with self.assertRaisesRegex(ModelUnavailable, "expected structured answer"):
                adapter.ask("role", "film", {"type": "object", "properties": {}})


if __name__ == "__main__":
    unittest.main()
