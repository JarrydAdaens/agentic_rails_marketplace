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
import subprocess
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
        launcher = config["mcpServers"]["critic-guardrail"]
        self.assertNotIn("cwd", launcher)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", launcher["args"][0])

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

    @patch.object(server.shutil, "which", return_value="codex")
    def test_command_is_fixed_read_only_high_reasoning(self, _which):
        self.assertEqual(server.command(), [
            "codex", "exec", "--ephemeral", "--sandbox", "read-only", "--model",
            "gpt-5.6-sol", "-c", 'model_reasoning_effort="high"', "-",
        ])

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
        self.assertEqual(run.call_args.kwargs["timeout"], server.TIMEOUT_SECONDS)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertIn("TASK: Fix the gate", run.call_args.kwargs["input"])

    @patch.object(server, "command", return_value=["codex"])
    @patch.object(server.subprocess, "run", side_effect=subprocess.TimeoutExpired("codex", 180))
    def test_timeout_is_actionable(self, _run, _command):
        with self.assertRaisesRegex(RuntimeError, "timed out after 180"):
            server.consult(payload())

    def test_auth_and_model_failures_are_classified(self):
        self.assertIn("sign in", server.classify_failure("Not logged in"))
        self.assertIn("gpt-5.6-sol", server.classify_failure("model not available"))

    def test_initialize_reports_plugin_server_name(self):
        result = server.dispatch({"id": 1, "method": "initialize"})
        self.assertEqual(result["result"]["serverInfo"]["name"], "critic-guardrail")

    def test_dispatch_returns_tool_error_for_bad_payload(self):
        result = server.dispatch({"id": 1, "method": "tools/call", "params": {"name": "consult_critic", "arguments": {}}})
        self.assertTrue(result["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
