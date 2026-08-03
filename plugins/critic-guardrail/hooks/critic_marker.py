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

"""PostToolUse marker: record that the critic was consulted this session.

Fires on consult_critic completions (plain or MCP-namespaced, e.g.
mcp__critic-guardrail__consult_critic). Touches a per-session marker file that
critic_gate.py checks before allowing Write/Edit tools.
"""

import json
import sys

from critic_markers import marker_dir, marker_path


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = str(payload.get("tool_name") or payload.get("tool") or "")
    if not (tool_name == "consult_critic" or tool_name.endswith("consult_critic")):
        sys.exit(0)

    session_id = payload.get("session_id", "unknown")
    marker_dir().mkdir(parents=True, exist_ok=True)
    marker_path(session_id).touch()


if __name__ == "__main__":
    main()
