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
    def test_mcp_launcher_keeps_executor_workspace(self):
        config = json.loads((SERVER_PATH.parents[1] / ".mcp.json").read_text(encoding="utf-8"))
        launcher = config["mcpServers"]["codex-as-critic-guardrail"]
        self.assertNotIn("cwd", launcher)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", launcher["args"][0])

    def test_cursor_launcher_is_plugin_rooted_and_windows_safe(self):
        config = json.loads((SERVER_PATH.parents[1] / "mcp.json").read_text(encoding="utf-8"))
        launcher = config["mcpServers"]["codex-as-critic-guardrail"]
        self.assertEqual(launcher["type"], "stdio")
        self.assertEqual(launcher["cwd"], "${PLUGIN_ROOT}")
        self.assertEqual(launcher["command"], r"C:\Windows\System32\cmd.exe")
        self.assertEqual(launcher["args"][:3], ["/d", "/c", "call"])
        self.assertEqual(launcher["args"][3], "${PLUGIN_ROOT}/scripts/launch-uv.cmd")
        self.assertIn("${PLUGIN_ROOT}/mcp/critic_server.py", launcher["args"])
        self.assertTrue(all(not arg.startswith("./") for arg in launcher["args"]))

    def test_validation_requires_all_nonempty_fields(self):
        with self.assertRaisesRegex(ValueError, "question"):
            server.validate_arguments(payload(question=" "))
        with self.assertRaisesRegex(ValueError, "stage must be"):
            server.validate_arguments(payload(stage="other"))

    def test_prompt_has_contract_and_adversarial_persona(self):
        prompt = server.build_prompt(payload())
        self.assertIn("TASK: Fix the gate", prompt)
        self.assertIn("PLAN/APPROACH: Inspect then patch", prompt)
        self.assertIn("at most 120 words", prompt)
        self.assertIn("adversarial critic", prompt)
        self.assertIn("Do not implement or modify files", prompt)

    def test_every_schema_field_is_described_for_the_caller(self):
        properties = server.TOOL["inputSchema"]["properties"]
        for field in server.FIELDS:
            self.assertTrue(properties[field].get("description"), f"{field} needs a description")

    @patch.object(server.shutil, "which", return_value="codex")
    def test_command_is_fixed_read_only_high_reasoning(self, _which):
        self.assertEqual(server.command(), [
            "codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox",
            "read-only", "--model", "gpt-5.6-sol", "-c", 'model_reasoning_effort="high"', "-",
        ])

    @patch.object(server.shutil, "which", return_value="codex")
    def test_command_runs_outside_git_repositories(self, _which):
        # Without this flag Codex refuses to start in a non-git workspace, which
        # made the critic unusable in whole projects.
        self.assertIn("--skip-git-repo-check", server.command())

    @patch.object(server.shutil, "which", return_value=None)
    def test_missing_executable_is_actionable(self, _which):
        with self.assertRaisesRegex(RuntimeError, "not found on PATH"):
            server.command()

    @patch.object(server, "command", return_value=["codex"])
    @patch.object(server.subprocess, "run")
    def test_consult_propagates_workspace_and_returns_output(self, run, _command):
        run.return_value = MagicMock(returncode=0, stdout="The plan misses the lock.\n", stderr="")
        self.assertEqual(server.consult(payload(), workspace="C:/repo"), "The plan misses the lock.")
        self.assertEqual(run.call_args.kwargs["cwd"], "C:/repo")
        self.assertEqual(run.call_args.kwargs["timeout"], server.DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertIn("TASK: Fix the gate", run.call_args.kwargs["input"])

    @patch.object(server, "command", return_value=["codex"])
    @patch.object(server.subprocess, "run")
    def test_cursor_workspace_env_overrides_plugin_launcher_cwd(self, run, _command):
        run.return_value = MagicMock(returncode=0, stdout="Critique\n", stderr="")
        with patch.dict(server.os.environ, {"AGENTIC_RAILS_WORKSPACE": "C:/consumer"}):
            server.consult(payload())
        self.assertEqual(run.call_args.kwargs["cwd"], "C:/consumer")

    def test_timeout_default_clears_observed_consult_latency(self):
        # Real consults measured a p90 of 132s and a longest success of 178s, so
        # the cap has to sit well clear of the distribution, not inside it.
        self.assertGreaterEqual(server.DEFAULT_TIMEOUT_SECONDS, 300)

    def test_timeout_is_configurable_and_ignores_junk(self):
        for value, expected in (("900", 900), ("0", server.DEFAULT_TIMEOUT_SECONDS), ("soon", server.DEFAULT_TIMEOUT_SECONDS)):
            with patch.dict(os.environ, {server.TIMEOUT_ENV_VAR: value}):
                self.assertEqual(server.timeout_seconds(), expected)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(server.timeout_seconds(), server.DEFAULT_TIMEOUT_SECONDS)

    @patch.object(server, "command", return_value=["codex"])
    @patch.object(server.subprocess, "run", side_effect=subprocess.TimeoutExpired("codex", 600, stderr="thinking hard"))
    def test_timeout_is_actionable_and_reports_partial_output(self, _run, _command):
        with self.assertRaises(RuntimeError) as caught:
            server.consult(payload())
        message = str(caught.exception)
        self.assertIn("timed out after 600", message)
        self.assertIn(server.TIMEOUT_ENV_VAR, message)
        self.assertIn("thinking hard", message)

    def test_auth_and_model_failures_are_classified(self):
        self.assertIn("sign in", server.classify_failure("Not logged in"))
        self.assertIn("gpt-5.6-sol", server.classify_failure("model not available"))

    def test_initialize_reports_plugin_server_name(self):
        result = server.dispatch({"id": 1, "method": "initialize"})
        self.assertEqual(result["result"]["serverInfo"]["name"], "codex-as-critic-guardrail")
        self.assertEqual(result["result"]["serverInfo"]["version"], "1.1.0")

    def test_server_becomes_gate_ready_only_after_cursor_lists_tools(self):
        with patch.dict(server.os.environ, {
            "AGENTIC_RAILS_MCP_HOST": "cursor",
            "AGENTIC_RAILS_WORKSPACE": "C:/repo",
        }), patch.object(server, "mark_server_ready") as ready:
            server.dispatch({"id": 1, "method": "initialize"})
            ready.assert_not_called()
            listed = server.dispatch({"id": 2, "method": "tools/list"})
        ready.assert_called_once_with(host="cursor", workspace="C:/repo")
        self.assertEqual(listed["result"]["tools"][0]["name"], "consult_critic")

    def test_initialize_echoes_a_supported_protocol_version(self):
        agreed = server.dispatch({"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(agreed["result"]["protocolVersion"], "2024-11-05")
        unknown = server.dispatch({"id": 1, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})
        self.assertEqual(unknown["result"]["protocolVersion"], server.SUPPORTED_PROTOCOL_VERSIONS[0])

    def test_ping_answers_with_an_empty_result(self):
        # The spec requires a result here; answering -32601 is a protocol violation.
        self.assertEqual(server.dispatch({"id": 7, "method": "ping"}), {"jsonrpc": "2.0", "id": 7, "result": {}})

    def test_notifications_are_never_answered(self):
        for method in ("notifications/initialized", "notifications/cancelled", "notifications/anything"):
            self.assertIsNone(server.dispatch({"method": method}))

    def test_dispatch_returns_tool_error_for_bad_payload(self):
        result = server.dispatch({"id": 1, "method": "tools/call", "params": {"name": "consult_critic", "arguments": {}}})
        self.assertTrue(result["result"]["isError"])


class StdioTransportTests(unittest.TestCase):
    """End-to-end checks against a real server process.

    The unit tests above all call dispatch() directly, so they never exercised
    main(). The defects that reached users -- cp1252 stdio on Windows and a
    crash-prone read loop -- lived exactly there.
    """

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
        self.assertEqual([r["id"] for r in replies], [1, 2, 3])  # the notification drew no reply
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(replies[1]["result"]["tools"][0]["name"], "consult_critic")
        self.assertEqual(replies[2]["result"], {})

    def test_non_ascii_payload_survives_the_transport_intact(self):
        # Windows pipes default to cp1252, which silently mangled every curly
        # quote, dash, and emoji on its way to the critic.
        marker = "“critic” — naïve caché, 2–3 per task 🚀"
        replies = self.converse({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "consult_critic", "arguments": payload(stage=marker)},
        })
        # An invalid stage is rejected before Codex is ever launched, so the test
        # stays hermetic -- and the rejection echoes the received value, which
        # proves the text survived the transport character for character.
        self.assertTrue(replies[0]["result"]["isError"])
        self.assertIn(marker, replies[0]["result"]["content"][0]["text"])

    def test_malformed_and_blank_lines_do_not_kill_the_server(self):
        # A dead server leaves an in-flight call hanging until the client's own
        # idle timeout, which is what "it kept timing out" looks like from outside.
        replies = self.converse(
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
            {"jsonrpc": "2.0", "id": 2, "method": "no/such/method"},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"},
        )
        self.assertEqual(replies[0]["result"], {})
        self.assertEqual(replies[1]["error"]["code"], -32601)
        self.assertEqual(replies[2]["result"], {})

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
