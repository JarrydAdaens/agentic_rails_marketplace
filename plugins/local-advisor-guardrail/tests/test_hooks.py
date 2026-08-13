from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS = Path(__file__).parents[1] / "hooks"
sys.path.insert(0, str(HOOKS))
import advisor_cleanup
import advisor_context
import advisor_gate
import advisor_marker
import advisor_markers


class HookTests(unittest.TestCase):
    def invoke(self, module, payload):
        output = io.StringIO()
        error = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            try:
                module.main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        self.last_stderr = error.getvalue()
        return output.getvalue()

    def test_claude_subagent_and_mcp_tool_create_markers(self):
        payloads = [
            {"session_id": "claude", "tool_name": "Task", "tool_input": {"subagent_type": "local-advisor-guardrail:advisor"}},
            {"conversation_id": "cursor", "tool_name": "MCP:local-advisor-guardrail:consult_advisor", "tool_input": {}},
            {"session_id": "codex", "tool_name": "mcp__local-advisor-guardrail__consult_advisor", "tool_input": {}},
        ]
        for payload in payloads:
            directory, marker = MagicMock(), MagicMock()
            with patch.object(advisor_marker, "marker_dir", return_value=directory), patch.object(advisor_marker, "marker_path", return_value=marker):
                self.invoke(advisor_marker, payload)
            directory.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            marker.touch.assert_called_once()

    def test_gate_uses_native_host_response_shapes(self):
        claude = json.loads(self.invoke(advisor_gate, {"session_id": "c", "tool_name": "Edit"}))
        with patch.object(advisor_gate, "has_live_server", return_value=True):
            cursor = json.loads(self.invoke(advisor_gate, {"conversation_id": "u", "hook_event_name": "preToolUse", "tool_name": "Write"}))
        self.assertEqual(claude["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(cursor["permission"], "deny")
        self.assertIn("plugin-local-advisor-guardrail-local-advisor-guardrail", cursor["agent_message"])
        with patch.object(advisor_gate, "has_marker", return_value=True):
            self.assertEqual(self.invoke(advisor_gate, {"conversation_id": "u", "hook_event_name": "preToolUse"}), "")

    def test_cursor_gate_fails_open_when_mcp_tool_is_not_registered(self):
        with patch.object(advisor_gate, "has_live_server", return_value=False):
            decision = json.loads(self.invoke(advisor_gate, {
                "conversation_id": "missing-mcp",
                "hook_event_name": "preToolUse",
                "tool_name": "StrReplace",
            }))
        self.assertEqual(decision["permission"], "allow")
        self.assertIn("has not registered", decision["agent_message"])
        self.assertIn("/plugin", decision["agent_message"])
        self.assertIn("has not registered", self.last_stderr)

    def test_legacy_markers_unlock_gate(self):
        neutral = MagicMock()
        neutral.exists.return_value = False
        legacy_dirs = [MagicMock(), MagicMock()]
        legacy_dirs[0].__truediv__.return_value.exists.return_value = False
        legacy_dirs[1].__truediv__.return_value.exists.return_value = True
        with patch.object(advisor_markers, "marker_path", return_value=neutral), patch.object(advisor_markers, "legacy_marker_dirs", return_value=legacy_dirs):
            self.assertTrue(advisor_markers.has_marker("legacy"))

    def test_marker_directories_preserve_pre_rename_sessions(self):
        self.assertEqual(advisor_markers.marker_dir().name, "local-advisor-guardrail-markers")
        self.assertEqual(
            {path.name for path in advisor_markers.legacy_marker_dirs()},
            {
                "claude-advisor-markers",
                "advisor-guardrail-markers",
                "advisor-codex-guardrail-markers",
            },
        )

    def test_mcp_readiness_is_scoped_to_cursor_and_workspace(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            advisor_markers, "marker_dir", return_value=Path(temporary)
        ), patch.object(advisor_markers, "_process_is_running", return_value=True):
            advisor_markers.mark_server_ready("cursor", "C:/expected")
            self.assertTrue(advisor_markers.has_live_server("cursor", "C:/expected"))
            self.assertFalse(advisor_markers.has_live_server("codex", "C:/expected"))
            self.assertFalse(advisor_markers.has_live_server("cursor", "C:/other"))

    def test_cleanup_handles_neutral_and_both_legacy_directories(self):
        directories = [MagicMock(), MagicMock(), MagicMock()]
        for directory in directories:
            marker = MagicMock()
            directory.is_dir.return_value = True
            directory.glob.return_value = [marker]
            marker.stat.return_value.st_mtime = 0
        with patch.object(advisor_cleanup, "marker_dir", return_value=directories[0]), patch.object(advisor_cleanup, "legacy_marker_dirs", return_value=tuple(directories[1:])), patch.object(advisor_cleanup.time, "time", return_value=advisor_cleanup.MAX_AGE_SECONDS + 100):
            advisor_cleanup.main()
        for directory in directories:
            directory.glob.return_value[0].unlink.assert_called_once()

    def test_host_hook_manifests_cover_write_and_consult(self):
        claude = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
        cursor = json.loads((HOOKS / "cursor-hooks.json").read_text(encoding="utf-8"))
        self.assertIn("apply_patch", claude["hooks"]["PreToolUse"][0]["matcher"])
        self.assertIn("consult_advisor", claude["hooks"]["PostToolUse"][0]["matcher"])
        pre = cursor["hooks"]["preToolUse"][0]
        for tool in ("Write", "StrReplace", "Delete"):
            self.assertIn(tool, pre["matcher"])
        self.assertFalse(pre["failClosed"])
        self.assertIn("consult_advisor", cursor["hooks"]["afterMCPExecution"][0]["matcher"])
        self.assertNotIn("postToolUse", cursor["hooks"])

    def test_context_uses_cursor_additional_context_shape(self):
        cursor = json.loads(self.invoke(advisor_context, {"hook_event_name": "sessionStart"}))
        self.assertIn("Advisor Protocol", cursor["additional_context"])
        claude = self.invoke(advisor_context, {"hook_event_name": "SessionStart"})
        self.assertIn("Advisor Protocol", claude)


if __name__ == "__main__":
    unittest.main()
