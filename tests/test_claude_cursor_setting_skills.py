# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CURSOR = ROOT / "plugins" / "cursor"


class ClaudeCursorSettingSkillsTests(unittest.TestCase):
    def run_cli(self, path: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(path), *args], text=True, capture_output=True,
            timeout=60, check=False,
        )

    def test_enabled_and_model_controls_persist_for_advisor_and_critic(self):
        cases = (
            ("claude-as-advisor-guardrail", "advisor", "Advisor"),
            ("claude-as-critic-guardrail", "critic", "Critic"),
        )
        for plugin, prefix, label in cases:
            with self.subTest(plugin=plugin), tempfile.TemporaryDirectory() as workspace:
                root = CURSOR / plugin
                enabled = self.run_cli(
                    root / "cli" / f"{prefix}_enabled.py",
                    "--enabled", "disengage", "--workspace", workspace,
                )
                self.assertEqual(enabled.returncode, 0, enabled.stderr)
                self.assertIn(f"{label} is now: Disabled", enabled.stdout)

                compact = self.run_cli(
                    root / "cli" / f"{prefix}_model.py",
                    "--model", "2a", "--workspace", workspace,
                )
                self.assertEqual(compact.returncode, 0, compact.stderr)
                self.assertIn("Sonnet", compact.stdout)
                self.assertIn("Low", compact.stdout)

                future = self.run_cli(
                    root / "cli" / f"{prefix}_model.py",
                    "--model", "deity high", "--workspace", workspace,
                )
                self.assertEqual(future.returncode, 0, future.stderr)
                self.assertIn("Deity", future.stdout)

                config_path = Path(workspace) / "harness" / plugin / "config.json"
                config_text = config_path.read_text(encoding="utf-8")
                self.assertIn("// Set false", config_text)
                config = json.loads("\n".join(line for line in config_text.splitlines() if not line.lstrip().startswith("//")))
                self.assertFalse(config["enabled"])
                self.assertEqual(config["model"], "deity")
                self.assertEqual(config["effort"], "high")

    def test_disabled_gate_allows_a_write_without_health_state(self):
        cases = (
            ("claude-as-advisor-guardrail", "advisor", "advisor_gate.py"),
            ("claude-as-critic-guardrail", "critic", "critic_gate.py"),
        )
        for plugin, prefix, gate_name in cases:
            with self.subTest(plugin=plugin), tempfile.TemporaryDirectory() as workspace:
                root = CURSOR / plugin
                enabled = self.run_cli(
                    root / "cli" / f"{prefix}_enabled.py",
                    "--enabled", "off", "--workspace", workspace,
                )
                self.assertEqual(enabled.returncode, 0, enabled.stderr)
                payload = json.dumps({
                    "session_id": "disabled-gate", "hook_event_name": "preToolUse",
                    "tool_name": "Write", "workspace_roots": [workspace],
                })
                gate = subprocess.run(
                    [sys.executable, str(root / "hooks" / gate_name)], input=payload,
                    text=True, capture_output=True, timeout=60, check=False,
                )
                self.assertEqual(gate.returncode, 0, gate.stderr)
                self.assertEqual(json.loads(gate.stdout)["permission"], "allow")

    def test_model_without_value_prints_both_selection_tables(self):
        for plugin, prefix in (
            ("claude-as-advisor-guardrail", "advisor"),
            ("claude-as-critic-guardrail", "critic"),
        ):
            with self.subTest(plugin=plugin):
                result = self.run_cli(CURSOR / plugin / "cli" / f"{prefix}_model.py", "--model")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Select model", result.stdout)
                self.assertIn("Select effort", result.stdout)
                self.assertIn("5e", result.stdout)


if __name__ == "__main__":
    unittest.main()
