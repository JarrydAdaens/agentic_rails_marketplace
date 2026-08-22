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


class LocalAdvisorConfigPathTests(unittest.TestCase):
    def test_cursor_uses_a_host_specific_harness_config_filename(self):
        lib = Path(__file__).parents[1] / "lib"
        sys.path.insert(0, str(lib))
        from advisor_config import CONFIG_RELATIVE_PATH
        self.assertEqual(
            CONFIG_RELATIVE_PATH.as_posix(),
            "harness/local-advisor-guardrail/cursor-config.json",
        )


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

    def test_native_local_subagent_creates_marker(self):
        payloads = [
            {"session_id": "cursor", "tool_name": "Task", "tool_input": {"subagent_type": "local-advisor-cursor-grok-4.6"}},
        ]
        for payload in payloads:
            directory, marker = MagicMock(), MagicMock()
            with patch.object(advisor_marker, "marker_dir", return_value=directory), patch.object(advisor_marker, "marker_path", return_value=marker):
                self.invoke(advisor_marker, payload)
            directory.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            marker.touch.assert_called_once()

    def test_gate_uses_cursor_permission_shape(self):
        denied = json.loads(self.invoke(advisor_gate, {"conversation_id": "u", "hook_event_name": "preToolUse", "tool_name": "Write"}))
        self.assertEqual(denied["permission"], "deny")
        self.assertIn("native local-advisor", denied["agent_message"])
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

    def test_hook_manifest_covers_write_and_native_consult(self):
        cursor = json.loads((HOOKS / "cursor-hooks.json").read_text(encoding="utf-8"))
        pre = cursor["hooks"]["preToolUse"][0]
        for tool in ("Write", "StrReplace", "Delete"):
            self.assertIn(tool, pre["matcher"])
        self.assertFalse(pre["failClosed"])
        self.assertIn("postToolUse", cursor["hooks"])
        self.assertNotIn("afterMCPExecution", cursor["hooks"])

    def test_context_uses_cursor_additional_context_shape(self):
        with patch.object(advisor_context, "notify_guardrail_online") as toast:
            cursor = json.loads(self.invoke(advisor_context, {"hook_event_name": "sessionStart"}))
        toast.assert_called_once()
        self.assertIn("Advisor Protocol", cursor["additional_context"])

    def test_session_start_skips_toast_when_disabled(self):
        with tempfile.TemporaryDirectory() as root:
            harness = Path(root) / "harness" / "local-advisor-guardrail"
            harness.mkdir(parents=True)
            (harness / "cursor-config.json").write_text('{"enabled": false}\n', encoding="utf-8")
            with patch.object(advisor_context, "notify_guardrail_online") as toast:
                emitted = json.loads(self.invoke(advisor_context, {
                    "hook_event_name": "sessionStart",
                    "workspace_roots": [root],
                    "cwd": root,
                }))
        toast.assert_not_called()
        self.assertIn("disabled", emitted["additional_context"])


if __name__ == "__main__":
    unittest.main()
