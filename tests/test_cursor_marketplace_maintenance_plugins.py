# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

import json
import py_compile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CURSOR_ROOT = ROOT / "plugins" / "cursor"
CATALOG = ROOT / ".cursor-plugin" / "marketplace.json"


class CursorMarketplaceMaintenancePluginTests(unittest.TestCase):
    def test_doctor_and_surgeon_are_cursor_only_catalogued_plugins(self):
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        entries = {entry["name"]: entry for entry in catalog["plugins"]}
        for name in ("rails-marketplace-doctor", "rails-marketplace-surgeon"):
            with self.subTest(plugin=name):
                plugin = CURSOR_ROOT / name
                self.assertEqual(entries[name]["source"], f"./plugins/cursor/{name}")
                manifest = json.loads((plugin / ".cursor-plugin" / "plugin.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["name"], name)
                self.assertFalse((plugin / ".claude-plugin").exists())
                self.assertFalse((plugin / ".codex-plugin").exists())

    def test_each_plugin_has_primary_help_and_health_skills(self):
        expected = {
            "rails-marketplace-doctor": ("rails-marketplace-doctor", "rails-doctor-help", "rails-doctor-health"),
            "rails-marketplace-surgeon": ("rails-marketplace-surgeon", "rails-surgeon-help", "rails-surgeon-health"),
        }
        for plugin, skills in expected.items():
            for skill in skills:
                with self.subTest(plugin=plugin, skill=skill):
                    path = CURSOR_ROOT / plugin / "skills" / skill / "SKILL.md"
                    self.assertTrue(path.is_file())
                    self.assertIn(f"name: {skill}", path.read_text(encoding="utf-8"))

    def test_maintenance_scripts_compile(self):
        for script in (
            CURSOR_ROOT / "rails-marketplace-doctor" / "scripts" / "marketplace_doctor.py",
            CURSOR_ROOT / "rails-marketplace-surgeon" / "scripts" / "marketplace_surgeon.py",
        ):
            with self.subTest(script=script):
                py_compile.compile(str(script), doraise=True)


if __name__ == "__main__":
    unittest.main()
