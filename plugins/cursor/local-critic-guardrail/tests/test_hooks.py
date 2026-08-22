from __future__ import annotations
import contextlib, io, json, sys, unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parents[1]
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))
import critic_gate, critic_marker, critic_markers

class LocalCriticTests(unittest.TestCase):
    def invoke(self, module, payload):
        out = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(out): module.main()
        return out.getvalue()

    def test_cursor_config_path_is_host_specific(self):
        sys.path.insert(0, str(ROOT / "lib"))
        from critic_config import CONFIG_RELATIVE_PATH
        self.assertEqual(CONFIG_RELATIVE_PATH.as_posix(), "harness/local-critic-guardrail/cursor-config.json")

    def test_native_critic_task_marks_session_consulted(self):
        directory, marker = MagicMock(), MagicMock()
        with patch.object(critic_marker, "marker_dir", return_value=directory), patch.object(critic_marker, "marker_path", return_value=marker):
            self.invoke(critic_marker, {"session_id": "s", "tool_name": "Task", "tool_input": {"subagent_type": "local-critic-auto"}})
        directory.mkdir.assert_called_once_with(parents=True, exist_ok=True); marker.touch.assert_called_once()

    def test_unrelated_subagent_does_not_mark_session(self):
        with patch.object(critic_marker, "marker_path") as marker:
            self.invoke(critic_marker, {"session_id": "s", "tool_name": "Task", "tool_input": {"subagent_type": "local-advisor-auto"}})
        marker.assert_not_called()

    def test_first_write_is_denied_until_consulted(self):
        payload = {"conversation_id": "s", "tool_name": "Write", "hook_event_name": "preToolUse"}
        with patch.object(critic_gate, "has_marker", return_value=False):
            denied = json.loads(self.invoke(critic_gate, payload))
        self.assertEqual(denied["permission"], "deny"); self.assertIn("local-critic", denied["agent_message"])
        with patch.object(critic_gate, "has_marker", return_value=True): self.assertEqual(self.invoke(critic_gate, payload), "")

    def test_disabled_config_allows_write(self):
        sys.path.insert(0, str(ROOT / "lib"))
        from critic_config import CriticConfig
        with patch.object(critic_gate, "load_critic_config", return_value=CriticConfig(enabled=False)):
            self.assertEqual(self.invoke(critic_gate, {"tool_name": "Write"}), "")

    def test_manifest_uses_native_post_tool_marker(self):
        hooks = json.loads((HOOKS / "cursor-hooks.json").read_text(encoding="utf-8"))["hooks"]
        self.assertIn("postToolUse", hooks); self.assertNotIn("afterMCPExecution", hooks)
        self.assertIn("Write", hooks["preToolUse"][0]["matcher"])

if __name__ == "__main__": unittest.main()
