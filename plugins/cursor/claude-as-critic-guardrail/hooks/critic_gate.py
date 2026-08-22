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

"""preToolUse gate: deny writes only when critic health is online and no consult yet."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from critic_markers import BACKEND_LABEL, HEALTH_SKILL, has_marker, health_state, offline_reason
from critic_streams import force_utf8, read_hook_payload

_LIB = Path(__file__).resolve().parents[1] / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from critic_config import load_critic_config  # noqa: E402

DENY_REASON = (
    "Claude critic gate: consult the critic before the first write of this "
    "session. Run `uv run --no-project python ./scripts/launch.py "
    "./cli/consult_critic.py` and pipe a JSON object with task, stage, "
    "approach, evidence, and question to its stdin, then retry this write."
)


def _session_id(payload: dict) -> str:
    return str(payload.get("session_id") or payload.get("conversation_id") or "unknown")


def _reply(permission: str, message: str) -> str:
    return json.dumps({
        "permission": permission,
        "user_message": message,
        "agent_message": message,
    })


def _workspace(payload: dict) -> str | None:
    roots = payload.get("workspace_roots") or []
    return str(roots[0]) if roots else (str(payload.get("cwd")) if payload.get("cwd") else None)


def main() -> None:
    force_utf8()
    payload = read_hook_payload()
    if payload is None:
        sys.exit(0)

    if not load_critic_config(_workspace(payload)).enabled:
        message = "Claude critic is disabled in this project's harness config. Writes are allowed."
        print(_reply("allow", message))
        return

    session_id = _session_id(payload)
    if has_marker(session_id):
        sys.exit(0)

    state = health_state(session_id)

    if state == "pending":
        message = f"{BACKEND_LABEL} health pending — write gate fail-open until the probe finishes."
        print(message, file=sys.stderr)
        print(_reply("allow", message))
        return

    if state == "offline":
        message = (
            f"{BACKEND_LABEL} offline — {offline_reason(session_id)}. "
            f"Write gate disarmed. Retest with the {HEALTH_SKILL} skill."
        )
        print(message, file=sys.stderr)
        print(_reply("allow", message))
        return

    # online and not consulted
    print(_reply("deny", DENY_REASON))


if __name__ == "__main__":
    main()
