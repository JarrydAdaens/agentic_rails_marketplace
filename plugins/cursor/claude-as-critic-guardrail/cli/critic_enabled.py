"""Persist the Claude critic enabled state for one project."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))

from critic_config import update_critic_config  # noqa: E402

TRUE_WORDS = {"true", "yes", "y", "on", "enable", "enabled", "engage", "1"}
FALSE_WORDS = {"false", "no", "n", "off", "disable", "disabled", "disengage", "0"}


def parse_enabled(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_WORDS:
        return True
    if normalized in FALSE_WORDS:
        return False
    raise ValueError("expected enabled/disabled, true/false, yes/no, on/off, or engage/disengage")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enabled", required=True)
    parser.add_argument("--workspace", default=os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd())
    args = parser.parse_args(argv)
    try:
        enabled = parse_enabled(args.enabled)
        update_critic_config(args.workspace, enabled=enabled)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Could not update critic enabled state: {exc}", file=sys.stderr)
        return 1
    if enabled:
        print("Critic is now: Enabled, it will give criticism to your agent.")
    else:
        print("Critic is now: Disabled, it will not do anything.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
