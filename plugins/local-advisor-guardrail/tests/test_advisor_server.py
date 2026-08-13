from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SERVER_PATH = Path(__file__).parents[1] / "mcp" / "advisor_server.py"
spec = importlib.util.spec_from_file_location("portable_advisor_server", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(server)


def payload():
    return {"task": "Unify the advisor", "stage": "planning", "approach": "Port host adapters", "evidence": "Three plugin manifests", "question": "Is the boundary sound?"}


class AdvisorServerTests(unittest.TestCase):
    def test_all_host_manifests_use_local_plugin_identity(self):
        root = SERVER_PATH.parents[1]
        for manifest in (
            root / ".claude-plugin" / "plugin.json",
            root / ".codex-plugin" / "plugin.json",
            root / ".cursor-plugin" / "plugin.json",
        ):
            self.assertEqual(
                json.loads(manifest.read_text(encoding="utf-8"))["name"],
                "local-advisor-guardrail",
            )

    def test_manifests_select_same_server_with_host_argument(self):
        root = SERVER_PATH.parents[1]
        codex = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["local-advisor-guardrail"]
        cursor = json.loads((root / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["local-advisor-guardrail"]
        self.assertEqual(codex["args"][-2:], ["--host", "codex"])
        self.assertEqual(cursor["args"][-2:], ["--host", "cursor"])
        self.assertEqual(cursor["type"], "stdio")
        self.assertNotIn("cwd", cursor)
        self.assertEqual(cursor["command"], r"C:\Windows\System32\cmd.exe")
        self.assertEqual(cursor["args"][:3], ["/d", "/c", "call"])
        self.assertEqual(cursor["args"][3], "${PLUGIN_ROOT}/scripts/launch-windows.cmd")
        self.assertTrue(all(not arg.startswith("./") for arg in cursor["args"]))
        self.assertIn("${PLUGIN_ROOT}/mcp/advisor_server.py", cursor["args"])

    @patch.object(server, "resolve_cli", return_value=["codex"])
    def test_codex_is_sol_read_only_high_reasoning(self, _which):
        command = server.codex_command()
        self.assertIn("gpt-5.6-sol", command)
        self.assertIn("read-only", command)
        self.assertIn('model_reasoning_effort="high"', command)

    @patch.object(server, "resolve_cli", return_value=["agent"])
    def test_cursor_is_grok_high_in_ask_mode(self, _which):
        command = server.cursor_command("C:/repo")
        self.assertIn("cursor-grok-4.5-high", command)
        self.assertIn("ask", command)
        self.assertIn("C:/repo", command)

    def test_tools_advertise_host_specific_models(self):
        self.assertIn("gpt-5.6-sol", server.tool("codex")["description"])
        self.assertIn("cursor-grok-4.5-high", server.tool("cursor")["description"])
        self.assertNotIn("model", server.tool("codex")["inputSchema"]["properties"])
        self.assertIn("model", server.tool("cursor")["inputSchema"]["properties"])

    def test_cursor_model_is_configurable_per_project_without_changing_default(self):
        with tempfile.TemporaryDirectory() as workspace:
            selected, remember = server.select_cursor_model(payload(), workspace)
            self.assertEqual(selected, "cursor-grok-4.5-high")
            self.assertTrue(remember)
            server.write_project_default("cursor-grok-4.6-high", workspace)
            selected, remember = server.select_cursor_model(payload(), workspace)
            self.assertEqual(selected, "cursor-grok-4.6-high")
            self.assertFalse(remember)
            selected, remember = server.select_cursor_model(
                payload() | {"model": "cursor-grok-4.6-xhigh"}, workspace
            )
            self.assertEqual(selected, "cursor-grok-4.6-xhigh")
            self.assertTrue(remember)

    def test_cursor_workspace_env_overrides_plugin_launcher_cwd(self):
        with patch.dict(server.os.environ, {"AGENTIC_RAILS_WORKSPACE": "C:/consumer"}):
            self.assertEqual(server.project_root(), str(Path("C:/consumer").resolve()))

    @patch.object(server, "command", return_value=["agent"])
    @patch.object(server.subprocess, "run")
    def test_successful_cursor_consult_uses_and_remembers_requested_model(self, run, command):
        run.return_value = MagicMock(returncode=0, stdout="Use the smaller seam.\n", stderr="")
        with tempfile.TemporaryDirectory() as workspace:
            arguments = payload() | {"model": "cursor-grok-4.6-high"}
            self.assertEqual(
                server.consult("cursor", arguments, workspace),
                "Use the smaller seam.",
            )
            self.assertEqual(
                command.call_args.args,
                ("cursor", str(Path(workspace).resolve()), "cursor-grok-4.6-high"),
            )
            self.assertEqual(
                json.loads(server.config_path(workspace).read_text(encoding="utf-8"))["default_model"],
                "cursor-grok-4.6-high",
            )

    @patch.object(server, "command", return_value=["agent"])
    @patch.object(server.subprocess, "run")
    def test_failed_cursor_consult_does_not_remember_requested_model(self, run, _command):
        run.return_value = MagicMock(returncode=1, stdout="", stderr="model not available")
        with tempfile.TemporaryDirectory() as workspace:
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                server.consult(
                    "cursor",
                    payload() | {"model": "cursor-grok-future-high"},
                    workspace,
                )
            self.assertFalse(server.config_path(workspace).exists())

    def test_validation_and_dispatch(self):
        self.assertEqual(server.validate_arguments(payload())["stage"], "planning")
        with self.assertRaises(ValueError):
            server.validate_arguments({})
        initialized = server.dispatch("cursor", {"id": 1, "method": "initialize"})
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "local-advisor-guardrail")
        self.assertEqual(initialized["result"]["serverInfo"]["version"], "2.2.2")

    def test_server_becomes_gate_ready_only_after_cursor_lists_tools(self):
        with patch.dict(server.os.environ, {
            "AGENTIC_RAILS_MCP_HOST": "cursor",
            "AGENTIC_RAILS_WORKSPACE": "C:/repo",
        }), patch.object(server, "mark_server_ready") as ready:
            server.dispatch("cursor", {"id": 1, "method": "initialize"})
            ready.assert_not_called()
            listed = server.dispatch("cursor", {"id": 2, "method": "tools/list"})
        ready.assert_called_once_with(host="cursor", workspace="C:/repo")
        self.assertEqual(listed["result"]["tools"][0]["name"], "consult_advisor")


if __name__ == "__main__":
    unittest.main()
