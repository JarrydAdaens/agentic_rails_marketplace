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

"""Deny writes until Cursor has critiqued this session (native Cursor host)."""

import json
import sys

from critic_markers import has_live_server, has_marker
from critic_streams import force_utf8, read_hook_payload

DENY_REASON = (
    "Critic gate: consult the critic before the first write of this session. "
    "Call the consult_critic MCP tool with all five fields from the Critic "
    "Protocol in your context (task / stage / approach / evidence / question), "
    "then retry this edit."
)


def main() -> None:
    force_utf8()
    payload = read_hook_payload()
    if payload is None:
        sys.exit(0)

    session_id = payload.get("session_id") or payload.get("conversation_id", "unknown")
    if has_marker(session_id):
        sys.exit(0)

    roots = payload.get("workspace_roots") or []
    workspace = roots[0] if roots else payload.get("cwd")
    if not has_live_server("cursor", workspace):
        reason = "Cursor critic gate is inactive because Cursor has not registered consult_critic for this workspace. Install and approve the MCP server, then start a fresh session."
        print(reason, file=sys.stderr)
        print(json.dumps({"permission": "allow", "user_message": reason, "agent_message": reason}))
        return

    print(json.dumps({
        "permission": "deny",
        "user_message": DENY_REASON,
        "agent_message": DENY_REASON,
    }))


if __name__ == "__main__":
    main()
