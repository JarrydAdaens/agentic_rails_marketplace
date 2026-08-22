# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CURSOR = ROOT / "plugins" / "cursor"

PYTHON_TOAST = frozenset({
    "claude-as-advisor-guardrail",
    "claude-as-critic-guardrail",
    "claude-home-fence-guardrail",
    "codex-as-advisor-guardrail",
    "codex-as-critic-guardrail",
    "cursor-as-advisor-guardrail",
    "cursor-as-critic-guardrail",
    "local-advisor-guardrail",
})
POWERSHELL_TOAST = frozenset({
    "jobs-done-guardrail",
    "python-uv-guardrail",
    "readme-name-guardrail",
})


class CursorGuardrailOnlineToastTests(unittest.TestCase):
    def test_every_cursor_guardrail_toasts_on_session_start(self):
        plugins = sorted(
            path for path in CURSOR.iterdir()
            if path.is_dir() and path.name.endswith("-guardrail")
        )
        names = {path.name for path in plugins}
        self.assertEqual(names, PYTHON_TOAST | POWERSHELL_TOAST)

        canonical_py = (CURSOR / "claude-as-advisor-guardrail" / "hooks" / "windows_toast.py").read_text(encoding="utf-8")
        canonical_ps = (CURSOR / "python-uv-guardrail" / "hooks" / "notify-online.ps1").read_text(encoding="utf-8")

        for plugin in plugins:
            with self.subTest(plugin=plugin.name):
                hooks = json.loads((plugin / "hooks" / "cursor-hooks.json").read_text(encoding="utf-8"))["hooks"]
                self.assertIn("sessionStart", hooks)
                if plugin.name in POWERSHELL_TOAST:
                    notify = plugin / "hooks" / "notify-online.ps1"
                    self.assertTrue(notify.is_file())
                    self.assertEqual(notify.read_text(encoding="utf-8"), canonical_ps)
                    self.assertIn("notify-online.ps1", json.dumps(hooks["sessionStart"]))
                    self.assertNotIn("windows_toast.py", json.dumps(hooks["sessionStart"]))
                else:
                    toast = plugin / "hooks" / "windows_toast.py"
                    self.assertTrue(toast.is_file())
                    self.assertEqual(toast.read_text(encoding="utf-8"), canonical_py)


if __name__ == "__main__":
    unittest.main()
