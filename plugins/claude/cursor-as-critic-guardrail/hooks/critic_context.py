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

"""SessionStart context injection: put the Critic Protocol into context.

A SessionStart hook's stdout is added to the session's context, so the
executor knows the consult contract without touching the target project's
CLAUDE.md. Missing protocol file exits silently — never block startup.
"""

import json
import sys
from pathlib import Path

from critic_streams import force_utf8, read_hook_payload


def main() -> None:
    force_utf8()
    protocol = Path(__file__).resolve().parent.parent / "critic-protocol.md"
    try:
        content = protocol.read_text(encoding="utf-8")
    except OSError:
        return

    payload = read_hook_payload() or {}

    if payload.get("hook_event_name") == "sessionStart":
        print(json.dumps({"additional_context": content}))
    else:
        print(content)


if __name__ == "__main__":
    main()
    sys.exit(0)
