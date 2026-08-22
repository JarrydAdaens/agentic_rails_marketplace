from __future__ import annotations
import argparse, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from advisor_config import load_advisor_config, update_advisor_config
MODELS={"a":"auto","b":"cursor-grok-4.6","c":"composer-2.5","d":"gemini-3.7-flash","e":"gpt-5.4-nano","f":"kimi-k3"}; CANCEL={"0","cancel","abort","back","exit","quit","no"}
def menu(current:str)->str:
 def tag(value:str)->str:return " (Current)" if value==current else ""
 return f"""Select local advisor model
The advisor is a native Cursor custom subagent. Cursor chooses each model's own default effort.
Current selection: {current}

  0. Cancel
  a. Auto{tag('auto')}
  b. Cursor Grok 4.6{tag('cursor-grok-4.6')}
  c. Composer 2.5{tag('composer-2.5')}
  d. Gemini 3.7 Flash{tag('gemini-3.7-flash')}
  e. GPT-5.4-Nano{tag('gpt-5.4-nano')}
  f. Kimi-K3{tag('kimi-k3')}

No effort selector is available: Cursor applies the selected model's native defaults. Type cancel to leave settings unchanged."""
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--model",nargs="?",const="");p.add_argument("--workspace",default=os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd());a=p.parse_args()
 try:
  current=load_advisor_config(a.workspace)
  if current.error:raise RuntimeError(current.error)
  if a.model is None or not a.model.strip():print(menu(current.model));return 0
  choice=a.model.strip().lower()
  if choice in CANCEL:print("Model selection cancelled. No settings were changed.");return 0
  model=MODELS.get(choice,choice)
  updated=update_advisor_config(a.workspace,model=model)
 except (OSError,RuntimeError,ValueError) as exc:print(f"Could not update local advisor model: {exc}",file=sys.stderr);return 1
 print(f"Local advisor is now model: {updated.model}, and is saved as your default for new sessions in this project.");return 0
if __name__ == "__main__":raise SystemExit(main())
