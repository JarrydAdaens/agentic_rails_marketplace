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

SERVER_PATH = Path(__file__).parents[1] / "mcp" / "advisor_server.py"
spec = importlib.util.spec_from_file_location("advisor_server", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(server)


def payload(**overrides):
    values = {
        "task": "Fix the gate",
        "stage": "planning",
        "approach": "Inspect then patch",
        "evidence": "hooks/advisor_gate.py exists",
        "question": "What should I prioritize?",
    }
    values.update(overrides)
    return values


class AdvisorServerTests(unittest.TestCase):
    def test_builtin_default_is_grok_46_high_at_standard_speed(self):
        self.assertEqual(server.BUILTIN_DEFAULT_MODEL, "cursor-grok-4.6-high")
        self.assertNotIn("fast", server.BUILTIN_DEFAULT_MODEL)

    def test_mcp_launcher_keeps_executor_workspace(self):
        config = json.loads((SERVER_PATH.parents[1] / ".mcp.json").read_text(encoding="utf-8"))
        launcher = config["mcpServers"]["cursor-as-advisor-guardrail"]
        self.assertNotIn("cwd", launcher)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", launcher["args"][0])

    def test_validation_requires_fields_and_accepts_optional_model(self):
        with self.assertRaisesRegex(ValueError, "question"):
            server.validate_arguments(payload(question=" "))
        with self.assertRaisesRegex(ValueError, "stage must be"):
            server.validate_arguments(payload(stage="other"))
        self.assertEqual(
            server.validate_arguments(payload(model=" composer-2.5 "))["model"],
            "composer-2.5",
        )
        with self.assertRaisesRegex(ValueError, "model must be"):
            server.validate_arguments(payload(model=" "))

    def test_prompt_has_contract_and_constructive_persona(self):
        prompt = server.build_prompt(payload())
        self.assertIn("TASK: Fix the gate", prompt)
        self.assertIn("PLAN/APPROACH: Inspect then patch", prompt)
        self.assertIn("at most 120 words", prompt)
        self.assertIn("constructive, candid, and practical", prompt)
        self.assertIn("plan, a course correction, or a completion verdict", prompt)
        self.assertIn("not to manufacture objections", prompt)
        self.assertNotIn("adversarial critic", prompt)

    def test_schema_describes_every_field_and_model_is_optional(self):
        properties = server.TOOL["inputSchema"]["properties"]
        for field in server.FIELDS + server.OPTIONAL_FIELDS:
            self.assertTrue(properties[field].get("description"), f"{field} needs a description")
        self.assertNotIn("model", server.TOOL["inputSchema"]["required"])
        self.assertEqual(server.TOOL["name"], "consult_advisor")

    def test_missing_project_config_uses_builtin_default(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(
                server.read_project_default(root),
                (server.BUILTIN_DEFAULT_MODEL, False),
            )
            self.assertFalse(server.config_path(root).exists())

    def test_project_default_is_written_in_plugin_harness_seam(self):
        with tempfile.TemporaryDirectory() as root:
            path = server.write_project_default("cursor-grok-4.5-low", root)
            expected = Path(root) / "harness" / "cursor-as-advisor-guardrail" / "config.json"
            self.assertEqual(path, expected)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["default_model"], "cursor-grok-4.5-low")
            self.assertEqual(server.read_project_default(root), ("cursor-grok-4.5-low", True))

    def test_project_config_preserves_unrelated_keys(self):
        with tempfile.TemporaryDirectory() as root:
            path = server.config_path(root)
            path.parent.mkdir(parents=True)
            path.write_text('{"note": "keep", "default_model": "auto"}\n', encoding="utf-8")
            server.write_project_default("composer-2.5", root)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"note": "keep", "default_model": "composer-2.5"},
            )

    def test_invalid_project_config_is_actionable(self):
        with tempfile.TemporaryDirectory() as root:
            path = server.config_path(root)
            path.parent.mkdir(parents=True)
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Could not read Cursor advisor config"):
                server.read_project_default(root)

    @patch.object(server.shutil, "which", return_value="agent")
    def test_command_uses_cursor_read_only_ask_mode(self, _which):
        command = server.command("composer-2.5")
        self.assertEqual(command, [
            "agent", "--print", "--output-format", "text", "--mode", "ask",
            "--sandbox", "disabled", "--trust", "--model", "composer-2.5",
        ])
        for forbidden in ("--force", "--yolo", "--auto-review"):
            self.assertNotIn(forbidden, command)

    @patch.object(server.shutil, "which", return_value=None)
    def test_missing_executable_is_actionable(self, _which):
        with self.assertRaisesRegex(RuntimeError, "not found on PATH"):
            server.command("composer-2.5")

    @patch.object(server, "command", side_effect=lambda model: ["agent", "--model", model])
    @patch.object(server.subprocess, "run")
    def test_consult_uses_model_and_remembers_only_after_success(self, run, _command):
        run.return_value = MagicMock(returncode=0, stdout="Keep the gate isolated.\n", stderr="")
        with tempfile.TemporaryDirectory() as root:
            result = server.consult(payload(model="cursor-grok-4.5-low"), workspace=root)
            self.assertEqual(result, "Keep the gate isolated.")
            self.assertEqual(run.call_args.args[0][2], "cursor-grok-4.5-low")
            self.assertEqual(Path(run.call_args.kwargs["cwd"]), Path(root))
            self.assertIn("TASK: Fix the gate", run.call_args.kwargs["input"])
            self.assertEqual(server.read_project_default(root)[0], "cursor-grok-4.5-low")

    @patch.object(server, "command", side_effect=lambda model: ["agent", "--model", model])
    @patch.object(server.subprocess, "run")
    def test_failed_model_change_does_not_poison_saved_default(self, run, _command):
        run.return_value = MagicMock(returncode=1, stdout="", stderr="model unavailable")
        with tempfile.TemporaryDirectory() as root:
            server.write_project_default("composer-2.5", root)
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                server.consult(payload(model="does-not-exist"), workspace=root)
            self.assertEqual(server.read_project_default(root)[0], "composer-2.5")

    def test_timeout_is_configurable(self):
        for value, expected in (
            ("900", 900),
            ("0", server.DEFAULT_TIMEOUT_SECONDS),
            ("soon", server.DEFAULT_TIMEOUT_SECONDS),
        ):
            with patch.dict(os.environ, {server.TIMEOUT_ENV_VAR: value}):
                self.assertEqual(server.timeout_seconds(), expected)

    @patch.object(server, "command", return_value=["agent"])
    @patch.object(server.subprocess, "run", side_effect=subprocess.TimeoutExpired("agent", 600, stderr="still reading"))
    def test_timeout_reports_limit_variable_and_partial_output(self, _run, _command):
        with tempfile.TemporaryDirectory() as root, self.assertRaises(RuntimeError) as caught:
            server.consult(payload(), workspace=root)
        message = str(caught.exception)
        self.assertIn("timed out after 600", message)
        self.assertIn(server.TIMEOUT_ENV_VAR, message)
        self.assertIn("still reading", message)

    def test_initialize_and_tool_errors_use_advisor_identity(self):
        initialized = server.dispatch({"id": 1, "method": "initialize"})
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "cursor-as-advisor-guardrail")
        bad = server.dispatch({
            "id": 2,
            "method": "tools/call",
            "params": {"name": "consult_advisor", "arguments": {}},
        })
        self.assertTrue(bad["result"]["isError"])


class StdioTransportTests(unittest.TestCase):
    def converse(self, *messages: dict) -> list[dict]:
        request = b"".join(json.dumps(message).encode("utf-8") + b"\n" for message in messages)
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
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "cursor-as-advisor-guardrail")
        self.assertEqual(replies[1]["result"]["tools"][0]["name"], "consult_advisor")
        self.assertEqual(replies[2]["result"], {})

    def test_non_ascii_payload_survives_transport(self):
        marker = "“advisor” — naïve caché, 2–3 per task 🚀"
        replies = self.converse({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "consult_advisor", "arguments": payload(stage=marker)},
        })
        self.assertTrue(replies[0]["result"]["isError"])
        self.assertIn(marker, replies[0]["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
