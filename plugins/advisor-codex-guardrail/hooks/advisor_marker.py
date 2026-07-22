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

"""PostToolUse marker: record that the advisor was consulted this session.

Fires on consult_advisor completions (plain or MCP-namespaced, e.g.
mcp__advisor-codex-guardrail__consult_advisor). Touches a per-session marker
file that advisor_gate.py checks before allowing apply_patch.
"""

import json
import sys

from advisor_markers import marker_dir, marker_path


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = str(payload.get("tool_name") or payload.get("tool") or "")
    if not (tool_name == "consult_advisor" or tool_name.endswith("consult_advisor")):
        sys.exit(0)

    session_id = payload.get("session_id", "unknown")
    marker_dir().mkdir(parents=True, exist_ok=True)
    marker_path(session_id).touch()


if __name__ == "__main__":
    main()
