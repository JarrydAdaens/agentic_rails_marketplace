# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
HOOKS = PLUGIN / "hooks"
SCRIPT = HOOKS / "claude-home-fence.ps1"
CURSOR_HOOKS = HOOKS / "cursor-hooks.json"
MANIFEST = PLUGIN / ".cursor-plugin" / "plugin.json"


def invoke(payload: dict, *, cwd: Path | None = None, env: dict | None = None) -> tuple[int, str, str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd or PLUGIN),
        env=merged,
        timeout=30,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


class PluginLayoutTests(unittest.TestCase):
    def test_cursor_only_manifest(self):
        self.assertTrue(MANIFEST.is_file())
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "claude-home-fence-guardrail")
        self.assertFalse((PLUGIN / ".claude-plugin").exists())
        self.assertFalse((PLUGIN / ".codex-plugin").exists())
        self.assertFalse((HOOKS / "hooks.json").exists())

    def test_cursor_hooks_cover_read_write_shell_session(self):
        config = json.loads(CURSOR_HOOKS.read_text(encoding="utf-8"))
        hooks = config["hooks"]
        self.assertTrue(hooks["beforeReadFile"][0]["failClosed"])
        self.assertTrue(hooks["beforeTabFileRead"][0]["failClosed"])
        self.assertIn("sessionStart", hooks)
        self.assertIn("beforeShellExecution", hooks)
        matchers = " ".join(entry.get("matcher", "") for entry in hooks["preToolUse"])
        for tool in ("Write", "StrReplace", "Delete", "Grep", "Glob", "Read", "Shell"):
            self.assertIn(tool, matchers)


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
        self.env = {
            "USERPROFILE": str(self.home),
            "HOME": str(self.home),
        }

    def test_denies_before_read_under_claude_home(self):
        code, stdout, _ = invoke(
            {
                "hook_event_name": "beforeReadFile",
                "file_path": str(self.skill),
                "workspace_roots": [str(self.workspace)],
            },
            env=self.env,
        )
        self.assertEqual(code, 0)
        decision = json.loads(stdout)
        self.assertEqual(decision["permission"], "deny")
        self.assertIn("claude-home-fence-guardrail", decision["user_message"])

    def test_allows_workspace_claude_md(self):
        code, stdout, _ = invoke(
            {
                "hook_event_name": "beforeReadFile",
                "file_path": str(self.workspace / "CLAUDE.md"),
                "workspace_roots": [str(self.workspace)],
            },
            env=self.env,
        )
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")

    def test_allows_project_local_dot_claude(self):
        code, stdout, _ = invoke(
            {
                "hook_event_name": "beforeReadFile",
                "file_path": str(self.workspace / ".claude" / "settings.json"),
                "workspace_roots": [str(self.workspace)],
            },
            env=self.env,
        )
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")

    def test_denies_grep_path_under_claude_home(self):
        code, stdout, _ = invoke(
            {
                "hook_event_name": "preToolUse",
                "tool_name": "Grep",
                "tool_input": {"path": str(self.claude / "skills"), "pattern": "secret"},
                "workspace_roots": [str(self.workspace)],
            },
            env=self.env,
        )
        self.assertEqual(code, 0)
        decision = json.loads(stdout)
        self.assertEqual(decision["permission"], "deny")
        self.assertIn("agent_message", decision)

    def test_denies_shell_userprofile_reference(self):
        code, stdout, _ = invoke(
            {
                "hook_event_name": "beforeShellExecution",
                "command": r'Get-Content "$env:USERPROFILE\.claude\skills\SKILL.md"',
                "cwd": str(self.workspace),
                "workspace_roots": [str(self.workspace)],
            },
            env=self.env,
        )
        self.assertEqual(code, 0)
        decision = json.loads(stdout)
        self.assertEqual(decision["permission"], "deny")

    def test_denies_shell_tilde_reference(self):
        code, stdout, _ = invoke(
            {
                "hook_event_name": "preToolUse",
                "tool_name": "Shell",
                "tool_input": {"command": "cat ~/.claude/skills/SKILL.md"},
                "workspace_roots": [str(self.workspace)],
            },
            env=self.env,
        )
        self.assertEqual(code, 0)
        decision = json.loads(stdout)
        self.assertEqual(decision["permission"], "deny")

    def test_allows_unrelated_shell(self):
        code, stdout, _ = invoke(
            {
                "hook_event_name": "beforeShellExecution",
                "command": "git status",
                "cwd": str(self.workspace),
                "workspace_roots": [str(self.workspace)],
            },
            env=self.env,
        )
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")

    def test_session_start_injects_policy(self):
        code, stdout, _ = invoke(
            {
                "hook_event_name": "sessionStart",
                "workspace_roots": [str(self.workspace)],
            },
            env=self.env,
        )
        self.assertEqual(code, 0)
        decision = json.loads(stdout)
        self.assertIn("HARD POLICY", decision["additional_context"])
        self.assertIn("~/.claude", decision["additional_context"])

    def test_disabled_seam_allows_claude_home_read(self):
        harness = self.workspace / "harness" / "claude-home-fence-guardrail"
        harness.mkdir(parents=True)
        (harness / "config.json").write_text('{"enabled": false}\n', encoding="utf-8")
        code, stdout, _ = invoke(
            {
                "hook_event_name": "beforeReadFile",
                "file_path": str(self.skill),
                "workspace_roots": [str(self.workspace)],
                "cwd": str(self.workspace),
            },
            env=self.env,
        )
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")


if __name__ == "__main__":
    unittest.main()
