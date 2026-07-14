"""PostToolUse marker: record that the advisor was consulted this session.

Fires on consult_advisor completions (plain or MCP-namespaced, e.g.
mcp__advisor-codex-guardrail__consult_advisor). Touches a per-session marker
file that advisor_gate.py checks before allowing apply_patch.
"""

import json
import sys

from advisor_markers import marker_dir, marker_path


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = str(payload.get("tool_name") or payload.get("tool") or "")
    if not (tool_name == "consult_advisor" or tool_name.endswith("consult_advisor")):
        sys.exit(0)

    session_id = payload.get("session_id", "unknown")
    marker_dir().mkdir(parents=True, exist_ok=True)
    marker_path(session_id).touch()


if __name__ == "__main__":
    main()
