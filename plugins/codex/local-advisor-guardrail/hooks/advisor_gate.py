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

"""PreToolUse gate: deny Write/Edit tools until the advisor has been consulted this session.

Reads the hook payload from stdin. If no consult marker exists for the current
session, emits a permissionDecision deny so the executor self-corrects by
consulting the advisor subagent first. Marker files are created by
advisor_marker.py (PostToolUse on Task/Agent).
"""

import json
import sys

from advisor_markers import has_marker
from advisor_streams import force_utf8, read_hook_payload

DENY_REASON = (
    "Advisor gate: consult the advisor before the first write of this session. "
    "In Claude Code, invoke local-advisor-guardrail:advisor with Task/Agent. In Codex "
    "or Cursor, call consult_advisor from "
    "plugin-local-advisor-guardrail-local-advisor-guardrail. Supply the task, "
    "stage, approach, evidence, "
    "and question fields from the Advisor Protocol, then retry this edit."
)


def main() -> None:
    force_utf8()
    payload = read_hook_payload()
    if payload is None:
        sys.exit(0)

    session_id = payload.get("session_id") or payload.get("conversation_id") or "unknown"
    if has_marker(session_id):
        sys.exit(0)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": DENY_REASON,
        }
    }))


if __name__ == "__main__":
    main()
