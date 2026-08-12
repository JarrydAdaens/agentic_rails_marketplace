from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER_PATH = Path(__file__).parents[1] / "mcp" / "advisor_server.py"
spec = importlib.util.spec_from_file_location("portable_advisor_server", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(server)


def payload():
    return {"task": "Unify the advisor", "stage": "planning", "approach": "Port host adapters", "evidence": "Three plugin manifests", "question": "Is the boundary sound?"}


class AdvisorServerTests(unittest.TestCase):
    def test_manifests_select_same_server_with_host_argument(self):
        root = SERVER_PATH.parents[1]
        codex = json.loads((root / ".codex-mcp.json").read_text(encoding="utf-8"))["mcpServers"]["advisor-guardrail"]
        cursor = json.loads((root / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["advisor-guardrail"]
        self.assertEqual(codex["args"][-2:], ["--host", "codex"])
        self.assertEqual(cursor["args"][-2:], ["--host", "cursor"])

    @patch.object(server.shutil, "which", return_value="codex")
    def test_codex_is_sol_read_only_high_reasoning(self, _which):
        command = server.codex_command()
        self.assertIn("gpt-5.6-sol", command)
        self.assertIn("read-only", command)
        self.assertIn('model_reasoning_effort="high"', command)

    @patch.object(server.shutil, "which", return_value="agent")
    def test_cursor_is_grok_high_in_ask_mode(self, _which):
        command = server.cursor_command("C:/repo")
        self.assertIn("cursor-grok-4.5-high", command)
        self.assertIn("ask", command)
        self.assertIn("C:/repo", command)

    def test_tools_advertise_host_specific_models(self):
        self.assertIn("gpt-5.6-sol", server.tool("codex")["description"])
        self.assertIn("cursor-grok-4.5-high", server.tool("cursor")["description"])

    def test_validation_and_dispatch(self):
        self.assertEqual(server.validate_arguments(payload())["stage"], "planning")
        with self.assertRaises(ValueError):
            server.validate_arguments({})
        initialized = server.dispatch("cursor", {"id": 1, "method": "initialize"})
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "advisor-guardrail")


if __name__ == "__main__":
    unittest.main()
