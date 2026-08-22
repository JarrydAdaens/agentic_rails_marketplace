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

"""preToolUse gate: deny writes until the advisor has been consulted this session.

Reads the hook payload from stdin. If no consult marker exists for the current
session, emits a deny decision so the executor self-corrects by consulting the
advisor MCP tool first. Marker files are created by advisor_marker.py.
"""

import json
import sys
from pathlib import Path

from advisor_markers import has_marker
from advisor_streams import force_utf8, read_hook_payload

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))
from advisor_config import load_advisor_config  # noqa: E402

DENY_REASON = (
    "Advisor gate: consult the advisor before the first write of this session. "
    "In Cursor, invoke the configured native local-advisor-* Task/Agent subagent. Supply the task, "
    "stage, approach, evidence, "
    "and question fields from the Advisor Protocol, then retry this edit."
)


def main() -> None:
    force_utf8()
    payload = read_hook_payload()
    if payload is None:
        sys.exit(0)

    session_id = payload.get("session_id") or payload.get("conversation_id") or "unknown"
    roots = payload.get("workspace_roots") or []
    config = load_advisor_config(str(roots[0]) if roots else payload.get("cwd"))
    if not config.enabled:
        print(json.dumps({"permission": "allow", "user_message": "Local advisor disabled for this project.", "agent_message": "Local advisor disabled for this project."}))
        return
    if has_marker(session_id):
        sys.exit(0)

    print(json.dumps({
        "permission": "deny",
        "user_message": DENY_REASON,
        "agent_message": DENY_REASON,
    }))


if __name__ == "__main__":
    main()
