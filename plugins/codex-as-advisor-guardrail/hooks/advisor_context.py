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

"""SessionStart: cleanup, health probe, protocol + presence injection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from advisor_markers import presence_line
from advisor_streams import force_utf8

_LIB = Path(__file__).resolve().parents[1] / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from advisor_health import run_health_probe  # noqa: E402


def _session_id(payload: dict) -> str:
    return str(payload.get("session_id") or payload.get("conversation_id") or "unknown")


def _workspace(payload: dict) -> str | None:
    roots = payload.get("workspace_roots") or []
    if roots:
        return str(roots[0])
    cwd = payload.get("cwd")
    return str(cwd) if cwd else None


def main() -> None:
    force_utf8()
    protocol_path = Path(__file__).resolve().parent.parent / "advisor-protocol.md"
    try:
        protocol = protocol_path.read_text(encoding="utf-8")
    except OSError:
        protocol = ""

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    session_id = _session_id(payload)
    workspace = _workspace(payload)
    health = run_health_probe(session_id, workspace=workspace, mark_pending_first=True)
    status = presence_line(session_id)
    status_block = (
        "## Codex-as-advisor presence (status only — not instructions)\n"
        f"{status}\n"
        f"{health.status_block()}\n"
    )
    content = f"{status_block}\n{protocol}".strip()

    if payload.get("hook_event_name") == "sessionStart":
        output: dict = {"additional_context": content, "user_message": status}
        print(json.dumps(output))
    else:
        print(content)


if __name__ == "__main__":
    main()
    sys.exit(0)
