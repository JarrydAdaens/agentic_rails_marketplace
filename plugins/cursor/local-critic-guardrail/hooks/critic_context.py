from __future__ import annotations
import json, sys
from pathlib import Path
from critic_streams import force_utf8, read_hook_payload
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from critic_config import load_critic_config
def main() -> None:
    force_utf8(); payload = read_hook_payload() or {}; protocol = Path(__file__).resolve().parents[1] / "advisor-protocol.md"
    try: content = protocol.read_text(encoding="utf-8")
    except OSError: return
    roots = payload.get("workspace_roots") or []; config = load_critic_config(str(roots[0]) if roots else payload.get("cwd"))
    if config.error:
        content = f"Local critic configuration is invalid ({config.error}). No consultation gate is active."
    elif not config.enabled:
        content = "Local critic is disabled for this project. No consultation gate is active."
    else:
        content += f"\n\nCursor selection: invoke native Task/Agent subagent `{config.agent_name}`. Advisory budget: {config.consult_timeout_seconds}s."
    print(json.dumps({"additional_context": content}) if payload.get("hook_event_name") == "sessionStart" else content)
if __name__ == "__main__": main()
