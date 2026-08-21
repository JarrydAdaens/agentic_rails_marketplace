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

"""Bounded health probe for the Claude critic backend."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from critic_config import CriticConfig, load_critic_config, resolve_health_timeout  # noqa: E402
from critic_consult import run_claude_prompt  # noqa: E402
from critic_session import (  # noqa: E402
    clear_consulted,
    format_status_block,
    mark_offline,
    mark_online,
    mark_pending,
)
from windows_runtime import resolve_cli  # noqa: E402

HEALTH_PROMPT = (
    "Reply with exactly CRITIC_OK and nothing else. "
    "Do not read or modify files."
)
HEALTH_TOKEN = "CRITIC_OK"
SKIP_HEALTH_ENV_VAR = "CLAUDE_CRITIC_SKIP_HEALTH"


def health_timeout_seconds(config: CriticConfig | None = None) -> int:
    return resolve_health_timeout(config)


@dataclass(frozen=True)
class HealthResult:
    online: bool
    model: str
    effort: str
    reason: str

    @property
    def gate(self) -> str:
        if self.online:
            return "armed (next write requires consult)"
        return "disarmed (writes allowed)"

    def status_block(self) -> str:
        return format_status_block(
            result="ONLINE" if self.online else "OFFLINE",
            model=self.model,
            effort=self.effort,
            reason=self.reason,
            gate=self.gate,
        )


def _offline(session_id: str, config: CriticConfig, reason: str) -> HealthResult:
    result = HealthResult(online=False, model=config.model, effort=config.effort, reason=reason)
    mark_offline(session_id, reason, model=result.model, effort=result.effort)
    return result


def run_health_probe(
    session_id: str,
    *,
    workspace: str | None = None,
    mark_pending_first: bool = True,
) -> HealthResult:
    """Probe the configured Claude model and update this session's health markers.

    Never raises: sessionStart calls this, and a probe that throws would take
    the whole hook down and leave the gate in an unreadable state.
    """
    loaded = load_critic_config(workspace)

    if os.environ.get(SKIP_HEALTH_ENV_VAR) == "1":
        mark_online(session_id, model=loaded.model, effort=loaded.effort)
        return HealthResult(
            online=True,
            model=loaded.model,
            effort=loaded.effort,
            reason=f"health probe skipped ({SKIP_HEALTH_ENV_VAR}=1)",
        )

    if loaded.error:
        return _offline(session_id, loaded, f"invalid harness config: {loaded.error}")

    config = CriticConfig(
        model=loaded.model,
        effort=loaded.effort,
        consult_timeout_seconds=loaded.consult_timeout_seconds,
        health_timeout_seconds=loaded.health_timeout_seconds,
        source=loaded.source,
    )
    if mark_pending_first:
        mark_pending(session_id, model=config.model, effort=config.effort)

    try:
        resolve_cli("claude")
        output = run_claude_prompt(
            HEALTH_PROMPT,
            config=config,
            workspace=workspace,
            timeout=health_timeout_seconds(config),
        )
    except Exception as exc:  # noqa: BLE001 - the probe must never raise into sessionStart
        return _offline(session_id, config, str(exc))

    if HEALTH_TOKEN not in output:
        return _offline(session_id, config, f"unexpected health response: {output[:200]}")

    # A fresh online verdict re-arms the gate: whatever consult happened before
    # this probe was against a backend we had not confirmed.
    clear_consulted(session_id)
    mark_online(session_id, model=config.model, effort=config.effort)
    return HealthResult(
        online=True, model=config.model, effort=config.effort, reason="health probe ok"
    )
