from __future__ import annotations

import contextlib
import io
import json
import sys
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
        with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(output):
            try:
                module.main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        return output.getvalue()

    def test_claude_subagent_and_mcp_tool_create_markers(self):
        payloads = [
            {"session_id": "claude", "tool_name": "Task", "tool_input": {"subagent_type": "advisor-guardrail:advisor"}},
            {"conversation_id": "cursor", "tool_name": "MCP:advisor-guardrail:consult_advisor", "tool_input": {}},
            {"session_id": "codex", "tool_name": "mcp__advisor-guardrail__consult_advisor", "tool_input": {}},
        ]
        for payload in payloads:
            directory, marker = MagicMock(), MagicMock()
            with patch.object(advisor_marker, "marker_dir", return_value=directory), patch.object(advisor_marker, "marker_path", return_value=marker):
                self.invoke(advisor_marker, payload)
            directory.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            marker.touch.assert_called_once()

    def test_gate_uses_native_host_response_shapes(self):
        claude = json.loads(self.invoke(advisor_gate, {"session_id": "c", "tool_name": "Edit"}))
        cursor = json.loads(self.invoke(advisor_gate, {"conversation_id": "u", "hook_event_name": "preToolUse", "tool_name": "Write"}))
        self.assertEqual(claude["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(cursor["permission"], "deny")
        with patch.object(advisor_gate, "has_marker", return_value=True):
            self.assertEqual(self.invoke(advisor_gate, {"conversation_id": "u", "hook_event_name": "preToolUse"}), "")

    def test_legacy_markers_unlock_gate(self):
        neutral = MagicMock()
        neutral.exists.return_value = False
        legacy_dirs = [MagicMock(), MagicMock()]
        legacy_dirs[0].__truediv__.return_value.exists.return_value = False
        legacy_dirs[1].__truediv__.return_value.exists.return_value = True
        with patch.object(advisor_markers, "marker_path", return_value=neutral), patch.object(advisor_markers, "legacy_marker_dirs", return_value=legacy_dirs):
            self.assertTrue(advisor_markers.has_marker("legacy"))

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
        self.assertEqual(cursor["hooks"]["preToolUse"][0]["matcher"], "Write")
        self.assertIn("consult_advisor", cursor["hooks"]["postToolUse"][0]["matcher"])

    def test_context_uses_cursor_additional_context_shape(self):
        cursor = json.loads(self.invoke(advisor_context, {"hook_event_name": "sessionStart"}))
        self.assertIn("Advisor Protocol", cursor["additional_context"])
        claude = self.invoke(advisor_context, {"hook_event_name": "SessionStart"})
        self.assertIn("Advisor Protocol", claude)


if __name__ == "__main__":
    unittest.main()
