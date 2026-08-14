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

"""PreToolUse gate: deny writes only when critic health is online and no consult yet."""

from __future__ import annotations

import json
import sys

from critic_markers import HEALTH_SKILL, has_marker, health_state, offline_reason
from critic_streams import force_utf8

CLAUDE_DENY = (
    "Critic gate: consult the critic before the first write of this session. "
    "Call consult_critic (MCP) with all five fields from the Critic Protocol "
    "(task / stage / approach / evidence / question), then retry this edit."
)

CURSOR_DENY = (
    "Critic gate: consult the critic before the first write of this session. "
    "Pipe a JSON object with task, stage, approach, evidence, and question to "
    "cli/consult_critic.py via the plugin launcher (see Critic Protocol), then retry."
)


def _session_id(payload: dict) -> str:
    return str(payload.get("session_id") or payload.get("conversation_id") or "unknown")


def _cursor_payload(permission: str, message: str) -> str:
    return json.dumps({
        "permission": permission,
        "user_message": message,
        "agent_message": message,
    })


def main() -> None:
    force_utf8()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("Codex critic hook received invalid input; allowing the write.", file=sys.stderr)
        sys.exit(0)

    if not isinstance(payload, dict):
        print("Codex critic hook received an unexpected payload; allowing the write.", file=sys.stderr)
        sys.exit(0)

    session_id = _session_id(payload)
    if has_marker(session_id):
        sys.exit(0)

    cursor = payload.get("hook_event_name") == "preToolUse"
    state = health_state(session_id)

    if state == "pending":
        message = (
            "Codex-as-critic health pending — write gate fail-open until the probe finishes."
        )
    elif state == "offline":
        message = (
            f"Codex-as-critic offline — {offline_reason(session_id)}. "
            f"Write gate disarmed. Retest with the {HEALTH_SKILL} skill."
        )
    else:
        message = None

    if message is not None:
        if cursor:
            print(message, file=sys.stderr)
            print(_cursor_payload("allow", message))
            return
        print(message, file=sys.stderr)
        sys.exit(0)

    # online and not consulted
    deny = CURSOR_DENY if cursor else CLAUDE_DENY
    if cursor:
        print(json.dumps({
            "permission": "deny",
            "user_message": deny,
            "agent_message": deny,
        }))
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny,
        }
    }))


if __name__ == "__main__":
    main()
