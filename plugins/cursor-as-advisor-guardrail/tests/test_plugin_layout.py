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

import json
import unittest
from pathlib import Path

PLUGIN = Path(__file__).parents[1]
MARKETPLACE = PLUGIN.parents[1]
NAME = "cursor-as-advisor-guardrail"


class PluginLayoutTests(unittest.TestCase):
    def test_claude_manifest_has_stable_identity_and_no_version(self):
        manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], NAME)
        self.assertNotIn("version", manifest)

    def test_claude_catalog_lists_plugin_once_at_the_end(self):
        catalog = json.loads((MARKETPLACE / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        names = [entry["name"] for entry in catalog["plugins"]]
        self.assertEqual(names.count(NAME), 1)
        self.assertEqual(names[-1], NAME)
        entry = catalog["plugins"][-1]
        self.assertEqual(entry["source"], f"./plugins/{NAME}")
        self.assertEqual(entry["category"], "guardrail")

    def test_claude_only_plugin_is_excluded_from_codex_catalog(self):
        self.assertFalse((PLUGIN / ".codex-plugin").exists())
        catalog = json.loads((MARKETPLACE / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        names = [entry["name"] for entry in catalog["plugins"]]
        self.assertNotIn(NAME, names)

    def test_mcp_and_hook_payloads_stay_inside_plugin(self):
        mcp = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
        launcher = mcp["mcpServers"][NAME]
        self.assertEqual(launcher["command"], "python")
        self.assertEqual(launcher["args"], ["${CLAUDE_PLUGIN_ROOT}/mcp/advisor_server.py"])
        hooks = (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8")
        self.assertNotIn("../", hooks)


if __name__ == "__main__":
    unittest.main()
