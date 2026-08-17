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

import contextlib
import io
import json
import os
import subprocess
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

    def test_plain_and_mcp_namespaced_consult_create_marker(self):
        tools = ("consult_advisor", "mcp__cursor-as-advisor-guardrail__consult_advisor")
        for tool in tools:
            directory, marker = MagicMock(), MagicMock()
            with patch.object(advisor_marker, "marker_dir", return_value=directory), patch.object(advisor_marker, "marker_path", return_value=marker):
                self.invoke(advisor_marker, {"session_id": "s1", "tool_name": tool})
            directory.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            marker.touch.assert_called_once()

    def test_similar_and_unrelated_tools_do_not_mark(self):
        with patch.object(advisor_marker, "marker_path") as marker:
            self.invoke(advisor_marker, {"session_id": "no", "tool_name": "Task"})
            self.invoke(advisor_marker, {"session_id": "no", "tool_name": "consult_advisor_extra"})
            self.invoke(advisor_marker, {"session_id": "no", "tool_name": "consult_critic"})
            marker.assert_not_called()

    def test_malformed_payload_fails_open(self):
        with patch.object(sys, "stdin", io.StringIO("{")):
            with self.assertRaises(SystemExit):
                advisor_marker.main()
        with patch.object(sys, "stdin", io.StringIO("{")):
            with self.assertRaises(SystemExit):
                advisor_gate.main()

    def test_gate_denies_before_consult_and_allows_after(self):
        payload = {"conversation_id": "gate", "hook_event_name": "preToolUse", "tool_name": "Edit"}
        with patch.object(advisor_gate, "has_live_server", return_value=True):
            denied = json.loads(self.invoke(advisor_gate, payload))
        self.assertEqual(denied["permission"], "deny")
        self.assertIn("consult_advisor", denied["agent_message"])
        with patch.object(advisor_gate, "has_marker", return_value=True):
            self.assertEqual(self.invoke(advisor_gate, payload), "")

    def test_cleanup_removes_stale_markers(self):
        directory, marker = MagicMock(), MagicMock()
        directory.is_dir.return_value = True
        directory.glob.return_value = [marker]
        marker.stat.return_value.st_mtime = 0
        with patch.object(advisor_cleanup, "marker_dir", return_value=directory), patch.object(advisor_cleanup.time, "time", return_value=advisor_cleanup.MAX_AGE_SECONDS + 100):
            advisor_cleanup.main()
        marker.unlink.assert_called_once()

    def test_marker_paths_are_plugin_specific(self):
        self.assertEqual(advisor_markers.marker_dir().name, "cursor-as-advisor-guardrail-markers")
        self.assertTrue(advisor_markers.marker_path("abc").name.startswith("advisor-consulted-"))
        self.assertEqual(advisor_markers.legacy_marker_dirs(), [])

    def test_session_start_injects_protocol_as_utf8(self):
        plugin_root = HOOKS.parent
        launcher = (
            "import os,sys,runpy; d=os.path.join(os.environ['CLAUDE_PLUGIN_ROOT'],'hooks'); "
            "sys.path.insert(0,d); runpy.run_path(os.path.join(d,'advisor_context.py'),run_name='__main__')"
        )
        completed = subprocess.run(
            [sys.executable, "-c", launcher],
            env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(plugin_root)},
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        emitted = completed.stdout.decode("utf-8")
        self.assertIn("Cursor Advisor Protocol", emitted)
        self.assertIn("Target 2–3 consultations per task", emitted)
        self.assertNotIn("�", emitted)

    def test_cursor_hooks_match_write_and_consult_surfaces(self):
        config = json.loads((HOOKS / "cursor-hooks.json").read_text(encoding="utf-8"))
        pre = config["hooks"]["preToolUse"][0]
        for tool in ("Write", "StrReplace", "Delete"):
            self.assertIn(tool, pre["matcher"])
        self.assertFalse(pre["failClosed"])
        self.assertIn("consult_advisor", config["hooks"]["afterMCPExecution"][0]["matcher"])
        self.assertNotIn("consult_critic", config["hooks"]["afterMCPExecution"][0]["matcher"])


if __name__ == "__main__":
    unittest.main()
