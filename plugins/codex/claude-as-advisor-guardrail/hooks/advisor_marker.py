import sys

from advisor_markers import marker_dir, marker_path
from advisor_streams import force_utf8, read_hook_payload


def _is_cli_consult(payload):
    command = str(payload.get("command") or "")
    if "consult_advisor.py" not in command and "consult_advisor" not in command:
        return False
    if "exit_code" in payload:
        try:
            return int(payload["exit_code"]) == 0
        except (TypeError, ValueError):
            return False
    return True


def main():
    force_utf8()
    payload = read_hook_payload()
    if payload is None: return
    if not _is_cli_consult(payload): return
    session = payload.get("session_id") or payload.get("conversation_id", "unknown")
    marker_dir().mkdir(parents=True, exist_ok=True); marker_path(session).touch()


if __name__ == "__main__": main()
