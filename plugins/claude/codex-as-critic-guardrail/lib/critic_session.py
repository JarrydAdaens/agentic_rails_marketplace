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

"""Per-session consult and health markers for the Codex critic guardrail."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Literal

HealthState = Literal["pending", "online", "offline"]

MARKER_DIR_NAMES = ("codex-as-critic-guardrail-markers", "critic-guardrail-markers")
HEALTH_SKILL = "codex-critic-health"


def marker_dir() -> Path:
    return Path(tempfile.gettempdir()) / MARKER_DIR_NAMES[0]


def legacy_marker_dirs() -> list[Path]:
    return [Path(tempfile.gettempdir()) / name for name in MARKER_DIR_NAMES[1:]]


def marker_path(session_id: str) -> Path:
    return marker_dir() / f"critic-consulted-{session_id}"


def health_path(session_id: str) -> Path:
    return marker_dir() / f"critic-health-{session_id}.json"


def has_marker(session_id: str) -> bool:
    return marker_path(session_id).exists()


def mark_consulted(session_id: str) -> Path:
    directory = marker_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = marker_path(session_id)
    path.touch()
    return path


def clear_consulted(session_id: str) -> None:
    try:
        marker_path(session_id).unlink()
    except FileNotFoundError:
        pass


def read_health(session_id: str) -> dict[str, Any] | None:
    path = health_path(session_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def health_state(session_id: str) -> HealthState:
    payload = read_health(session_id)
    if not payload:
        return "pending"
    state = payload.get("state")
    if state in ("pending", "online", "offline"):
        return state  # type: ignore[return-value]
    return "pending"


def write_health(
    session_id: str,
    state: HealthState,
    *,
    reason: str = "",
    model: str = "",
    effort: str = "",
    fast: bool | None = None,
) -> Path:
    marker_dir().mkdir(parents=True, exist_ok=True)
    path = health_path(session_id)
    payload: dict[str, Any] = {
        "state": state,
        "reason": reason,
        "model": model,
        "effort": effort,
        "pid": os.getpid(),
    }
    if fast is not None:
        payload["fast"] = fast
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def mark_online(session_id: str, *, model: str, effort: str, fast: bool) -> Path:
    return write_health(
        session_id,
        "online",
        reason="health probe ok",
        model=model,
        effort=effort,
        fast=fast,
    )


def mark_offline(
    session_id: str,
    reason: str,
    *,
    model: str = "",
    effort: str = "",
    fast: bool | None = None,
) -> Path:
    return write_health(
        session_id,
        "offline",
        reason=reason,
        model=model,
        effort=effort,
        fast=fast,
    )


def mark_pending(session_id: str, *, model: str = "", effort: str = "", fast: bool | None = None) -> Path:
    return write_health(
        session_id,
        "pending",
        reason="health check running",
        model=model,
        effort=effort,
        fast=fast,
    )


def offline_reason(session_id: str) -> str:
    payload = read_health(session_id) or {}
    reason = payload.get("reason")
    return reason if isinstance(reason, str) and reason.strip() else "critic unavailable"


def format_status_block(
    *,
    result: str,
    model: str,
    effort: str,
    fast: bool,
    reason: str,
    gate: str,
) -> str:
    return (
        "Codex-as-critic health check\n"
        f"Result: {result}\n"
        f"Model: {model}\n"
        f"Effort: {effort}\n"
        f"Fast: {str(fast).lower()}\n"
        f"Reason: {reason}\n"
        f"Gate: {gate}"
    )


def presence_line(session_id: str | None = None) -> str:
    if not session_id:
        return "Codex-as-critic status unknown."
    state = health_state(session_id)
    payload = read_health(session_id) or {}
    model = payload.get("model") or "unknown"
    effort = payload.get("effort") or "unknown"
    fast = payload.get("fast")
    fast_text = str(fast).lower() if isinstance(fast, bool) else "unknown"
    if state == "online":
        return (
            f"Codex-as-critic online — model {model}, effort {effort}, fast {fast_text}."
        )
    if state == "offline":
        reason = offline_reason(session_id)
        return (
            f"Codex-as-critic offline — {reason}. Write gate disabled for this session. "
            f"Retest with the {HEALTH_SKILL} skill."
        )
    return (
        f"Codex-as-critic health pending — model {model}, effort {effort}, fast {fast_text}. "
        "Write gate is fail-open until the probe finishes."
    )
