"""Parse Codex model/effort choices and persist advisor defaults."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))

from advisor_config import EFFORTS, load_advisor_config, update_advisor_config  # noqa: E402

MODELS = {"1": "gpt-5.6-sol", "2": "gpt-5.6-terra", "3": "gpt-5.6-luna", "4": "gpt-5.5", "5": "gpt-5.4", "6": "gpt-5.4-mini"}
EFFORT_CODES = {"a": "low", "b": "medium", "c": "high", "d": "xhigh", "e": "max", "f": "ultra"}
EFFORT_NAMES = {"low": "Low", "medium": "Medium", "high": "High", "xhigh": "Extra High", "max": "Max", "ultra": "Ultra"}
MODEL_ID = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")
CANCEL_WORDS = {"0", "cancel", "abort", "back", "exit", "quit", "no"}


def select_menu(current_model: str, current_effort: str) -> str:
    def current(value: str, selected: str) -> str:
        return " (Current)" if value == selected else ""

    return f"""Select model
Switch between Codex models. Your pick becomes the default for new sessions. For other model names, specify with --model.
Current selection: {current_model.upper()} / {EFFORT_NAMES.get(current_effort, current_effort.title())}

  0. Cancel
  1. GPT-5.6-Sol{current('gpt-5.6-sol', current_model)}
  2. GPT-5.6-Terra{current('gpt-5.6-terra', current_model)}
  3. GPT-5.6-Luna{current('gpt-5.6-luna', current_model)}
  4. GPT-5.5{current('gpt-5.5', current_model)}
  5. GPT-5.4{current('gpt-5.4', current_model)}
  6. GPT-5.4-Mini{current('gpt-5.4-mini', current_model)}

Select effort
  a. Low{current('low', current_effort)}              Fast, lightweight reasoning for simple work
  b. Medium{current('medium', current_effort)}           Balanced reasoning for routine implementation
  c. High{current('high', current_effort)}             Thorough reasoning for complex work (recommended)
  d. Extra High{current('xhigh', current_effort)}       Deep reasoning for difficult design and debugging
  e. Max{current('max', current_effort)}              Maximum reasoning for exceptional problems
  f. Ultra{current('ultra', current_effort)}            Highest available reasoning for the hardest work

Examples: `gpt-5.6-sol high`, `gpt-5.6-luna low`, `2a`, or `6f`. Type `cancel` to leave settings unchanged."""


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
    model, effort = current_model, current_effort
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
    print(f"Advisor is now model: {updated.model.upper()}, effort: {EFFORT_NAMES.get(updated.effort, updated.effort.title())}, and is saved as your default for new sessions in this project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
