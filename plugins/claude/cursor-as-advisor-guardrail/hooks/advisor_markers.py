# Copyright 2026 Jarryd Adaens
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Per-session marker paths for Cursor advisor consultation hooks."""

from __future__ import annotations

import ctypes
import json
import os
import tempfile
from pathlib import Path

MARKER_DIR_NAMES = ("cursor-as-advisor-guardrail-markers",)


def marker_dir() -> Path:
    return Path(tempfile.gettempdir()) / MARKER_DIR_NAMES[0]


def legacy_marker_dirs() -> list[Path]:
    return [Path(tempfile.gettempdir()) / name for name in MARKER_DIR_NAMES[1:]]


def marker_path(session_id: str) -> Path:
    return marker_dir() / f"advisor-consulted-{session_id}"


def has_marker(session_id: str) -> bool:
    return marker_path(session_id).exists()


def _workspace(value: str | None) -> str:
    return os.path.normcase(os.path.abspath(value or ""))


def _process_is_running(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def server_path(pid: int | None = None) -> Path:
    return marker_dir() / f"mcp-server-{pid or os.getpid()}.json"


def mark_server_ready(host: str, workspace: str | None) -> None:
    marker_dir().mkdir(parents=True, exist_ok=True)
    server_path().write_text(json.dumps({"pid": os.getpid(), "host": host, "workspace": _workspace(workspace)}), encoding="utf-8")


def clear_server_ready() -> None:
    try:
        server_path().unlink()
    except OSError:
        pass


def has_live_server(host: str, workspace: str | None) -> bool:
    if not marker_dir().is_dir():
        return False
    expected = _workspace(workspace)
    for path in marker_dir().glob("mcp-server-*.json"):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            alive = _process_is_running(int(state["pid"]))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            state, alive = {}, False
        if not alive:
            try:
                path.unlink()
            except OSError:
                pass
        elif state.get("host") == host and state.get("workspace") == expected:
            return True
    return False
