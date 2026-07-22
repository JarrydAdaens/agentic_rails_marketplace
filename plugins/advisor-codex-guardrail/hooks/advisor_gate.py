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

"""PreToolUse gate: deny apply_patch until the advisor has been consulted this session.

Reads the hook payload from stdin. If no consult marker exists for the current
session, emits a permissionDecision deny so the executor self-corrects by
consulting the advisor first. Marker files are created by advisor_marker.py
(PostToolUse on consult_advisor).
"""

import json
import sys

from advisor_markers import has_marker

DENY_REASON = (
    "Advisor gate: consult the advisor before the first write of this session. "
    "Invoke consult_advisor with the payload format from the Advisor Protocol in "
    "your context (task / stage / approach / evidence / question), then retry "
    "this patch."
)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # malformed input: fail open rather than block all writes

    session_id = payload.get("session_id", "unknown")
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
