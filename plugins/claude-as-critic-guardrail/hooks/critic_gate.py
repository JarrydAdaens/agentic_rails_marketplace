import json
import sys
from critic_markers import has_live_server, has_marker
from critic_streams import force_utf8

DENY = "Claude critic gate: call consult_critic with task, stage, approach, evidence, and question, then retry this write."
CURSOR_TOOL = "plugin-claude-as-critic-guardrail-claude-as-critic-guardrail:consult_critic"


def main():
    force_utf8()
    try: payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("Claude critic hook received invalid input; allowing the write.", file=sys.stderr); return
    if not isinstance(payload, dict): return
    session = payload.get("session_id") or payload.get("conversation_id", "unknown")
    if has_marker(session): return
    cursor = payload.get("hook_event_name") == "preToolUse"
    roots = payload.get("workspace_roots") or []
    workspace = roots[0] if roots else payload.get("cwd")
    host = "cursor" if cursor else "codex"
    if not has_live_server(host, workspace):
        reason = f"Claude critic gate is inactive because {host} has not registered consult_critic for this workspace. Enable and approve the plugin MCP server, then start a fresh session."
        print(reason, file=sys.stderr)
        if cursor: print(json.dumps({"permission": "allow", "user_message": reason, "agent_message": reason}))
        return
    if cursor:
        reason = f"{DENY} Use {CURSOR_TOOL}."; print(json.dumps({"permission": "deny", "user_message": reason, "agent_message": reason})); return
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": DENY}}))


if __name__ == "__main__": main()
