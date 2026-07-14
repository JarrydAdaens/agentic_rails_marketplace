from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS = Path(__file__).parents[1] / "hooks"
sys.path.insert(0, str(HOOKS))
import advisor_cleanup
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

    def test_claude_task_and_agent_create_marker(self):
        for tool in ("Task", "Agent"):
            session = tool.lower()
            directory, marker = MagicMock(), MagicMock()
            with patch.object(advisor_marker, "marker_dir", return_value=directory), patch.object(advisor_marker, "marker_path", return_value=marker):
                self.invoke(advisor_marker, {"session_id": session, "tool_name": tool, "tool_input": {"subagent_type": "advisor-guardrail:advisor"}})
            directory.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            marker.touch.assert_called_once()

    def test_non_advisor_and_malformed_payload_do_not_mark(self):
        self.invoke(advisor_marker, {"session_id": "no", "tool_name": "Task", "tool_input": {"subagent_type": "worker"}})
        with patch.object(advisor_marker, "marker_path") as marker:
            self.invoke(advisor_marker, {"session_id": "no", "tool_name": "Task", "tool_input": {"subagent_type": "worker"}})
            marker.assert_not_called()
        with patch.object(sys, "stdin", io.StringIO("{")):
            with self.assertRaises(SystemExit):
                advisor_marker.main()

    def test_gate_denies_before_consult_and_allows_after(self):
        denied = self.invoke(advisor_gate, {"session_id": "gate", "tool_name": "Edit"})
        self.assertEqual(json.loads(denied)["hookSpecificOutput"]["permissionDecision"], "deny")
        with patch.object(advisor_gate, "has_marker", return_value=True):
            self.assertEqual(self.invoke(advisor_gate, {"session_id": "gate", "tool_name": "Write"}), "")

    def test_legacy_marker_unlocks_gate(self):
        with patch.object(advisor_markers, "marker_path") as neutral, patch.object(advisor_markers, "legacy_marker_path") as legacy:
            neutral.return_value.exists.return_value = False
            legacy.return_value.exists.return_value = True
            self.assertTrue(advisor_markers.has_marker("legacy"))

    def test_cleanup_removes_stale_neutral_and_legacy_markers(self):
        directories = [MagicMock(), MagicMock()]
        markers = [MagicMock(), MagicMock()]
        for directory, marker in zip(directories, markers):
            directory.is_dir.return_value = True
            directory.glob.return_value = [marker]
            marker.stat.return_value.st_mtime = 0
        with patch.object(advisor_cleanup, "marker_dir", return_value=directories[0]), patch.object(advisor_cleanup, "legacy_marker_dir", return_value=directories[1]), patch.object(advisor_cleanup.time, "time", return_value=advisor_cleanup.MAX_AGE_SECONDS + 100):
            advisor_cleanup.main()
        for marker in markers:
            marker.unlink.assert_called_once()

    def test_hooks_match_claude_write_and_advisor_surfaces(self):
        config = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
        pre = config["hooks"]["PreToolUse"][0]["matcher"]
        post = config["hooks"]["PostToolUse"][0]["matcher"]
        self.assertIn("Write", pre)
        self.assertNotIn("apply_patch", pre)
        self.assertIn("Task", post)
        self.assertNotIn("consult_advisor", post)


if __name__ == "__main__":
    unittest.main()
