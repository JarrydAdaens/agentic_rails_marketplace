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

"""Shared marker-path helper for the codex-as-critic-guardrail hooks.

Consult markers are per-session flags: critic_marker.py creates one when the
critic MCP tool completes, critic_gate.py checks for it before allowing the
session's first write, and critic_cleanup.py removes stale ones. They live in
the system temp directory — session IDs are globally unique, and keeping
markers out of the target project means the guardrail needs no .gitignore
entry there.
"""

from __future__ import annotations

import ctypes
import json
import os
import tempfile
from pathlib import Path

# Marker directories this plugin has used. The first is current; the rest are
# names it shipped under before, kept so cleanup can still sweep markers left in
# the temp directory by an older install.
MARKER_DIR_NAMES = ("codex-as-critic-guardrail-markers", "critic-guardrail-markers")


def marker_dir() -> Path:
    return Path(tempfile.gettempdir()) / MARKER_DIR_NAMES[0]


def legacy_marker_dirs() -> list[Path]:
    return [Path(tempfile.gettempdir()) / name for name in MARKER_DIR_NAMES[1:]]


def marker_path(session_id: str) -> Path:
    return marker_dir() / f"critic-consulted-{session_id}"


def server_state_path(pid: int | None = None) -> Path:
    return marker_dir() / f"mcp-server-{pid or os.getpid()}.json"


def _normalized_workspace(workspace: str | None) -> str:
    return os.path.normcase(os.path.abspath(workspace)) if workspace else ""


def mark_server_ready(host: str = "unknown", workspace: str | None = None) -> Path:
    marker_dir().mkdir(parents=True, exist_ok=True)
    state = server_state_path()
    state.write_text(
        json.dumps({
            "pid": os.getpid(),
            "host": host,
            "workspace": _normalized_workspace(workspace),
        }),
        encoding="utf-8",
    )
    return state


def clear_server_ready() -> None:
    try:
        server_state_path().unlink()
    except FileNotFoundError:
        pass


def _process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        process_query_limited_information = 0x1000
        still_active = 259
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            return bool(
                ctypes.windll.kernel32.GetExitCodeProcess(
                    handle, ctypes.byref(exit_code)
                )
                and exit_code.value == still_active
            )
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except (OSError, PermissionError):
        return False
    return True


def has_live_server(host: str, workspace: str | None) -> bool:
    expected_workspace = _normalized_workspace(workspace)
    if not expected_workspace:
        return False
    directory = marker_dir()
    if not directory.is_dir():
        return False
    for state in directory.glob("mcp-server-*.json"):
        try:
            payload = json.loads(state.read_text(encoding="utf-8"))
            pid = int(payload["pid"])
            matches = (
                payload.get("host") == host
                and payload.get("workspace") == expected_workspace
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            pid = -1
            matches = False
        if matches and _process_is_running(pid):
            return True
        if _process_is_running(pid):
            continue
        try:
            state.unlink()
        except OSError:
            pass
    return False


def has_marker(session_id: str) -> bool:
    return marker_path(session_id).exists()
