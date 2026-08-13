"""Deny the first write only when the matching advisor MCP is available."""
import json
import sys

from advisor_markers import has_live_server, has_marker
from advisor_streams import force_utf8

DENY = "Codex advisor gate: call consult_advisor with task, stage, approach, evidence, and question, then retry this write."
CURSOR_TOOL = "plugin-codex-as-advisor-guardrail-codex-as-advisor-guardrail:consult_advisor"
UNAVAILABLE = f"Codex advisor gate is inactive because Cursor has not registered {CURSOR_TOOL}. Install and enable the plugin, approve its MCP server, and start a fresh session."


def main() -> None:
    force_utf8()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("Codex advisor hook received invalid input; allowing the write.", file=sys.stderr)
        return
    if not isinstance(payload, dict):
        return
    session_id = payload.get("session_id") or payload.get("conversation_id", "unknown")
    if has_marker(session_id):
        return
    if payload.get("hook_event_name") == "preToolUse":
        roots = payload.get("workspace_roots") or []
        workspace = roots[0] if roots else payload.get("cwd")
        if not has_live_server("cursor", workspace):
            print(UNAVAILABLE, file=sys.stderr)
            print(json.dumps({"permission": "allow", "user_message": UNAVAILABLE, "agent_message": UNAVAILABLE}))
            return
        reason = f"{DENY} Use {CURSOR_TOOL}."
        print(json.dumps({"permission": "deny", "user_message": reason, "agent_message": reason}))
        return
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": DENY}}))


if __name__ == "__main__":
    main()
