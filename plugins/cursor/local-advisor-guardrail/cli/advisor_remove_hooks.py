"""Remove local advisor hooks from the user-level Cursor hooks.json."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
_PLUGIN=Path(__file__).resolve().parents[1]; sys.path.insert(0, str(_PLUGIN / "lib"))
from user_hooks import remove_user_hooks
def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--hooks-file"); args=parser.parse_args(argv)
    try: path, removed=remove_user_hooks(_PLUGIN, Path(args.hooks_file) if args.hooks_file else None)
    except (OSError, RuntimeError) as exc: print(f"Could not remove local advisor hooks: {exc}", file=sys.stderr); return 1
    print(f"Local-advisor hooks removed ({removed} entries)\nPath: {path}\nStart a new Cursor CLI session for the change to take effect."); return 0
if __name__ == "__main__": raise SystemExit(main())
