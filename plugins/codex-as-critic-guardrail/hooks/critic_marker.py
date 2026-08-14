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

"""Record a successful critic consult (MCP PostToolUse or Cursor afterShellExecution)."""

from __future__ import annotations

import json
import sys

from critic_markers import mark_consulted, mark_online, read_health
from critic_streams import force_utf8


def _session_id(payload: dict) -> str:
    return str(payload.get("session_id") or payload.get("conversation_id") or "unknown")


def _is_mcp_consult(payload: dict) -> bool:
    tool_name = str(payload.get("tool_name") or payload.get("tool") or "")
    return tool_name == "consult_critic" or tool_name.endswith("consult_critic")


def _is_cli_consult(payload: dict) -> bool:
    command = str(payload.get("command") or "")
    if "consult_critic.py" not in command and "consult_critic" not in command:
        return False
    # Prefer explicit success signals when the host provides them.
    if "exit_code" in payload:
        try:
            return int(payload["exit_code"]) == 0
        except (TypeError, ValueError):
            return False
    status = payload.get("status") or payload.get("result")
    if isinstance(status, str) and status.lower() in {"failed", "error", "failure"}:
        return False
    output = str(payload.get("output") or "")
    if "Codex critic" in output and ("failed" in output.lower() or "timed out" in output.lower()):
        return False
    return True


def main() -> None:
    force_utf8()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        sys.exit(0)

    if not isinstance(payload, dict):
        sys.exit(0)

    event = str(payload.get("hook_event_name") or "")
    if event == "afterShellExecution" or "command" in payload and not _is_mcp_consult(payload):
        if not _is_cli_consult(payload):
            sys.exit(0)
    elif not _is_mcp_consult(payload):
        sys.exit(0)

    session_id = _session_id(payload)
    mark_consulted(session_id)
    health = read_health(session_id) or {}
    mark_online(
        session_id,
        model=str(health.get("model") or ""),
        effort=str(health.get("effort") or ""),
        fast=bool(health.get("fast")) if isinstance(health.get("fast"), bool) else False,
    )


if __name__ == "__main__":
    main()
