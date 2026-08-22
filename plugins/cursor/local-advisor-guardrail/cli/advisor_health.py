from __future__ import annotations
import argparse, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from advisor_config import config_path, load_advisor_config
def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument("--workspace",default=os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd()); a=p.parse_args(); config=load_advisor_config(a.workspace); path=config_path(a.workspace)
 ready = config.error is None and (Path(__file__).resolve().parents[1] / "agents" / f"{config.agent_name}.md").is_file()
 print(f"Local advisor health check\nResult: {'ONLINE' if ready and config.enabled else 'OFFLINE'}\nModel: {config.model}\nAgent: {config.agent_name}\nReason: {config.error or ('disabled by project config' if not config.enabled else 'native Cursor custom subagent is available')}\nGate: {'armed (next write requires consult)' if ready and config.enabled else 'disarmed (writes allowed)'}\nConfig file: {'FOUND' if path.is_file() else 'MISSING'}\nConfig path: {path}\nManual fields: enabled, model, consult_timeout_seconds, health_timeout_seconds")
 return 0 if ready and config.enabled else 1
if __name__ == "__main__": raise SystemExit(main())
