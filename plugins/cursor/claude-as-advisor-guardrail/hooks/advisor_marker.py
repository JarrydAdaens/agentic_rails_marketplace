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

"""Record a successful advisor consult (afterShellExecution on cli/consult_advisor.py)."""

from __future__ import annotations

import sys

from advisor_markers import marker_dir, marker_path
from advisor_streams import force_utf8, read_hook_payload


def _is_cli_consult(payload: dict) -> bool:
    command = str(payload.get("command") or "")
    if "consult_advisor.py" not in command and "consult_advisor" not in command:
        return False
    if "exit_code" in payload:
        try:
            return int(payload["exit_code"]) == 0
        except (TypeError, ValueError):
            return False
    status = payload.get("status") or payload.get("result")
    if isinstance(status, str) and status.lower() in {"failed", "error", "failure"}:
        return False
    output = str(payload.get("output") or "")
    if "Claude advisor" in output and ("failed" in output.lower() or "timed out" in output.lower()):
        return False
    return True


def main() -> None:
    force_utf8()
    payload = read_hook_payload()
    if payload is None:
        sys.exit(0)

    if not _is_cli_consult(payload):
        sys.exit(0)

    session = payload.get("session_id") or payload.get("conversation_id", "unknown")
    marker_dir().mkdir(parents=True, exist_ok=True)
    marker_path(session).touch()


if __name__ == "__main__":
    main()
