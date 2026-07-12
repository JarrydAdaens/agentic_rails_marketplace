"""PreToolUse gate: deny Write/Edit tools until the advisor has been consulted this session.

Reads the hook payload from stdin. If no consult marker exists for the current
session, emits a permissionDecision deny so the executor self-corrects by
consulting the advisor subagent first. Marker files are created by
advisor_marker.py (PostToolUse on Task/Agent).
"""

import json
import sys

from advisor_markers import has_marker

DENY_REASON = (
    "Advisor gate: consult the advisor before the first write of this session. "
    "In Claude, invoke advisor-guardrail:advisor with Task/Agent; in Codex, invoke "
    "consult_advisor. Use the consult payload format "
    "from the Advisor Protocol in your context (TASK / STAGE / "
    "PLAN-APPROACH / EVIDENCE / QUESTION), then retry this edit."
)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # malformed input: fail open rather than block all writes

    session_id = payload.get("session_id", "unknown")
    if has_marker(session_id):
        sys.exit(0)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": DENY_REASON,
        }
    }))


if __name__ == "__main__":
    main()
