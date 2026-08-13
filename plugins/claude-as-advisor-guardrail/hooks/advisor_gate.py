import json
import os
import sys
from advisor_markers import has_live_server, has_marker
from advisor_streams import force_utf8

DENY = "Claude advisor gate: call consult_advisor with task, stage, approach, evidence, and question, then retry this write."
CURSOR_TOOL = "plugin-claude-as-advisor-guardrail-claude-as-advisor-guardrail:consult_advisor"


def main():
    force_utf8()
    try: payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("Claude advisor hook received invalid input; allowing the write.", file=sys.stderr); return
    if not isinstance(payload, dict): return
    session = payload.get("session_id") or payload.get("conversation_id", "unknown")
    if has_marker(session): return
    cursor = payload.get("hook_event_name") == "preToolUse"
    roots = payload.get("workspace_roots") or []
    workspace = roots[0] if roots else payload.get("cwd")
    host = "cursor" if cursor else "codex"
    if not has_live_server(host, workspace):
        reason = f"Claude advisor gate is inactive because {host} has not registered consult_advisor for this workspace. Enable and approve the plugin MCP server, then start a fresh session."
        print(reason, file=sys.stderr)
        if cursor: print(json.dumps({"permission": "allow", "user_message": reason, "agent_message": reason}))
        return
    if cursor:
        reason = f"{DENY} Use {CURSOR_TOOL}."
        print(json.dumps({"permission": "deny", "user_message": reason, "agent_message": reason})); return
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": DENY}}))


if __name__ == "__main__": main()
