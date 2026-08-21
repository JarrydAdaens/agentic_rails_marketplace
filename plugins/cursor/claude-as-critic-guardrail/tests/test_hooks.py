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
from unittest.mock import patch

PLUGIN = Path(__file__).parents[1]
HOOKS = PLUGIN / "hooks"
sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(PLUGIN / "lib"))

import critic_config
import critic_gate
import critic_marker
import critic_markers
import critic_session

GATE_PAYLOAD = {
    "conversation_id": "cursor-gate",
    "hook_event_name": "preToolUse",
    "tool_name": "StrReplace",
}


class HookTests(unittest.TestCase):
    def invoke(self, module, payload, *, raw: str | None = None):
        text = raw if raw is not None else json.dumps(payload)
        output = io.StringIO()
        error = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO(text)), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            try:
                module.main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        self.last_stderr = error.getvalue()
        return output.getvalue()

    def test_gate_allows_when_pending_or_offline(self):
        with patch.object(critic_gate, "has_marker", return_value=False), patch.object(critic_gate, "health_state", return_value="pending"):
            pending = json.loads(self.invoke(critic_gate, GATE_PAYLOAD))
        self.assertEqual(pending["permission"], "allow")

        with patch.object(critic_gate, "has_marker", return_value=False), patch.object(critic_gate, "health_state", return_value="offline"), patch.object(critic_gate, "offline_reason", return_value="no credits"):
            offline = json.loads(self.invoke(critic_gate, GATE_PAYLOAD))
        self.assertEqual(offline["permission"], "allow")
        self.assertIn("offline", offline["agent_message"].lower())

    def test_gate_denies_when_online_and_unconsulted(self):
        with patch.object(critic_gate, "has_marker", return_value=False), patch.object(critic_gate, "health_state", return_value="online"):
            denied = json.loads(self.invoke(critic_gate, GATE_PAYLOAD))
        self.assertEqual(denied["permission"], "deny")
        self.assertIn("consult_critic.py", denied["agent_message"])

    def test_gate_still_denies_a_bom_prefixed_payload(self):
        # The Cursor Windows CLI prefixes hook stdin with a UTF-8 BOM; a gate
        # that cannot parse its payload fails open, which silently disabled
        # every write gate in this repository once already.
        with patch.object(critic_gate, "has_marker", return_value=False), patch.object(critic_gate, "health_state", return_value="online"):
            denied = json.loads(self.invoke(critic_gate, None, raw="﻿" + json.dumps(GATE_PAYLOAD)))
        self.assertEqual(denied["permission"], "deny")

    def test_shell_consult_marks_the_session_consulted(self):
        with patch.object(critic_marker, "mark_consulted") as consulted, patch.object(critic_marker, "mark_online"), patch.object(critic_marker, "read_health", return_value={}):
            self.invoke(critic_marker, {
                "session_id": "shell",
                "hook_event_name": "afterShellExecution",
                "command": "uv run --no-project python ./scripts/launch.py ./cli/consult_critic.py",
                "exit_code": 0,
                "output": "Looks fine",
            })
        consulted.assert_called_once_with("shell")

    def test_failed_or_unrelated_commands_do_not_mark(self):
        with patch.object(critic_marker, "mark_consulted") as consulted:
            self.invoke(critic_marker, {"session_id": "no", "command": "git status", "exit_code": 0})
            self.invoke(critic_marker, {
                "session_id": "no",
                "command": "./cli/consult_critic.py",
                "exit_code": 1,
            })
        consulted.assert_not_called()

    def test_marker_paths_are_plugin_specific(self):
        self.assertEqual(critic_markers.marker_dir().name, "claude-as-critic-guardrail-markers")
        self.assertTrue(critic_markers.marker_path("abc").name.startswith("critic-consulted-"))

    def test_health_markers_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(critic_session, "marker_dir", return_value=Path(temporary)):
            self.assertEqual(critic_session.health_state("s"), "pending")
            critic_session.mark_online("s", model="opus", effort="high")
            self.assertEqual(critic_session.health_state("s"), "online")
            critic_session.mark_offline("s", "quota", model="opus", effort="high")
            self.assertEqual(critic_session.health_state("s"), "offline")
            self.assertIn("quota", critic_session.offline_reason("s"))


