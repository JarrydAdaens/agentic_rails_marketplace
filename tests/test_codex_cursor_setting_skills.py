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


class CodexCursorSettingSkillsTests(unittest.TestCase):
    def run_cli(self, path: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(path), *args], text=True, capture_output=True,
            timeout=60, check=False,
        )

    def test_controls_persist_and_disabled_gate_allows_writes(self):
        cases = (
            ("codex-as-advisor-guardrail", "advisor", "Advisor", "advisor_gate.py"),
            ("codex-as-critic-guardrail", "critic", "Critic", "critic_gate.py"),
        )
        for plugin, prefix, label, gate_name in cases:
            with self.subTest(plugin=plugin), tempfile.TemporaryDirectory() as workspace:
                root = CURSOR / plugin
                enabled = self.run_cli(root / "cli" / f"{prefix}_enabled.py", "--enabled", "off", "--workspace", workspace)
                self.assertEqual(enabled.returncode, 0, enabled.stderr)
                self.assertIn(f"{label} is now: Disabled", enabled.stdout)

                model = self.run_cli(root / "cli" / f"{prefix}_model.py", "--model", "2a", "--workspace", workspace)
                self.assertEqual(model.returncode, 0, model.stderr)
                self.assertIn("GPT-5.6-TERRA", model.stdout)
                self.assertIn("Low", model.stdout)

                timeout = self.run_cli(root / "cli" / f"{prefix}_timeout.py", "--seconds", "fourhundred", "--workspace", workspace)
                self.assertEqual(timeout.returncode, 0, timeout.stderr)
                self.assertIn("400 seconds", timeout.stdout)

                config_path = Path(workspace) / "harness" / plugin / "cursor-config.json"
                config = json.loads("\n".join(line for line in config_path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("//")))
                self.assertFalse(config["enabled"])
                self.assertEqual(config["model"], "gpt-5.6-terra")
                self.assertEqual(config["effort"], "low")
                self.assertEqual(config["consult_timeout_seconds"], 400)

                payload = json.dumps({"session_id": "disabled", "tool_name": "Write", "workspace_roots": [workspace]})
                gate = subprocess.run([sys.executable, str(root / "hooks" / gate_name)], input=payload, text=True, capture_output=True, timeout=60, check=False)
                self.assertEqual(gate.returncode, 0, gate.stderr)
                self.assertEqual(json.loads(gate.stdout)["permission"], "allow")

    def test_picker_init_timeout_prompt_and_version(self):
        for plugin, prefix in (("codex-as-advisor-guardrail", "advisor"), ("codex-as-critic-guardrail", "critic")):
            with self.subTest(plugin=plugin), tempfile.TemporaryDirectory() as workspace:
                root = CURSOR / plugin
                menu = self.run_cli(root / "cli" / f"{prefix}_model.py", "--model", "--workspace", workspace)
                self.assertEqual(menu.returncode, 0, menu.stderr)
                self.assertIn("0. Cancel", menu.stdout)
                self.assertIn("GPT-5.6-Sol (Current)", menu.stdout)
                self.assertIn("f. Ultra", menu.stdout)

                prompt = self.run_cli(root / "cli" / f"{prefix}_timeout.py", "--seconds", "--workspace", workspace)
                self.assertEqual(prompt.returncode, 0, prompt.stderr)
                self.assertIn("Config path:", prompt.stdout)
                self.assertIn("fourhundred", prompt.stdout)

                initialized = self.run_cli(root / "cli" / f"{prefix}_init.py", "--workspace", workspace)
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                config = (Path(workspace) / "harness" / plugin / "cursor-config.json").read_text(encoding="utf-8")
                self.assertIn("Maximum wall-clock seconds a full", config)
                self.assertIn("This is separate from the consult limit.", config)

                version = self.run_cli(root / "cli" / f"{prefix}_version.py")
                self.assertEqual(version.returncode, 0, version.stderr)
                installed = (root / "VERSION").read_text(encoding="utf-8").strip()
                escaped = installed.replace(".", r"\.")
                self.assertRegex(
                    version.stdout,
                    rf"Version is {escaped} last edited \d{{2}}:\d{{2}} \d{{2}}-\d{{2}}-\d{{4}}",
                )


if __name__ == "__main__":
    unittest.main()
