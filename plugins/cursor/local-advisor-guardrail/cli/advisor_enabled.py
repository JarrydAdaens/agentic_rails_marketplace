from __future__ import annotations
import argparse, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from advisor_config import update_advisor_config
TRUE, FALSE = {"true","yes","enabled","enable","on","engage","engaged"}, {"false","no","disabled","disable","off","disengage","disengaged"}
def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument("--enabled",required=True); p.add_argument("--workspace",default=os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd()); a=p.parse_args(); value=a.enabled.lower().strip()
 try:
  if value in TRUE: enabled=True
  elif value in FALSE: enabled=False
  else: raise ValueError("use enabled/disabled, true/false, yes/no, on/off, or engage/disengage")
  update_advisor_config(a.workspace,enabled=enabled)
 except (OSError,RuntimeError,ValueError) as exc: print(f"Could not update local advisor enabled state: {exc}",file=sys.stderr); return 1
 print("Local advisor is now: Enabled, it will give advice to your agent." if enabled else "Local advisor is now: Disabled, it will not do anything."); return 0
if __name__ == "__main__": raise SystemExit(main())
