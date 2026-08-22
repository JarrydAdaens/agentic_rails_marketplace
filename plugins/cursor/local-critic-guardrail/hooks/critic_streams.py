"""Fail-open UTF-8 JSON hook payload reader."""
from __future__ import annotations
import json, sys
def force_utf8() -> None:
    for stream, encoding in ((sys.stdin, "utf-8-sig"), (sys.stdout, "utf-8"), (sys.stderr, "utf-8")):
        if hasattr(stream, "reconfigure"): stream.reconfigure(encoding=encoding, errors="replace")
def read_hook_payload() -> dict | None:
    try: raw = sys.stdin.read().lstrip("\ufeff")
    except OSError: return None
    try: payload = json.loads(raw) if raw.strip() else None
    except json.JSONDecodeError: return None
    return payload if isinstance(payload, dict) else None
