import json
import sys
from critic_markers import has_marker
from critic_streams import force_utf8, read_hook_payload

DENY = "Claude critic gate: call consult_critic with task, stage, approach, evidence, and question, then retry this write."


def main():
    force_utf8()
    payload = read_hook_payload()
    if payload is None: return
    session = payload.get("session_id") or payload.get("conversation_id", "unknown")
    if has_marker(session): return
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": DENY}}))


if __name__ == "__main__": main()
