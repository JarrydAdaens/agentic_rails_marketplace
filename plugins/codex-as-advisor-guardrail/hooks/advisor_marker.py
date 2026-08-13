"""Record a completed consult_advisor for the current session."""
import json
import sys

from advisor_markers import marker_dir, marker_path


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    tool = str(payload.get("tool_name") or payload.get("tool") or "")
    if not (tool == "consult_advisor" or tool.endswith("consult_advisor")):
        return
    session = payload.get("session_id") or payload.get("conversation_id", "unknown")
    marker_dir().mkdir(parents=True, exist_ok=True)
    marker_path(session).touch()


if __name__ == "__main__":
    main()
