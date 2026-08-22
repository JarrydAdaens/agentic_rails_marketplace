"""Parse Claude-style model/effort choices and persist advisor defaults."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))

from advisor_config import EFFORTS, load_advisor_config, update_advisor_config  # noqa: E402

MODELS = {"1": "haiku", "2": "sonnet", "3": "opus", "4": "fable"}
EFFORT_CODES = {"b": "low", "c": "medium", "d": "high", "e": "xhigh", "f": "max"}
MODEL_ID = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")
CANCEL_WORDS = {"0", "a", "cancel", "abort", "back", "exit", "quit", "no"}


def select_menu(current_model: str, current_effort: str) -> str:
    def current(value: str, selected: str) -> str:
        return " (Current)" if value == selected else ""

    return f"""Select model
Switch between Claude models. Your pick becomes the default for new sessions. For other/previous model names, specify with --model.
Current selection: {current_model.title()} / {current_effort.title()}

  0. Cancel
  1. Haiku{current('haiku', current_model)}                 Haiku 4.5 · Fastest for quick answers
  2. Sonnet{current('sonnet', current_model)}                Sonnet 5 · Efficient for routine tasks
  3. Opus{current('opus', current_model)}                  Opus 5 · Best for everyday, complex tasks · ~2× usage vs Sonnet
  4. Fable{current('fable', current_model)}                 Fable 5 · Most capable for your hardest and longest-running tasks · Requires usage credits

Select effort
  a. Cancel
  b. Low{current('low', current_effort)}                    Minimal reasoning for simple, well-scoped work
  c. Medium{current('medium', current_effort)}                 Balanced reasoning for ordinary implementation work
  d. High{current('high', current_effort)}                   Thorough reasoning for complex work (recommended)
  e. XHigh{current('xhigh', current_effort)}                  Deep reasoning for difficult design and debugging
  f. Max{current('max', current_effort)}                    Maximum available reasoning for exceptional problems

Examples: `opus high`, `haiku low`, `fable low`, `2b`, or `4f`. Type `cancel` to leave settings unchanged."""


def parse_selection(value: str, current_model: str, current_effort: str) -> tuple[str, str] | None:
    compact = value.strip().lower()
    if compact in CANCEL_WORDS:
        return None
    if len(compact) == 2 and compact[0] in MODELS and compact[1] in EFFORT_CODES:
        return MODELS[compact[0]], EFFORT_CODES[compact[1]]
    parts = compact.replace(",", " ").split()
    if any(part in CANCEL_WORDS for part in parts):
        if len(parts) == 1:
            return None
        raise ValueError("cancel cannot be combined with a model or effort selection")
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
    try:
        current = load_advisor_config(args.workspace)
        if current.error:
            raise RuntimeError(current.error)
        if args.model is None or not args.model.strip():
            print(select_menu(current.model, current.effort))
            return 0
        selected = parse_selection(args.model, current.model, current.effort)
        if selected is None:
            print("Model selection cancelled. No settings were changed.")
            return 0
        model, effort = selected
        updated = update_advisor_config(args.workspace, model=model, effort=effort)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Could not update advisor model: {exc}", file=sys.stderr)
        return 1
    print(f"Advisor is now model: {updated.model.title()}, effort: {updated.effort.title()}, and is saved as your default for new sessions in this project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
