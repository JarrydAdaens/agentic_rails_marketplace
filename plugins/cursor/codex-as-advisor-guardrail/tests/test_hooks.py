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
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PLUGIN = Path(__file__).parents[1]
HOOKS = PLUGIN / "hooks"
sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(PLUGIN / "lib"))

import advisor_cleanup
import advisor_context
import advisor_gate
import advisor_marker
import advisor_markers
import advisor_session


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

    def test_shell_consult_marks_on_success(self):
        with patch.object(advisor_marker, "mark_consulted") as consulted, patch.object(advisor_marker, "mark_online"), patch.object(advisor_marker, "read_health", return_value={}):
            self.invoke(advisor_marker, {
                "session_id": "shell",
                "hook_event_name": "afterShellExecution",
                "command": "uv run --no-project python ./scripts/launch.py ./cli/consult_advisor.py",
                "exit_code": 0,
                "output": "Looks fine",
            })
        consulted.assert_called_once_with("shell")

    def test_other_tools_and_malformed_payload_do_not_mark(self):
        with patch.object(advisor_marker, "mark_consulted") as consulted:
            self.invoke(advisor_marker, {"session_id": "no", "tool_name": "Task"})
            self.invoke(advisor_marker, {"session_id": "no", "tool_name": "consult_advisor_extra"})
            consulted.assert_not_called()

    def test_gate_allows_when_offline_or_pending(self):
        payload = {
            "conversation_id": "cursor-gate",
            "hook_event_name": "preToolUse",
            "tool_name": "StrReplace",
        }
        with patch.object(advisor_gate, "has_marker", return_value=False), patch.object(advisor_gate, "health_state", return_value="offline"), patch.object(advisor_gate, "offline_reason", return_value="no credits"):
            allowed = json.loads(self.invoke(advisor_gate, payload))
        self.assertEqual(allowed["permission"], "allow")
        self.assertIn("offline", allowed["agent_message"].lower())
        with patch.object(advisor_gate, "has_marker", return_value=False), patch.object(advisor_gate, "health_state", return_value="pending"):
            pending = json.loads(self.invoke(advisor_gate, payload))
        self.assertEqual(pending["permission"], "allow")

    def test_gate_denies_when_online(self):
        payload = {
            "conversation_id": "cursor-gate",
            "hook_event_name": "preToolUse",
            "tool_name": "StrReplace",
        }
        with patch.object(advisor_gate, "has_marker", return_value=False), patch.object(advisor_gate, "health_state", return_value="online"):
            denied = json.loads(self.invoke(advisor_gate, payload))
        self.assertEqual(denied["permission"], "deny")
        self.assertIn("consult_advisor.py", denied["agent_message"])

    def test_cleanup_removes_stale_markers(self):
        directory, marker = MagicMock(), MagicMock()
        directory.is_dir.return_value = True
        directory.glob.return_value = [marker]
        marker.stat.return_value.st_mtime = 0
        with patch.object(advisor_cleanup, "marker_dir", return_value=directory), patch.object(advisor_cleanup.time, "time", return_value=advisor_cleanup.MAX_AGE_SECONDS + 100):
            advisor_cleanup.main()
        marker.unlink.assert_called()

    def test_marker_paths_are_plugin_specific(self):
        self.assertEqual(advisor_markers.marker_dir().name, "codex-as-advisor-guardrail-markers")
        self.assertTrue(advisor_markers.marker_path("abc").name.startswith("advisor-consulted-"))

    def test_health_markers_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(advisor_session, "marker_dir", return_value=Path(temporary)):
            advisor_session.mark_pending("s")
            self.assertEqual(advisor_session.health_state("s"), "pending")
            advisor_session.mark_online("s", model="gpt-5.6-sol", effort="high", fast=False)
            self.assertEqual(advisor_session.health_state("s"), "online")
            advisor_session.mark_offline("s", "quota", model="gpt-5.6-sol", effort="high", fast=False)
            self.assertEqual(advisor_session.health_state("s"), "offline")
            self.assertIn("quota", advisor_session.offline_reason("s"))

    def test_former_marker_directories_are_still_swept(self):
        legacy = [directory.name for directory in advisor_markers.legacy_marker_dirs()]
        self.assertIn("advisor-guardrail-markers", legacy)

    def test_session_start_injects_the_protocol_as_utf8(self):
        plugin_root = HOOKS.parent
        launcher = (
            "import os,sys,runpy; d=os.path.join(os.environ['CLAUDE_PLUGIN_ROOT'],'hooks'); "
            "sys.path.insert(0,d); runpy.run_path(os.path.join(d,'advisor_context.py'),run_name='__main__')"
        )
        completed = subprocess.run(
            [sys.executable, "-c", launcher],
            env={
                **os.environ,
                "CLAUDE_PLUGIN_ROOT": str(plugin_root),
                "CODEX_ADVISOR_SKIP_HEALTH": "1",
                "AGENTIC_RAILS_SKIP_TOAST": "1",
            },
            input=b"{}",
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        emitted = completed.stdout.decode("utf-8")
        self.assertIn("Advisor Protocol", emitted)
        self.assertIn("target 2–3 per task", emitted)
        self.assertIn("Codex-as-advisor", emitted)
        self.assertNotIn("�", emitted)

    def test_cursor_hooks_are_portable_cli_not_mcp(self):
        config = json.loads((HOOKS / "cursor-hooks.json").read_text(encoding="utf-8"))
        pre = config["hooks"]["preToolUse"][0]
        for tool in ("Write", "StrReplace", "Delete"):
            self.assertIn(tool, pre["matcher"])
        self.assertFalse(pre["failClosed"])
        self.assertIn("afterShellExecution", config["hooks"])
        self.assertIn("consult_advisor", config["hooks"]["afterShellExecution"][0]["matcher"])
        self.assertNotIn("afterMCPExecution", config["hooks"])
        joined = json.dumps(config)
        self.assertNotIn("cmd.exe", joined)
        self.assertNotIn("launch-windows.cmd", joined)
        self.assertIn("launch.py", joined)

    def test_health_skill_is_user_invoked(self):
        skill = (PLUGIN / "skills" / "codex-advisor-health" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("disable-model-invocation: true", skill)
        self.assertIn("Result: ONLINE | OFFLINE", skill)

    def test_init_and_help_skills_exist(self):
        init = (PLUGIN / "skills" / "codex-advisor-init" / "SKILL.md").read_text(encoding="utf-8")
        help_text = (PLUGIN / "skills" / "codex-advisor-help" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("disable-model-invocation: true", init)
        self.assertIn("advisor_init.py", init)
        self.assertIn("disable-model-invocation: true", help_text)
        self.assertIn("preToolUse", help_text)
        self.assertIn("afterShellExecution", help_text)
        self.assertIn("sessionStart", help_text)

    def test_advisor_init_writes_commented_config(self):
        init_path = PLUGIN / "cli" / "advisor_init.py"
        with tempfile.TemporaryDirectory() as root:
            completed = subprocess.run(
                [sys.executable, str(init_path), "--workspace", root],
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Path:", completed.stdout)
            config = Path(root) / "harness" / "codex-as-advisor-guardrail" / "cursor-config.json"
            self.assertTrue(config.is_file())
            self.assertIn("//", config.read_text(encoding="utf-8"))
            again = subprocess.run(
                [sys.executable, str(init_path), "--workspace", root],
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(again.returncode, 1)

    def test_user_hook_lifecycle_skills_and_commands_exist(self):
        install = PLUGIN / "cli" / "advisor_install_hooks.py"
        remove = PLUGIN / "cli" / "advisor_remove_hooks.py"
        for path in (install, remove, PLUGIN / "lib" / "user_hooks.py"):
            self.assertTrue(path.is_file(), path)
        for name in ("codex-advisor-install-hooks", "codex-advisor-remove-hooks"):
            skill = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("disable-model-invocation: true", skill)
            self.assertIn("hooks.json", skill)
        with tempfile.TemporaryDirectory(dir=PLUGIN) as root:
            hooks_file = Path(root) / "hooks.json"
            first = subprocess.run([sys.executable, str(install), "--hooks-file", str(hooks_file)], capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            once = json.loads(hooks_file.read_text(encoding="utf-8"))
            second = subprocess.run([sys.executable, str(install), "--hooks-file", str(hooks_file)], capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(hooks_file.read_text(encoding="utf-8")), once)
            removed = subprocess.run([sys.executable, str(remove), "--hooks-file", str(hooks_file)], capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertEqual(json.loads(hooks_file.read_text(encoding="utf-8"))["hooks"], {})


class OnlineToastTests(unittest.TestCase):
    def invoke(self, payload):
        output = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), contextlib.redirect_stdout(output):
            try:
                advisor_context.main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        return output.getvalue()

    def test_session_start_toasts_when_enabled(self):
        with patch.object(advisor_context, "notify_guardrail_online") as toast, patch.object(
            advisor_context, "run_health_probe"
        ) as probe:
            probe.return_value.status_block.return_value = "status"
            self.invoke({"hook_event_name": "sessionStart", "session_id": "s"})
        toast.assert_called_once()

    def test_session_start_skips_toast_when_disabled(self):
        with tempfile.TemporaryDirectory() as root:
            harness = Path(root) / "harness" / "codex-as-advisor-guardrail"
            harness.mkdir(parents=True)
            (harness / "cursor-config.json").write_text('{"enabled": false}\n', encoding="utf-8")
            with patch.object(advisor_context, "notify_guardrail_online") as toast:
                self.invoke({
                    "hook_event_name": "sessionStart",
                    "workspace_roots": [root],
                    "cwd": root,
                })
        toast.assert_not_called()


if __name__ == "__main__":
    unittest.main()
