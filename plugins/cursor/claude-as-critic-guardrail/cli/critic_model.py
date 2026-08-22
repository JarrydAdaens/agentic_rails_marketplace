"""Parse Claude-style model/effort choices and persist critic defaults."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))

from critic_config import EFFORTS, load_critic_config, update_critic_config  # noqa: E402

MODELS = {"1": "sonnet", "2": "sonnet", "3": "fable", "4": "opus", "5": "haiku"}
EFFORT_CODES = {"a": "low", "b": "medium", "c": "high", "d": "xhigh", "e": "max"}
MODEL_ID = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")


def select_menu() -> str:
    return """Select model
Switch between Claude models. Your pick becomes the default for new sessions. For other/previous model names, specify with --model.

  1. Default (recommended)  Sonnet 5 · Efficient for routine tasks
  2. Sonnet                 Sonnet 5 · Efficient for routine tasks
  3. Fable                  Fable 5 · Most capable for your hardest and longest-running tasks · Requires usage credits
  4. Opus                   Opus 5 · Best for everyday, complex tasks · ~2× usage vs Sonnet
  5. Haiku                  Haiku 4.5 · Fastest for quick answers

Select effort
  a. Low                    Minimal reasoning for simple, well-scoped work
  b. Medium                 Balanced reasoning for ordinary implementation work
  c. High                   Thorough reasoning for complex work (recommended)
  d. XHigh                  Deep reasoning for difficult design and debugging
  e. Max                    Maximum available reasoning for exceptional problems

Examples: `opus high`, `haiku low`, `fable low`, `2a`, or `5e`."""


def parse_selection(value: str, current_model: str, current_effort: str) -> tuple[str, str]:
    compact = value.strip().lower()
    if len(compact) == 2 and compact[0] in MODELS and compact[1] in EFFORT_CODES:
        return MODELS[compact[0]], EFFORT_CODES[compact[1]]
    parts = compact.replace(",", " ").split()
    model = current_model
    effort = current_effort
    for part in parts:
        if part in MODELS:
            model = MODELS[part]
        elif part in EFFORT_CODES:
            effort = EFFORT_CODES[part]
        elif part in EFFORTS:
            effort = part
        elif MODEL_ID.fullmatch(part):
            model = part
        else:
            raise ValueError(f"unrecognized model/effort selection: {part}")
    return model, effort


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", nargs="?", const="")
    parser.add_argument("--workspace", default=os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd())
    args = parser.parse_args(argv)
    if args.model is None or not args.model.strip():
        print(select_menu())
        return 0
    try:
        current = load_critic_config(args.workspace)
        if current.error:
            raise RuntimeError(current.error)
        model, effort = parse_selection(args.model, current.model, current.effort)
        updated = update_critic_config(args.workspace, model=model, effort=effort)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Could not update critic model: {exc}", file=sys.stderr)
        return 1
    print(f"Critic is now model: {updated.model.title()}, effort: {updated.effort.title()}, and is saved as your default for new sessions in this project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
