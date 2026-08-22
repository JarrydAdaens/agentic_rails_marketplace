from __future__ import annotations
from critic_markers import marker_dir, marker_path
from critic_streams import force_utf8, read_hook_payload
def main() -> None:
    force_utf8(); payload = read_hook_payload()
    if payload is None: return
    tool = str(payload.get("tool_name") or payload.get("tool") or "")
    input = payload.get("tool_input") or payload.get("input") or {}
    subagent = str(input.get("subagent_type") or "")
    if tool in ("Task", "Agent", "") and subagent.startswith("local-critic-"):
        session_id = payload.get("session_id") or payload.get("conversation_id") or "unknown"
        marker_dir().mkdir(parents=True, exist_ok=True); marker_path(session_id).touch()
if __name__ == "__main__": main()
