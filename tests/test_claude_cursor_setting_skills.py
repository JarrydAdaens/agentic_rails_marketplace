# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

import json
import os
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
                    "--model", "2b", "--workspace", workspace,
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

                cancelled = self.run_cli(
                    root / "cli" / f"{prefix}_model.py",
                    "--model", "cancel", "--workspace", workspace,
                )
                self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
                self.assertIn("cancelled", cancelled.stdout.lower())
                still_saved = json.loads("\n".join(
                    line for line in config_path.read_text(encoding="utf-8").splitlines()
                    if not line.lstrip().startswith("//")
                ))
                self.assertEqual(still_saved["model"], "deity")

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
                self.assertIn("0. Cancel", result.stdout)
                self.assertIn("a. Cancel", result.stdout)
                self.assertIn("4f", result.stdout)
                self.assertIn("Opus (Current)", result.stdout)
                self.assertIn("High (Current)", result.stdout)
                self.assertNotIn("Default (recommended)", result.stdout)

    def test_timeout_control_persists_numbers_defaults_and_cancellation(self):
        cases = (
            ("claude-as-advisor-guardrail", "advisor", "Advisor"),
            ("claude-as-critic-guardrail", "critic", "Critic"),
        )
        for plugin, prefix, label in cases:
            with self.subTest(plugin=plugin), tempfile.TemporaryDirectory() as workspace:
                root = CURSOR / plugin
                prompt = self.run_cli(
                    root / "cli" / f"{prefix}_timeout.py",
                    "--seconds", "--workspace", workspace,
                )
                self.assertEqual(prompt.returncode, 0, prompt.stderr)
                self.assertIn("Consult timeout", prompt.stdout)
                self.assertIn("fourhundred", prompt.stdout)
                self.assertIn("Config path:", prompt.stdout)
                self.assertIn("health_timeout_seconds", prompt.stdout)

                numeric = self.run_cli(
                    root / "cli" / f"{prefix}_timeout.py",
                    "--seconds", "123", "--workspace", workspace,
                )
                self.assertEqual(numeric.returncode, 0, numeric.stderr)
                self.assertIn(f"{label} consult timeout is now: 123 seconds", numeric.stdout)

                spelled = self.run_cli(
                    root / "cli" / f"{prefix}_timeout.py",
                    "--seconds", "fourhundred", "--workspace", workspace,
                )
                self.assertEqual(spelled.returncode, 0, spelled.stderr)
                self.assertIn(f"{label} consult timeout is now: 400 seconds", spelled.stdout)

                config_path = Path(workspace) / "harness" / plugin / "config.json"
                config = json.loads("\n".join(
                    line for line in config_path.read_text(encoding="utf-8").splitlines()
                    if not line.lstrip().startswith("//")
                ))
                self.assertEqual(config["consult_timeout_seconds"], 400)

                cancelled = self.run_cli(
                    root / "cli" / f"{prefix}_timeout.py",
                    "--seconds", "nevermind", "--workspace", workspace,
                )
                self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
                self.assertIn("cancelled", cancelled.stdout.lower())

                defaulted = self.run_cli(
                    root / "cli" / f"{prefix}_timeout.py",
                    "--seconds", "default", "--workspace", workspace,
                )
                self.assertEqual(defaulted.returncode, 0, defaulted.stderr)
                self.assertIn("600 seconds", defaulted.stdout)

                config = json.loads("\n".join(
                    line for line in config_path.read_text(encoding="utf-8").splitlines()
                    if not line.lstrip().startswith("//")
                ))
                self.assertEqual(config["consult_timeout_seconds"], 600)

    def test_health_reports_config_presence_and_full_path(self):
        cases = (
            ("claude-as-advisor-guardrail", "advisor", "CLAUDE_ADVISOR_SKIP_HEALTH"),
            ("claude-as-critic-guardrail", "critic", "CLAUDE_CRITIC_SKIP_HEALTH"),
        )
        for plugin, prefix, skip_var in cases:
            with self.subTest(plugin=plugin), tempfile.TemporaryDirectory() as workspace:
                result = subprocess.run(
                    [sys.executable, str(CURSOR / plugin / "cli" / f"{prefix}_health.py"),
                     "--workspace", workspace],
                    text=True, capture_output=True, timeout=60, check=False,
                    env={**os.environ, skip_var: "1"},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Config file: MISSING", result.stdout)
                self.assertIn(str(Path(workspace).resolve()), result.stdout)
                self.assertIn("health_timeout_seconds", result.stdout)

    def test_init_writes_explanatory_comments_for_both_timeout_fields(self):
        cases = (
            ("claude-as-advisor-guardrail", "advisor"),
            ("claude-as-critic-guardrail", "critic"),
        )
        for plugin, prefix in cases:
            with self.subTest(plugin=plugin), tempfile.TemporaryDirectory() as workspace:
                root = CURSOR / plugin
                initialized = self.run_cli(
                    root / "cli" / f"{prefix}_init.py", "--workspace", workspace,
                )
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                self.assertIn("documents both timeout fields", initialized.stdout)
                config = (Path(workspace) / "harness" / plugin / "config.json").read_text(
                    encoding="utf-8"
                )
                self.assertIn("Maximum wall-clock seconds a full", config)
                self.assertIn("This is separate from the consult limit.", config)
                self.assertIn('"consult_timeout_seconds": 600', config)
                self.assertIn('"health_timeout_seconds": 90', config)

    def test_version_skill_reports_the_installed_version_and_timestamp(self):
        for plugin, prefix in (
            ("claude-as-advisor-guardrail", "advisor"),
            ("claude-as-critic-guardrail", "critic"),
        ):
            with self.subTest(plugin=plugin):
                result = self.run_cli(CURSOR / plugin / "cli" / f"{prefix}_version.py")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertRegex(result.stdout, r"Version is 1\.3\.3 last edited \d{2}:\d{2} \d{2}-\d{2}-\d{4}")


if __name__ == "__main__":
    unittest.main()
