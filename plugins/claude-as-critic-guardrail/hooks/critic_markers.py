from __future__ import annotations
import ctypes
import json
import os
import tempfile
from pathlib import Path

PLUGIN_NAME = "claude-as-critic-guardrail"


def marker_dir(): return Path(tempfile.gettempdir()) / f"{PLUGIN_NAME}-markers"
def marker_path(session_id): return marker_dir() / f"critic-consulted-{session_id}"
def has_marker(session_id): return marker_path(session_id).exists()
def _workspace(value): return os.path.normcase(os.path.abspath(value or ""))


def _process_is_running(pid):
    if os.name != "nt":
        try: os.kill(pid, 0); return True
        except OSError: return False
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not handle: return False
    try:
        code = ctypes.c_ulong()
        return bool(ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally: ctypes.windll.kernel32.CloseHandle(handle)


def server_path(pid=None): return marker_dir() / f"mcp-server-{pid or os.getpid()}.json"


def mark_server_ready(host, workspace):
    marker_dir().mkdir(parents=True, exist_ok=True)
    server_path().write_text(json.dumps({"pid": os.getpid(), "host": host, "workspace": _workspace(workspace)}), encoding="utf-8")


def clear_server_ready():
    try: server_path().unlink()
    except OSError: pass


def has_live_server(host, workspace):
    if not marker_dir().is_dir(): return False
    expected = _workspace(workspace)
    for path in marker_dir().glob("mcp-server-*.json"):
        try:
            state = json.loads(path.read_text(encoding="utf-8")); alive = _process_is_running(int(state["pid"]))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError): state, alive = {}, False
        if not alive:
            try: path.unlink()
            except OSError: pass
        elif state.get("host") == host and state.get("workspace") == expected: return True
    return False
