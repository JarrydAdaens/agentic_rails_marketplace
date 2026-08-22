# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parents[1]
HOOKS = PLUGIN / "hooks"
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(HOOKS))
import claude_home_fence  # noqa: E402

CURSOR_HOOKS = HOOKS / "cursor-hooks.json"
MANIFEST = PLUGIN / ".cursor-plugin" / "plugin.json"
LAUNCHER = SCRIPTS / "launch-windows.cmd"
SCRIPT = HOOKS / "claude_home_fence.py"


class PluginLayoutTests(unittest.TestCase):
    def test_cursor_only_manifest(self):
        self.assertTrue(MANIFEST.is_file())
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "claude-home-fence-guardrail")
        self.assertFalse((PLUGIN / ".claude-plugin").exists())
        self.assertFalse((PLUGIN / ".codex-plugin").exists())
        self.assertFalse((HOOKS / "hooks.json").exists())
        self.assertFalse((HOOKS / "claude-home-fence.ps1").exists())

    def test_cursor_hooks_use_uv_launcher(self):
        config = json.loads(CURSOR_HOOKS.read_text(encoding="utf-8"))
        hooks = config["hooks"]
        self.assertTrue(LAUNCHER.is_file())
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(hooks["beforeReadFile"][0]["failClosed"])
        self.assertTrue(hooks["beforeTabFileRead"][0]["failClosed"])
        self.assertIn("sessionStart", hooks)
        self.assertIn("beforeShellExecution", hooks)
        matchers = " ".join(entry.get("matcher", "") for entry in hooks["preToolUse"])
        for tool in ("Write", "StrReplace", "Delete", "Grep", "Glob", "Read", "Shell"):
            self.assertIn(tool, matchers)
        command = hooks["beforeReadFile"][0]["command"]
        self.assertIn("launch-windows.cmd", command)
        self.assertIn("claude_home_fence.py", command)
        self.assertNotIn("powershell", command.lower())


class FenceBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="claude-fence-home-"))
        self.claude = self.home / ".claude"
        self.claude.mkdir()
        (self.claude / "skills").mkdir()
        self.skill = self.claude / "skills" / "SKILL.md"
        self.skill.write_text("secret", encoding="utf-8")
        self.workspace = Path(tempfile.mkdtemp(prefix="claude-fence-ws-"))
        (self.workspace / "CLAUDE.md").write_text("project", encoding="utf-8")
        (self.workspace / ".claude").mkdir()
        (self.workspace / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
        (self.workspace / ".agents").mkdir()
        (self.workspace / ".agents" / "agent.md").write_text("local", encoding="utf-8")
        self.cursor_home = self.home / ".cursor"
        self.cursor_home.mkdir()
        (self.cursor_home / "skills").mkdir()
        (self.cursor_home / "skills" / "SKILL.md").write_text("cursor", encoding="utf-8")
        self.env = {
            "USERPROFILE": str(self.home),
            "HOME": str(self.home),
        }

    def invoke(self, payload: dict | None = None, *, raw: str | None = None) -> tuple[int, dict | None, str]:
        stdin = raw if raw is not None else json.dumps(payload or {})
        output = io.StringIO()
        code = 0
        with patch.dict(os.environ, self.env, clear=False):
            with patch.object(sys, "stdin", io.StringIO(stdin)), contextlib.redirect_stdout(output):
                try:
                    claude_home_fence.main()
                except SystemExit as exc:
                    code = int(exc.code or 0)
        stdout = output.getvalue().strip()
        parsed = json.loads(stdout) if stdout else None
        return code, parsed, stdout

    def test_denies_before_read_under_claude_home(self):
        code, decision, _ = self.invoke(
            {
                "hook_event_name": "beforeReadFile",
                "file_path": str(self.skill),
                "workspace_roots": [str(self.workspace)],
            }
        )
        self.assertEqual(code, 0)
        assert decision is not None
        self.assertEqual(decision["permission"], "deny")
        self.assertIn("claude-home-fence-guardrail", decision["user_message"])

    def test_allows_workspace_claude_md_with_json(self):
        code, decision, stdout = self.invoke(
            {
                "hook_event_name": "beforeReadFile",
                "file_path": str(self.workspace / "CLAUDE.md"),
                "workspace_roots": [str(self.workspace)],
            }
        )
        self.assertEqual(code, 0)
        self.assertTrue(stdout)
        assert decision is not None
        self.assertEqual(decision["permission"], "allow")

    def test_allows_project_local_dot_claude(self):
        code, decision, _ = self.invoke(
            {
                "hook_event_name": "beforeReadFile",
                "file_path": str(self.workspace / ".claude" / "settings.json"),
                "workspace_roots": [str(self.workspace)],
            }
        )
        self.assertEqual(code, 0)
        assert decision is not None
        self.assertEqual(decision["permission"], "allow")

    def test_allows_project_local_dot_agents(self):
        code, decision, _ = self.invoke(
            {
                "hook_event_name": "beforeReadFile",
                "file_path": str(self.workspace / ".agents" / "agent.md"),
                "workspace_roots": [str(self.workspace)],
            }
        )
        self.assertEqual(code, 0)
        assert decision is not None
        self.assertEqual(decision["permission"], "allow")

    def test_allows_cursor_home(self):
        code, decision, _ = self.invoke(
            {
                "hook_event_name": "beforeReadFile",
                "file_path": str(self.cursor_home / "skills" / "SKILL.md"),
                "workspace_roots": [str(self.workspace)],
            }
        )
        self.assertEqual(code, 0)
        assert decision is not None
        self.assertEqual(decision["permission"], "allow")

    def test_denies_grep_path_under_claude_home(self):
        code, decision, _ = self.invoke(
            {
                "hook_event_name": "preToolUse",
                "tool_name": "Grep",
                "tool_input": {"path": str(self.claude / "skills"), "pattern": "secret"},
                "workspace_roots": [str(self.workspace)],
            }
        )
        self.assertEqual(code, 0)
        assert decision is not None
        self.assertEqual(decision["permission"], "deny")
        self.assertIn("agent_message", decision)

    def test_denies_shell_userprofile_reference(self):
        code, decision, _ = self.invoke(
            {
                "hook_event_name": "beforeShellExecution",
                "command": r'Get-Content "$env:USERPROFILE\.claude\skills\SKILL.md"',
                "cwd": str(self.workspace),
                "workspace_roots": [str(self.workspace)],
            }
        )
        self.assertEqual(code, 0)
        assert decision is not None
        self.assertEqual(decision["permission"], "deny")

    def test_denies_shell_tilde_reference(self):
        code, decision, _ = self.invoke(
            {
                "hook_event_name": "preToolUse",
                "tool_name": "Shell",
                "tool_input": {"command": "cat ~/.claude/skills/SKILL.md"},
                "workspace_roots": [str(self.workspace)],
            }
        )
        self.assertEqual(code, 0)
        assert decision is not None
        self.assertEqual(decision["permission"], "deny")

    def test_allows_unrelated_shell_with_json(self):
        code, decision, stdout = self.invoke(
            {
                "hook_event_name": "beforeShellExecution",
                "command": "git status",
                "cwd": str(self.workspace),
                "workspace_roots": [str(self.workspace)],
            }
        )
        self.assertEqual(code, 0)
        self.assertTrue(stdout)
        assert decision is not None
        self.assertEqual(decision["permission"], "allow")

    def test_empty_stdin_emits_allow_json(self):
        code, decision, stdout = self.invoke(raw="")
        self.assertEqual(code, 0)
        self.assertTrue(stdout)
        assert decision is not None
        self.assertEqual(decision["permission"], "allow")

    def test_malformed_stdin_emits_allow_json(self):
        code, decision, stdout = self.invoke(raw="{")
        self.assertEqual(code, 0)
        self.assertTrue(stdout)
        assert decision is not None
        self.assertEqual(decision["permission"], "allow")

    def test_session_start_injects_policy(self):
        code, decision, _ = self.invoke(
            {
                "hook_event_name": "sessionStart",
                "workspace_roots": [str(self.workspace)],
            }
        )
        self.assertEqual(code, 0)
        assert decision is not None
        self.assertIn("HARD POLICY", decision["additional_context"])
        self.assertIn("~/.claude", decision["additional_context"])

    def test_disabled_seam_allows_claude_home_read(self):
        harness = self.workspace / "harness" / "claude-home-fence-guardrail"
        harness.mkdir(parents=True)
        (harness / "cursor-config.json").write_text('{"enabled": false}\n', encoding="utf-8")
        code, decision, _ = self.invoke(
            {
                "hook_event_name": "beforeReadFile",
                "file_path": str(self.skill),
                "workspace_roots": [str(self.workspace)],
                "cwd": str(self.workspace),
            }
        )
        self.assertEqual(code, 0)
        assert decision is not None
        self.assertEqual(decision["permission"], "allow")


if __name__ == "__main__":
    unittest.main()
