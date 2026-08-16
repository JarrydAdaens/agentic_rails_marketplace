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
MARKETPLACE = PLUGIN.parents[2]
NAME = "cursor-as-advisor-guardrail"


class PluginLayoutTests(unittest.TestCase):
    def test_codex_manifest_is_cataloged_and_carries_mcp_inline(self):
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], NAME)
        self.assertIn(NAME, manifest["mcpServers"])
        self.assertTrue((PLUGIN / "hooks" / "hooks.json").is_file())
        catalog = json.loads((MARKETPLACE / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        names = [entry["name"] for entry in catalog["plugins"]]
        self.assertEqual(names.count(NAME), 1)

    def test_hook_payload_stays_inside_plugin(self):
        hooks = (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8")
        self.assertNotIn("../", hooks)


if __name__ == "__main__":
    unittest.main()
