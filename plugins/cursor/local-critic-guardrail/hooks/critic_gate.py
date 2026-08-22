"""Deny guarded writes until the native local critic has completed."""
from __future__ import annotations
import json, sys
from pathlib import Path
from critic_markers import has_marker
from critic_streams import force_utf8, read_hook_payload
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from critic_config import load_critic_config
DENY_REASON = "Critic gate: consult the configured native local-critic-* Task/Agent subagent before the first write, using the Local Critic Protocol, then retry this edit."
def main() -> None:
    force_utf8(); payload = read_hook_payload()
    if payload is None: return
    roots = payload.get("workspace_roots") or []
    config = load_critic_config(str(roots[0]) if roots else payload.get("cwd"))
    if not config.enabled or config.error: return
    session_id = payload.get("session_id") or payload.get("conversation_id") or "unknown"
    if not has_marker(session_id): print(json.dumps({"permission": "deny", "user_message": DENY_REASON, "agent_message": DENY_REASON}))
if __name__ == "__main__": main()
