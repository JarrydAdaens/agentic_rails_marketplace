"""Persist the advisor consult timeout using natural number input."""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))
from advisor_config import DEFAULT_CONSULT_TIMEOUT_SECONDS, config_path, load_advisor_config, update_advisor_config  # noqa: E402

CANCEL = {"cancel", "nevermind", "never mind", "abort", "back", "exit", "quit", "no"}
WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
TOKENS = sorted((*WORDS, "hundred", "thousand"), key=len, reverse=True)

def parse_words(value: str) -> int:
    remaining, parsed, total, current = value.lower().replace("-", "").replace(" ", ""), [], 0, 0
    while remaining:
        token = next((item for item in TOKENS if remaining.startswith(item)), None)
        if token is None: raise ValueError("use a positive number such as 123 or fourhundred")
        parsed.append(token); remaining = remaining[len(token):]
    for token in parsed:
        if token in WORDS: current += WORDS[token]
        elif token == "hundred": current = max(current, 1) * 100
        else: total += max(current, 1) * 1000; current = 0
    return total + current

def parse(value: str) -> int | None:
    choice = value.strip().lower()
    if choice in CANCEL: return None
    if choice == "default": return DEFAULT_CONSULT_TIMEOUT_SECONDS
    seconds = int(choice) if choice.isdigit() else parse_words(choice)
    if seconds <= 0: raise ValueError("consult timeout must be a positive number of seconds")
    return seconds

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--seconds", nargs="?", const=""); parser.add_argument("--workspace", default=os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd()); args = parser.parse_args(argv)
    try:
        current = load_advisor_config(args.workspace)
        if current.error: raise RuntimeError(current.error)
        if args.seconds is None or not args.seconds.strip():
            path = config_path(args.workspace)
            print(f"Consult timeout\nThe consult timeout is the maximum number of seconds Cursor waits for a full Codex advisor consult before it is hard-killed.\nCurrent: {current.consult_timeout_seconds} seconds\nDefault: {DEFAULT_CONSULT_TIMEOUT_SECONDS} seconds\n\nReply with a positive number (for example `123` or `fourhundred`), `default` to restore {DEFAULT_CONSULT_TIMEOUT_SECONDS} seconds, or `cancel` / `nevermind` to leave it unchanged.\nConfig file: {'FOUND' if path.is_file() else 'MISSING'}\nConfig path: {path}\nAdvanced manual fields include `health_timeout_seconds`, `enabled`, `model`, `effort`, and `fast`.")
            return 0
        seconds = parse(args.seconds)
        if seconds is None: print("Consult timeout change cancelled. No settings were changed."); return 0
        updated = update_advisor_config(args.workspace, consult_timeout_seconds=seconds)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Could not update advisor consult timeout: {exc}", file=sys.stderr); return 1
    print(f"Advisor consult timeout is now: {updated.consult_timeout_seconds} seconds, and is saved as your default for new sessions in this project.")
    return 0

if __name__ == "__main__": raise SystemExit(main())