class ConfigTests(unittest.TestCase):
    def test_missing_config_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as root:
            config = critic_config.load_critic_config(root)
        self.assertEqual(config.source, "defaults")
        self.assertEqual(config.model, "opus")
        self.assertIsNone(config.error)

    def test_jsonc_comments_are_stripped_and_fields_validated(self):
        with tempfile.TemporaryDirectory() as root:
            path = critic_config.write_default_config(root)
            self.assertIn("//", path.read_text(encoding="utf-8"))
            self.assertEqual(critic_config.load_critic_config(root).source, "harness")

            path.write_text('{"effort": "turbo"}', encoding="utf-8")
            broken = critic_config.load_critic_config(root)
            self.assertEqual(broken.source, "error")
            self.assertIn("effort", broken.error)
            with self.assertRaises(RuntimeError):
                critic_config.require_critic_config(root)


class SurfaceTests(unittest.TestCase):
    """The user-facing surfaces the skills and hooks promise actually exist."""

    def test_cursor_hooks_are_portable_cli_not_mcp(self):
        config = json.loads((HOOKS / "cursor-hooks.json").read_text(encoding="utf-8"))
        pre = config["hooks"]["preToolUse"][0]
        for tool in ("Write", "StrReplace", "Delete"):
            self.assertIn(tool, pre["matcher"])
        self.assertFalse(pre["failClosed"])
        self.assertIn("consult_critic", config["hooks"]["afterShellExecution"][0]["matcher"])
        self.assertNotIn("afterMCPExecution", config["hooks"])
        joined = json.dumps(config)
        self.assertNotIn("launch-windows.cmd", joined)
        self.assertIn("launch.py", joined)

    def test_skills_are_user_invoked_and_name_their_cli(self):
        health = (PLUGIN / "skills" / "claude-critic-health" / "SKILL.md").read_text(encoding="utf-8")
        init = (PLUGIN / "skills" / "claude-critic-init" / "SKILL.md").read_text(encoding="utf-8")
        help_text = (PLUGIN / "skills" / "claude-critic-help" / "SKILL.md").read_text(encoding="utf-8")
        for skill in (health, init, help_text):
            self.assertIn("disable-model-invocation: true", skill)
        self.assertIn("Result: ONLINE | OFFLINE", health)
        self.assertIn("critic_health.py", health)
        self.assertIn("critic_init.py", init)
        for hook in ("preToolUse", "afterShellExecution", "sessionStart"):
            self.assertIn(hook, help_text)

    def test_critic_init_writes_a_config_and_refuses_to_clobber_it(self):
        init_path = PLUGIN / "cli" / "critic_init.py"
        with tempfile.TemporaryDirectory() as root:
            completed = subprocess.run(
                [sys.executable, str(init_path), "--workspace", root],
                capture_output=True, text=True, timeout=60, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Path:", completed.stdout)
            config = Path(root) / "harness" / "claude-as-critic-guardrail" / "config.json"
            self.assertTrue(config.is_file())

            again = subprocess.run(
                [sys.executable, str(init_path), "--workspace", root],
                capture_output=True, text=True, timeout=60, check=False,
            )
            self.assertEqual(again.returncode, 1)

    def test_critic_health_cli_reports_online_when_the_probe_is_skipped(self):
        health_path = PLUGIN / "cli" / "critic_health.py"
        with tempfile.TemporaryDirectory() as root:
            completed = subprocess.run(
                [sys.executable, str(health_path), "--session-id", "probe-test", "--workspace", root],
                env={**os.environ, "CLAUDE_CRITIC_SKIP_HEALTH": "1"},
                capture_output=True, text=True, timeout=60, check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Claude-as-critic health check", completed.stdout)
        self.assertIn("Result: ONLINE", completed.stdout)
        self.assertIn("Gate: armed", completed.stdout)

    def test_session_start_injects_the_protocol_as_utf8(self):
        launcher = (
            "import os,sys,runpy; d=os.path.join(os.environ['CLAUDE_PLUGIN_ROOT'],'hooks'); "
            "sys.path.insert(0,d); runpy.run_path(os.path.join(d,'critic_context.py'),run_name='__main__')"
        )
        completed = subprocess.run(
            [sys.executable, "-c", launcher],
            env={
                **os.environ,
                "CLAUDE_PLUGIN_ROOT": str(PLUGIN),
                "CLAUDE_CRITIC_SKIP_HEALTH": "1",
            },
            input=b"{}",
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        emitted = completed.stdout.decode("utf-8")
        self.assertIn("Claude Critic Protocol", emitted)
        self.assertIn("target 2–3 per task", emitted)
        self.assertIn("Claude-as-critic", emitted)
        self.assertNotIn("�", emitted)


if __name__ == "__main__":
    unittest.main()
