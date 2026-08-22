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

"""PostToolUse marker: record that the advisor subagent was consulted this session.

Fires on Task/Agent tool completions. When the invoked subagent is the advisor
(plain or plugin-namespaced), touches a per-session marker file that
advisor_gate.py checks before allowing Write/Edit tools.
"""

import sys

from advisor_markers import marker_dir, marker_path
from advisor_streams import force_utf8, read_hook_payload


def main() -> None:
    force_utf8()
    payload = read_hook_payload()
    if payload is None:
        sys.exit(0)

    tool_name = str(payload.get("tool_name") or payload.get("tool") or "")
    tool_input = payload.get("tool_input") or payload.get("input") or {}
    subagent = str(tool_input.get("subagent_type") or "")
    is_advisor = tool_name in ("Task", "Agent", "") and (
        subagent.startswith("local-advisor-") or subagent.endswith(":advisor")
    )
    if not is_advisor:
        sys.exit(0)

    session_id = payload.get("session_id") or payload.get("conversation_id") or "unknown"
    marker_dir().mkdir(parents=True, exist_ok=True)
    marker_path(session_id).touch()


if __name__ == "__main__":
    main()
