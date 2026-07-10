"""PostToolUse marker: record that the advisor subagent was consulted this session.

Fires on Task/Agent tool completions. When the invoked subagent is the advisor
(plain or plugin-namespaced), touches a per-session marker file that
advisor_gate.py checks before allowing Write/Edit tools.
"""

import json
import sys

from advisor_markers import marker_dir, marker_path


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    subagent = str(tool_input.get("subagent_type") or "")
    if subagent != "advisor" and not subagent.endswith(":advisor"):
        sys.exit(0)

    session_id = payload.get("session_id", "unknown")
    marker_dir().mkdir(parents=True, exist_ok=True)
    marker_path(session_id).touch()


if __name__ == "__main__":
    main()
