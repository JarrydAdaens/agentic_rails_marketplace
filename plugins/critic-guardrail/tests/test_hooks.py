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
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS = Path(__file__).parents[1] / "hooks"
sys.path.insert(0, str(HOOKS))
import critic_cleanup
import critic_gate
import critic_marker
import critic_markers


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
        for tool in ("consult_critic", "mcp__critic-guardrail__consult_critic"):
            directory, marker = MagicMock(), MagicMock()
            with patch.object(critic_marker, "marker_dir", return_value=directory), patch.object(critic_marker, "marker_path", return_value=marker):
                self.invoke(critic_marker, {"session_id": "s1", "tool_name": tool})
            directory.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            marker.touch.assert_called_once()

    def test_other_tools_and_malformed_payload_do_not_mark(self):
        with patch.object(critic_marker, "marker_path") as marker:
            self.invoke(critic_marker, {"session_id": "no", "tool_name": "Task"})
            self.invoke(critic_marker, {"session_id": "no", "tool_name": "consult_critic_extra"})
            marker.assert_not_called()
        with patch.object(sys, "stdin", io.StringIO("{")):
            with self.assertRaises(SystemExit):
                critic_marker.main()

    def test_gate_denies_before_consult_and_allows_after(self):
        denied = self.invoke(critic_gate, {"session_id": "gate", "tool_name": "Edit"})
        decision = json.loads(denied)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("consult_critic", decision["permissionDecisionReason"])
        with patch.object(critic_gate, "has_marker", return_value=True):
            self.assertEqual(self.invoke(critic_gate, {"session_id": "gate", "tool_name": "Write"}), "")

    def test_cleanup_removes_stale_markers(self):
        directory, marker = MagicMock(), MagicMock()
        directory.is_dir.return_value = True
        directory.glob.return_value = [marker]
        marker.stat.return_value.st_mtime = 0
        with patch.object(critic_cleanup, "marker_dir", return_value=directory), patch.object(critic_cleanup.time, "time", return_value=critic_cleanup.MAX_AGE_SECONDS + 100):
            critic_cleanup.main()
        marker.unlink.assert_called_once()

    def test_marker_paths_are_plugin_specific(self):
        self.assertEqual(critic_markers.marker_dir().name, "critic-guardrail-markers")
        self.assertTrue(critic_markers.marker_path("abc").name.startswith("critic-consulted-"))

    def test_hooks_match_claude_write_and_critic_surfaces(self):
        config = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
        pre = config["hooks"]["PreToolUse"][0]["matcher"]
        post = config["hooks"]["PostToolUse"][0]["matcher"]
        self.assertIn("Write", pre)
        self.assertNotIn("apply_patch", pre)
        self.assertIn("consult_critic", post)
        self.assertNotIn("Task", post)


if __name__ == "__main__":
    unittest.main()
