from __future__ import annotations
import argparse,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
from advisor_config import DEFAULT_CONSULT_TIMEOUT_SECONDS,config_path,load_advisor_config,update_advisor_config
CANCEL={"cancel","nevermind","never mind","abort","back","exit","quit","no"}
def value(text:str)->int|None:
 t=text.strip().lower()
 if t in CANCEL:return None
 if t=="default":return DEFAULT_CONSULT_TIMEOUT_SECONDS
 if not t.isdigit() or int(t)<=0:raise ValueError("use a positive number of seconds or default")
 return int(t)
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--seconds",nargs="?",const="");p.add_argument("--workspace",default=os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd());a=p.parse_args();current=load_advisor_config(a.workspace)
 if current.error:print(current.error,file=sys.stderr);return 1
 if a.seconds is None or not a.seconds.strip():
  path=config_path(a.workspace);print(f"Consult timeout\nThis is an advisory time budget for Cursor's native local subagent; plugins cannot hard-kill Cursor Task calls.\nCurrent: {current.consult_timeout_seconds} seconds\nDefault: {DEFAULT_CONSULT_TIMEOUT_SECONDS} seconds\nReply with a positive number, default, cancel, or nevermind.\nConfig file: {'FOUND' if path.is_file() else 'MISSING'}\nConfig path: {path}\nAdvanced manual field: health_timeout_seconds");return 0
 try: seconds=value(a.seconds)
 except ValueError as exc:print(f"Could not update local advisor consult timeout: {exc}",file=sys.stderr);return 1
 if seconds is None:print("Consult timeout change cancelled. No settings were changed.");return 0
 updated=update_advisor_config(a.workspace,consult_timeout_seconds=seconds);print(f"Local advisor consult timeout is now: {updated.consult_timeout_seconds} seconds, and is saved as your default for new sessions in this project.");return 0
if __name__ == "__main__":raise SystemExit(main())
