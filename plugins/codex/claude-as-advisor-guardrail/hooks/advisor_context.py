import json
from pathlib import Path

from advisor_streams import force_utf8, read_hook_payload


def main():
    force_utf8()
    try: content = (Path(__file__).resolve().parent.parent / "advisor-protocol.md").read_text(encoding="utf-8")
    except OSError: return
    payload = read_hook_payload() or {}
    print(json.dumps({"additional_context": content}) if payload.get("hook_event_name") == "sessionStart" else content)


if __name__ == "__main__": main()
