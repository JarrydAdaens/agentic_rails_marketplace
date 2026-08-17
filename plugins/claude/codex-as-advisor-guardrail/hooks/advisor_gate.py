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

"""PreToolUse gate: deny writes only when advisor health is online and no consult yet."""

from __future__ import annotations

import json
import sys

from advisor_markers import HEALTH_SKILL, has_marker, health_state, offline_reason
from advisor_streams import force_utf8, read_hook_payload

DENY = (
    "Advisor gate: consult the advisor before the first write of this session. "
    "Run `uv run --no-project python ./scripts/launch.py ./cli/consult_advisor.py` "
    "and pipe a JSON object with all five fields from the Advisor Protocol "
    "(task / stage / approach / evidence / question) to its stdin, then retry this edit."
)


def _session_id(payload: dict) -> str:
    return str(payload.get("session_id") or payload.get("conversation_id") or "unknown")


def main() -> None:
    force_utf8()
    payload = read_hook_payload()
    if payload is None:
        sys.exit(0)

    session_id = _session_id(payload)
    if has_marker(session_id):
        sys.exit(0)

    state = health_state(session_id)

    if state == "pending":
        print(
            "Codex-as-advisor health pending — write gate fail-open until the probe finishes.",
            file=sys.stderr,
        )
        sys.exit(0)

    if state == "offline":
        print(
            f"Codex-as-advisor offline — {offline_reason(session_id)}. "
            f"Write gate disarmed. Retest with the {HEALTH_SKILL} skill.",
            file=sys.stderr,
        )
        sys.exit(0)

    # online and not consulted
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": DENY,
        }
    }))


if __name__ == "__main__":
    main()
