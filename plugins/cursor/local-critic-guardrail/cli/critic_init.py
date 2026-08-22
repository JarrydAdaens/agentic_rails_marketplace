from __future__ import annotations
import argparse, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from critic_config import CONFIG_RELATIVE_PATH, write_default_config
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--workspace", default=os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd()); p.add_argument("--force", action="store_true"); a=p.parse_args()
    try: path=write_default_config(a.workspace, force=a.force)
    except (OSError, FileExistsError) as exc: print(str(exc), file=sys.stderr); return 1
    print(f"Local critic config initialized\nPath: {path}\nRelative: {CONFIG_RELATIVE_PATH.as_posix()}\nThe generated JSONC documents enabled state, model, and both timeout values."); return 0
if __name__ == "__main__": raise SystemExit(main())
