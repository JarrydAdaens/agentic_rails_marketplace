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

"""Deny Claude write tools until Cursor has advised this session."""

import json
import os
import sys

from advisor_markers import has_live_server, has_marker
from advisor_streams import force_utf8

DENY_REASON = (
    "Cursor advisor gate: consult the advisor before the first write of this "
    "session. Call the consult_advisor MCP tool with all five fields from the "
    "Cursor Advisor Protocol in your context (task / stage / approach / "
    "evidence / question), then retry this edit."
)


def main() -> None:
    force_utf8()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        sys.exit(0)

    session_id = payload.get("session_id") or payload.get("conversation_id", "unknown")
    if has_marker(session_id):
        sys.exit(0)

    if payload.get("hook_event_name") == "preToolUse":
        roots = payload.get("workspace_roots") or []
        workspace = roots[0] if roots else payload.get("cwd")
        if not has_live_server("cursor", workspace):
            reason = "Cursor advisor gate is inactive because Cursor has not registered consult_advisor for this workspace. Install and approve the MCP server, then start a fresh session."
            print(reason, file=sys.stderr)
            print(json.dumps({"permission": "allow", "user_message": reason, "agent_message": reason}))
            return
        print(json.dumps({
            "permission": "deny",
            "user_message": DENY_REASON,
            "agent_message": DENY_REASON,
        }))
        return

    if os.environ.get("PLUGIN_ROOT") and not has_live_server("codex", payload.get("cwd")):
        print("Cursor advisor gate is inactive because Codex has not registered consult_advisor for this workspace. Enable the plugin MCP server and start a fresh thread.", file=sys.stderr)
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": DENY_REASON,
        }
    }))


if __name__ == "__main__":
    main()
