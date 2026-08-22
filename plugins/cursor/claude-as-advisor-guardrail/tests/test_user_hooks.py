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
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).parents[1]
CLI = PLUGIN / "cli" / "advisor_install_hooks.py"
REMOVE = PLUGIN / "cli" / "advisor_remove_hooks.py"

FENCE = {
    "command": r"C:\Windows\System32\cmd.exe /d /c .\scripts\launch-windows.cmd .\hooks\claude_home_fence.py",
    "failClosed": True,
}
SIBLING = {
    "matcher": "Write|StrReplace|Delete|Edit",
    "command": r'uv run --no-project python "C:\Users\Jarry\.cursor\plugins\local\claude-as-critic-guardrail\scripts\launch.py" "C:\Users\Jarry\.cursor\plugins\local\claude-as-critic-guardrail\hooks\critic_gate.py"',
    "failClosed": False,
}
SEED = {
    "version": 1,
    "hooks": {
        "beforeReadFile": [dict(FENCE)],
        "preToolUse": [dict(FENCE), dict(SIBLING)],
        "sessionStart": [dict(FENCE)],
    },
}


def run_cli(script: Path, hooks_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--hooks-file", str(hooks_file)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=str(PLUGIN),
        env={**os.environ},
    )


class UserHookInstallTests(unittest.TestCase):
    def test_install_twice_then_remove_restores_seed(self):
        with tempfile.TemporaryDirectory() as raw:
            hooks_file = Path(raw) / "hooks.json"
            hooks_file.write_text(json.dumps(SEED, indent=2) + "\n", encoding="utf-8")
            seed = json.loads(hooks_file.read_text(encoding="utf-8"))

            first = run_cli(CLI, hooks_file)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("Claude-as-advisor hooks installed", first.stdout)
            after_first = json.loads(hooks_file.read_text(encoding="utf-8"))

            second = run_cli(CLI, hooks_file)
            self.assertEqual(second.returncode, 0, second.stderr)
            after_second = json.loads(hooks_file.read_text(encoding="utf-8"))
            self.assertEqual(after_first, after_second)

            pre = after_second["hooks"]["preToolUse"]
            self.assertEqual(pre[0]["command"], FENCE["command"])
            self.assertEqual(pre[1]["command"], SIBLING["command"])
            self.assertTrue(any("claude-as-advisor-guardrail" in str(item["command"]) for item in pre))
            self.assertTrue(any("advisor_gate.py" in str(item["command"]) for item in pre))

            removed = run_cli(REMOVE, hooks_file)
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertIn("Claude-as-advisor hooks removed", removed.stdout)
            restored = json.loads(hooks_file.read_text(encoding="utf-8"))
            self.assertEqual(restored, seed)

    def test_malformed_hooks_file_is_not_written(self):
        with tempfile.TemporaryDirectory() as raw:
            hooks_file = Path(raw) / "hooks.json"
            hooks_file.write_text("{not json", encoding="utf-8")
            completed = run_cli(CLI, hooks_file)
            self.assertEqual(completed.returncode, 1)
            self.assertEqual(hooks_file.read_text(encoding="utf-8"), "{not json")
            self.assertFalse((hooks_file.with_name("hooks.json.bak")).exists())


if __name__ == "__main__":
    unittest.main()
