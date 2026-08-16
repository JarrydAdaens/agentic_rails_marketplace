# Copyright 2026 Jarryd Adaens
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SERVER_PATH = Path(__file__).parents[1] / "mcp" / "critic_server.py"
spec = importlib.util.spec_from_file_location("critic_server", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(server)


def payload(**overrides):
    values = {
        "task": "Fix the gate", "stage": "planning", "approach": "Inspect then patch",
        "evidence": "hooks/critic_gate.py exists", "question": "Is this safe?",
    }
    values.update(overrides)
    return values


class CriticServerTests(unittest.TestCase):
    def test_builtin_default_is_grok_46_high_at_standard_speed(self):
        self.assertEqual(server.BUILTIN_DEFAULT_MODEL, "cursor-grok-4.6-high")
        self.assertNotIn("fast", server.BUILTIN_DEFAULT_MODEL)

    def test_validation_requires_fields_and_accepts_optional_model(self):
        with self.assertRaisesRegex(ValueError, "question"):
            server.validate_arguments(payload(question=" "))
        with self.assertRaisesRegex(ValueError, "stage must be"):
            server.validate_arguments(payload(stage="other"))
        self.assertEqual(server.validate_arguments(payload(model=" composer-2.5 "))["model"], "composer-2.5")
        with self.assertRaisesRegex(ValueError, "model must be"):
            server.validate_arguments(payload(model=" "))

    def test_prompt_has_contract_and_adversarial_persona(self):
        prompt = server.build_prompt(payload())
        self.assertIn("TASK: Fix the gate", prompt)
        self.assertIn("PLAN/APPROACH: Inspect then patch", prompt)
        self.assertIn("at most 120 words", prompt)
        self.assertIn("adversarial critic", prompt)
        self.assertIn("Do not implement or modify files", prompt)

    def test_every_schema_field_is_described_and_model_is_optional(self):
        properties = server.TOOL["inputSchema"]["properties"]
        for field in server.FIELDS + server.OPTIONAL_FIELDS:
            self.assertTrue(properties[field].get("description"), f"{field} needs a description")
        self.assertNotIn("model", server.TOOL["inputSchema"]["required"])

    def test_missing_project_config_uses_builtin_default(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(server.read_project_default(root), ("cursor-grok-4.6-high", False))
            self.assertFalse(server.config_path(root).exists())

    def test_project_default_is_written_in_the_harness_seam(self):
        with tempfile.TemporaryDirectory() as root:
            path = server.write_project_default("cursor-grok-4.5-low", root)
            self.assertEqual(path, Path(root) / "harness" / "cursor-as-critic-guardrail" / "config.json")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["default_model"], "cursor-grok-4.5-low")
            self.assertEqual(server.read_project_default(root), ("cursor-grok-4.5-low", True))

    def test_project_defaults_are_isolated(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            server.write_project_default("composer-2.5", first)
            server.write_project_default("claude-fable-5-thinking-high", second)
            self.assertEqual(server.read_project_default(first)[0], "composer-2.5")
            self.assertEqual(server.read_project_default(second)[0], "claude-fable-5-thinking-high")

    def test_project_config_preserves_unrelated_keys(self):
        with tempfile.TemporaryDirectory() as root:
            path = server.config_path(root)
            path.parent.mkdir(parents=True)
            path.write_text('{"note": "keep", "default_model": "auto"}\n', encoding="utf-8")
            server.write_project_default("composer-2.5", root)
            config = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(config, {"note": "keep", "default_model": "composer-2.5"})

    def test_invalid_project_config_is_actionable(self):
        with tempfile.TemporaryDirectory() as root:
            path = server.config_path(root)
            path.parent.mkdir(parents=True)
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Could not read Cursor critic config"):
                server.read_project_default(root)

    @patch.object(server, "resolve_cli", return_value=["agent"])
    def test_command_uses_cursor_read_only_ask_mode_and_selected_model(self, _which):
        self.assertEqual(server.command("composer-2.5"), [
            "agent", "--print", "--output-format", "text", "--mode", "ask",
            "--sandbox", "disabled", "--trust", "--model", "composer-2.5",
        ])
        self.assertNotIn("--force", server.command("composer-2.5"))

    @patch.object(server, "resolve_cli", side_effect=RuntimeError("Agent executable was not found after restoring PATH"))
    def test_missing_executable_is_actionable(self, _which):
        with self.assertRaisesRegex(RuntimeError, "not found after restoring PATH"):
            server.command("composer-2.5")

    @patch.object(server, "command", side_effect=lambda model: ["agent", "--model", model])
    @patch.object(server.subprocess, "run")
    def test_consult_uses_requested_model_and_remembers_it_after_success(self, run, _command):
        run.return_value = MagicMock(returncode=0, stdout="The plan misses the lock.\n", stderr="")
        with tempfile.TemporaryDirectory() as root:
            result = server.consult(payload(model="claude-fable-5-thinking-high"), workspace=root)
            self.assertEqual(result, "The plan misses the lock.")
            self.assertEqual(run.call_args.args[0][2], "claude-fable-5-thinking-high")
            self.assertEqual(Path(run.call_args.kwargs["cwd"]), Path(root))
            self.assertIn("TASK: Fix the gate", run.call_args.kwargs["input"])
            self.assertEqual(run.call_args.kwargs["errors"], "strict")
            self.assertEqual(server.read_project_default(root)[0], "claude-fable-5-thinking-high")

    @patch.object(server, "command", side_effect=lambda model: ["agent", "--model", model])
    @patch.object(server.subprocess, "run")
    def test_consult_reuses_saved_project_model(self, run, _command):
        run.return_value = MagicMock(returncode=0, stdout="Critique", stderr="")
        with tempfile.TemporaryDirectory() as root:
            server.write_project_default("cursor-grok-4.5-low", root)
            server.consult(payload(), workspace=root)
            self.assertEqual(run.call_args.args[0][2], "cursor-grok-4.5-low")

    @patch.object(server, "command", side_effect=lambda model: ["agent", "--model", model])
    @patch.object(server.subprocess, "run")
    def test_builtin_default_is_remembered_after_first_success(self, run, _command):
        run.return_value = MagicMock(returncode=0, stdout="Critique", stderr="")
        with tempfile.TemporaryDirectory() as root:
            server.consult(payload(), workspace=root)
            self.assertEqual(server.read_project_default(root), (server.BUILTIN_DEFAULT_MODEL, True))

    @patch.object(server, "command", side_effect=lambda model: ["agent", "--model", model])
    @patch.object(server.subprocess, "run")
    def test_failed_model_change_does_not_poison_saved_default(self, run, _command):
        run.return_value = MagicMock(returncode=1, stdout="", stderr="model unavailable")
        with tempfile.TemporaryDirectory() as root:
            server.write_project_default("composer-2.5", root)
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                server.consult(payload(model="does-not-exist"), workspace=root)
            self.assertEqual(server.read_project_default(root)[0], "composer-2.5")

    def test_timeout_is_configurable_and_ignores_junk(self):
        for value, expected in (("900", 900), ("0", server.DEFAULT_TIMEOUT_SECONDS), ("soon", server.DEFAULT_TIMEOUT_SECONDS)):
            with patch.dict(os.environ, {server.TIMEOUT_ENV_VAR: value}):
                self.assertEqual(server.timeout_seconds(), expected)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(server.timeout_seconds(), server.DEFAULT_TIMEOUT_SECONDS)

    @patch.object(server, "command", return_value=["agent"])
    @patch.object(server.subprocess, "run", side_effect=subprocess.TimeoutExpired("agent", 600, stderr="thinking hard"))
    def test_timeout_is_actionable_and_reports_partial_output(self, _run, _command):
        with tempfile.TemporaryDirectory() as root, self.assertRaises(RuntimeError) as caught:
            server.consult(payload(), workspace=root)
        message = str(caught.exception)
        self.assertIn("timed out after 600", message)
        self.assertIn(server.TIMEOUT_ENV_VAR, message)
        self.assertIn("thinking hard", message)

    def test_auth_and_model_failures_are_classified(self):
        self.assertIn("agent login", server.classify_failure("Not logged in", "composer-2.5"))
        self.assertIn("composer-2.5", server.classify_failure("model not available", "composer-2.5"))

    def test_initialize_reports_plugin_server_name(self):
        result = server.dispatch({"id": 1, "method": "initialize"})
        self.assertEqual(result["result"]["serverInfo"]["name"], "cursor-as-critic-guardrail")

    def test_initialize_echoes_a_supported_protocol_version(self):
        agreed = server.dispatch({"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(agreed["result"]["protocolVersion"], "2024-11-05")
        unknown = server.dispatch({"id": 1, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})
        self.assertEqual(unknown["result"]["protocolVersion"], server.SUPPORTED_PROTOCOL_VERSIONS[0])

    def test_ping_answers_with_an_empty_result(self):
        self.assertEqual(server.dispatch({"id": 7, "method": "ping"}), {"jsonrpc": "2.0", "id": 7, "result": {}})

    def test_notifications_are_never_answered(self):
        for method in ("notifications/initialized", "notifications/cancelled", "notifications/anything"):
            self.assertIsNone(server.dispatch({"method": method}))

    def test_dispatch_returns_tool_error_for_bad_payload(self):
        result = server.dispatch({"id": 1, "method": "tools/call", "params": {"name": "consult_critic", "arguments": {}}})
        self.assertTrue(result["result"]["isError"])


class StdioTransportTests(unittest.TestCase):
    def converse(self, *messages: dict) -> list[dict]:
        request = b"".join(json.dumps(m, ensure_ascii=False).encode("utf-8") + b"\n" for m in messages)
        completed = subprocess.run(
            [sys.executable, str(SERVER_PATH)], input=request,
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        return [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines() if line.strip()]

    def test_handshake_over_real_stdio(self):
        replies = self.converse(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"},
        )
        self.assertEqual([reply["id"] for reply in replies], [1, 2, 3])
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "cursor-as-critic-guardrail")
        self.assertEqual(replies[1]["result"]["tools"][0]["name"], "consult_critic")
        self.assertEqual(replies[2]["result"], {})

    def test_non_ascii_payload_survives_the_transport_intact(self):
        marker = "“critic” — naïve caché, 2–3 per task 🚀"
        replies = self.converse({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "consult_critic", "arguments": payload(stage=marker)},
        })
        self.assertTrue(replies[0]["result"]["isError"])
        self.assertIn(marker, replies[0]["result"]["content"][0]["text"])

    def test_garbage_input_draws_parse_errors_and_server_continues(self):
        completed = subprocess.run(
            [sys.executable, str(SERVER_PATH)],
            input=b"not json at all\n\xff\xfe invalid utf-8\n" + json.dumps(
                {"jsonrpc": "2.0", "id": 9, "method": "ping"}).encode("utf-8") + b"\n",
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        replies = [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines() if line.strip()]
        self.assertTrue(any(reply.get("error", {}).get("code") == -32700 for reply in replies))
        self.assertTrue(any(reply.get("id") == 9 and reply.get("result") == {} for reply in replies))


if __name__ == "__main__":
    unittest.main()
