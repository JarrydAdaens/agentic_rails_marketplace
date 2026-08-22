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

"""SessionStart context injection: put the Advisor Protocol into context.

A SessionStart hook's stdout is added to the session's context, which replaces
the installer-era step of appending the protocol to the target project's
CLAUDE.md. Missing protocol file exits silently — never block startup.
"""

import json
import sys
from pathlib import Path

from advisor_streams import force_utf8, read_hook_payload

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))
from advisor_config import load_advisor_config  # noqa: E402


def main() -> None:
    force_utf8()
    protocol = Path(__file__).resolve().parent.parent / "advisor-protocol.md"
    try:
        content = protocol.read_text(encoding="utf-8")
        payload = read_hook_payload() or {}
        roots = payload.get("workspace_roots") or []
        config = load_advisor_config(str(roots[0]) if roots else payload.get("cwd"))
        if not config.enabled:
            content = "Local advisor is disabled for this project. No consultation gate is active."
        else:
            content += (
                f"\n\nCursor selection: invoke native Task/Agent subagent `{config.agent_name}` "
                f"for this consult. Its configured advisory budget is {config.consult_timeout_seconds}s."
            )
        if payload.get("hook_event_name") == "sessionStart":
            print(json.dumps({"additional_context": content}))
        else:
            print(content)
    except OSError:
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
