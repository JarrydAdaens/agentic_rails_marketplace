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

from critic_markers import HEALTH_SKILL, has_marker, health_state, offline_reason
from critic_streams import force_utf8, read_hook_payload

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))

from critic_config import load_critic_config  # noqa: E402

DENY = (
    "Critic gate: consult the critic before the first write of this session. "
    "Pipe a JSON object with task, stage, approach, evidence, and question to "
    "cli/consult_critic.py via the plugin launcher (see Critic Protocol), then retry."
)


def _session_id(payload: dict) -> str:
    return str(payload.get("session_id") or payload.get("conversation_id") or "unknown")


def _workspace(payload: dict) -> str | None:
    roots = payload.get("workspace_roots") or []
    if roots:
        return str(roots[0])
    cwd = payload.get("cwd")
    return str(cwd) if cwd else None


def _reply(permission: str, message: str) -> str:
    return json.dumps({
        "permission": permission,
        "user_message": message,
        "agent_message": message,
    })


def main() -> None:
    force_utf8()
    payload = read_hook_payload()
    if payload is None:
        sys.exit(0)

    session_id = _session_id(payload)
    config = load_critic_config(_workspace(payload))
    if not config.enabled:
        message = "Codex-as-critic disabled for this project — write gate disengaged."
        print(_reply("allow", message))
        return
    if has_marker(session_id):
        sys.exit(0)

    state = health_state(session_id)

    if state == "pending":
        message = "Codex-as-critic health pending — write gate fail-open until the probe finishes."
        print(message, file=sys.stderr)
        print(_reply("allow", message))
        return

    if state == "offline":
        message = (
            f"Codex-as-critic offline — {offline_reason(session_id)}. "
            f"Write gate disarmed. Retest with the {HEALTH_SKILL} skill."
        )
        print(message, file=sys.stderr)
        print(_reply("allow", message))
        return

    # online and not consulted
    print(_reply("deny", DENY))


if __name__ == "__main__":
    main()
