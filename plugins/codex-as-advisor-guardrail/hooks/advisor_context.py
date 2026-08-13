"""Inject the advisor protocol at session start."""
import json
import sys
from pathlib import Path


def main() -> None:
    try:
        content = (Path(__file__).resolve().parent.parent / "advisor-protocol.md").read_text(encoding="utf-8")
    except OSError:
        return
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}
    print(json.dumps({"additional_context": content}) if payload.get("hook_event_name") == "sessionStart" else content)


if __name__ == "__main__":
    main()
