"""Install this plugin's hooks into the user-level Cursor hooks.json."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
_PLUGIN = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(_PLUGIN / "lib"))
from user_hooks import install_user_hooks
def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--hooks-file"); args=parser.parse_args(argv)
    try: path, added=install_user_hooks(_PLUGIN, Path(args.hooks_file) if args.hooks_file else None)
    except (OSError, RuntimeError) as exc: print(f"Could not install advisor hooks: {exc}", file=sys.stderr); return 1
    print(f"Codex-as-advisor hooks installed ({added} entries)\nPath: {path}\nStart a new CLI session for the write gate to load."); return 0
if __name__ == "__main__": raise SystemExit(main())
