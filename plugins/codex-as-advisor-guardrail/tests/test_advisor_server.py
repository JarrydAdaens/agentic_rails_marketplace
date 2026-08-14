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

PLUGIN = Path(__file__).parents[1]
LIB = PLUGIN / "lib"
sys.path.insert(0, str(LIB))

import advisor_consult as consult_mod  # noqa: E402
import advisor_config  # noqa: E402

SERVER_PATH = PLUGIN / "mcp" / "advisor_server.py"
spec = importlib.util.spec_from_file_location("advisor_server", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(server)


def payload(**overrides):
    values = {
        "task": "Fix the gate", "stage": "planning", "approach": "Inspect then patch",
        "evidence": "hooks/advisor_gate.py exists", "question": "Is this safe?",
    }
    values.update(overrides)
    return values


class AdvisorServerTests(unittest.TestCase):
    def test_mcp_launcher_keeps_executor_workspace(self):
        config = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
        launcher = config["mcpServers"]["codex-as-advisor-guardrail"]
        self.assertNotIn("cwd", launcher)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", launcher["args"][0])

    def test_cursor_plugin_has_no_mcp_packaging(self):
        cursor = json.loads((PLUGIN / ".cursor-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertNotIn("mcpServers", cursor)
        self.assertFalse((PLUGIN / "mcp.json").exists())

    def test_validation_requires_all_nonempty_fields(self):
        with self.assertRaisesRegex(ValueError, "question"):
            server.validate_arguments(payload(question=" "))
        with self.assertRaisesRegex(ValueError, "stage must be"):
            server.validate_arguments(payload(stage="other"))

    def test_prompt_has_contract_and_constructive_persona(self):
        prompt = server.build_prompt(payload())
        self.assertIn("TASK: Fix the gate", prompt)
        self.assertIn("senior reviewer", prompt)
        self.assertIn("constructive", prompt)
        self.assertIn("course correction", prompt)
        self.assertNotIn("adversarial", prompt)

    def test_every_schema_field_is_described_for_the_caller(self):
        properties = server.TOOL["inputSchema"]["properties"]
        for field in server.FIELDS:
            self.assertTrue(properties[field].get("description"), f"{field} needs a description")

    @patch.object(consult_mod, "resolve_cli", return_value=["codex"])
    def test_command_uses_config_model_effort_and_optional_fast(self, _which):
        cfg = advisor_config.AdvisorConfig(model="gpt-5.6-sol", effort="high", fast=False)
        self.assertEqual(consult_mod.command(cfg), [
            "codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox",
            "read-only", "--model", "gpt-5.6-sol", "-c", 'model_reasoning_effort="high"', "-",
        ])
        fast = advisor_config.AdvisorConfig(model="gpt-5.4-mini", effort="low", fast=True)
        argv = consult_mod.command(fast)
        self.assertIn('service_tier="fast"', argv)
        self.assertIn("gpt-5.4-mini", argv)

    @patch.object(consult_mod, "resolve_cli", return_value=["codex"])
    def test_command_runs_outside_git_repositories(self, _which):
        self.assertIn("--skip-git-repo-check", consult_mod.command())

    @patch.object(consult_mod, "command", return_value=["codex"])
    @patch.object(consult_mod.subprocess, "run")
    def test_consult_propagates_workspace_and_returns_output(self, run, _command):
        run.return_value = MagicMock(returncode=0, stdout="The plan misses the lock.\n", stderr="")
        with patch.object(consult_mod, "require_advisor_config", return_value=advisor_config.AdvisorConfig()):
            self.assertEqual(
                consult_mod.consult(payload(), workspace="C:/repo"),
                "The plan misses the lock.",
            )
        self.assertEqual(run.call_args.kwargs["cwd"], "C:/repo")
        self.assertEqual(run.call_args.kwargs["timeout"], consult_mod.DEFAULT_TIMEOUT_SECONDS)

    def test_timeout_default_is_raised(self):
        self.assertEqual(consult_mod.DEFAULT_TIMEOUT_SECONDS, 1800)

    def test_timeout_is_configurable_and_ignores_junk(self):
        for value, expected in (("900", 900), ("0", consult_mod.DEFAULT_TIMEOUT_SECONDS), ("soon", consult_mod.DEFAULT_TIMEOUT_SECONDS)):
            with patch.dict(os.environ, {consult_mod.TIMEOUT_ENV_VAR: value}):
                self.assertEqual(consult_mod.timeout_seconds(), expected)

    @patch.object(consult_mod, "command", return_value=["codex"])
    @patch.object(consult_mod.subprocess, "run", side_effect=subprocess.TimeoutExpired("codex", 1800, stderr="thinking hard"))
    def test_timeout_is_actionable_and_reports_partial_output(self, _run, _command):
        with patch.object(consult_mod, "require_advisor_config", return_value=advisor_config.AdvisorConfig()):
            with self.assertRaises(RuntimeError) as caught:
                consult_mod.consult(payload())
        message = str(caught.exception)
        self.assertIn("timed out after 1800", message)
        self.assertIn(consult_mod.TIMEOUT_ENV_VAR, message)
        self.assertIn("thinking hard", message)

    def test_auth_and_model_failures_are_classified(self):
        self.assertIn("sign in", consult_mod.classify_failure("Not logged in", "gpt-5.6-sol"))
        self.assertIn("gpt-5.6-sol", consult_mod.classify_failure("model not available", "gpt-5.6-sol"))
        self.assertIn("quota", consult_mod.classify_failure("usage limit exceeded", "gpt-5.6-sol").lower())

    def test_harness_config_defaults_and_load(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(advisor_config.load_advisor_config(root).model, "gpt-5.6-sol")
            path = advisor_config.config_path(root)
            path.parent.mkdir(parents=True)
            path.write_text(
                advisor_config.DEFAULT_CONFIG_TEMPLATE.replace(
                    '"consult_timeout_seconds": 1800',
                    '"consult_timeout_seconds": 900',
                ).replace(
                    '"health_timeout_seconds": 90',
                    '"health_timeout_seconds": 45',
                ).replace(
                    '"model": "gpt-5.6-sol"',
                    '"model": "gpt-5.4-mini"',
                ).replace(
                    '"effort": "high"',
                    '"effort": "low"',
                ).replace(
                    '"fast": false',
                    '"fast": true',
                ),
                encoding="utf-8",
            )
            loaded = advisor_config.load_advisor_config(root)
            self.assertEqual(loaded.model, "gpt-5.4-mini")
            self.assertEqual(loaded.effort, "low")
            self.assertTrue(loaded.fast)
            self.assertEqual(loaded.consult_timeout_seconds, 900)
            self.assertEqual(loaded.health_timeout_seconds, 45)
            self.assertEqual(loaded.source, "harness")

    def test_jsonc_comments_are_stripped(self):
        with tempfile.TemporaryDirectory() as root:
            path = advisor_config.write_default_config(root)
            loaded = advisor_config.load_advisor_config(root)
            self.assertEqual(loaded.model, "gpt-5.6-sol")
            self.assertEqual(loaded.consult_timeout_seconds, 1800)
            text = path.read_text(encoding="utf-8")
            self.assertIn("// Codex model id", text)

    def test_env_timeout_overrides_config(self):
        cfg = advisor_config.AdvisorConfig(consult_timeout_seconds=900, health_timeout_seconds=45)
        with patch.dict(os.environ, {advisor_config.CONSULT_TIMEOUT_ENV_VAR: "1200"}):
            self.assertEqual(advisor_config.resolve_consult_timeout(cfg), 1200)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(advisor_config.CONSULT_TIMEOUT_ENV_VAR, None)
            self.assertEqual(advisor_config.resolve_consult_timeout(cfg), 900)
    def test_initialize_reports_plugin_server_name(self):
        result = server.dispatch({"id": 1, "method": "initialize"})
        self.assertEqual(result["result"]["serverInfo"]["name"], "codex-as-advisor-guardrail")
        self.assertEqual(result["result"]["serverInfo"]["version"], "1.1.0")

    def test_ping_answers_with_an_empty_result(self):
        self.assertEqual(server.dispatch({"id": 7, "method": "ping"}), {"jsonrpc": "2.0", "id": 7, "result": {}})

    def test_notifications_are_never_answered(self):
        self.assertIsNone(server.dispatch({"method": "notifications/initialized"}))

    def test_dispatch_returns_tool_error_for_bad_payload(self):
        result = server.dispatch({"id": 1, "method": "tools/call", "params": {"name": "consult_advisor", "arguments": {}}})
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
        self.assertEqual([r["id"] for r in replies], [1, 2, 3])
        self.assertEqual(replies[1]["result"]["tools"][0]["name"], "consult_advisor")

    def test_non_ascii_payload_survives_the_transport_intact(self):
        marker = "“critic” — naïve caché, 2–3 per task 🚀"
        replies = self.converse({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "consult_advisor", "arguments": payload(stage=marker)},
        })
        self.assertTrue(replies[0]["result"]["isError"])
        self.assertIn(marker, replies[0]["result"]["content"][0]["text"])

    def test_garbage_input_draws_a_parse_error_and_the_server_continues(self):
        completed = subprocess.run(
            [sys.executable, str(SERVER_PATH)],
            input=b"not json at all\n\n\xff\xfe invalid utf-8\n" + json.dumps(
                {"jsonrpc": "2.0", "id": 9, "method": "ping"}).encode("utf-8") + b"\n",
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        replies = [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines() if line.strip()]
        self.assertTrue(any(r.get("error", {}).get("code") == -32700 for r in replies))
        self.assertTrue(any(r.get("id") == 9 and r.get("result") == {} for r in replies))


if __name__ == "__main__":
    unittest.main()
