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

"""Bounded health probe for the Codex advisor backend."""

from __future__ import annotations

import os
from dataclasses import dataclass

from advisor_config import (
    AdvisorConfig,
    load_advisor_config,
    require_advisor_config,
    resolve_health_timeout,
)
from advisor_consult import run_codex_prompt
from advisor_session import (
    clear_consulted,
    format_status_block,
    mark_offline,
    mark_online,
    mark_pending,
)
from windows_runtime import resolve_cli

HEALTH_PROMPT = (
    "Reply with exactly the six characters ADVISOR_OK and nothing else. "
    "Do not read or modify files."
)


def health_timeout_seconds(config: AdvisorConfig | None = None) -> int:
    return resolve_health_timeout(config)

@dataclass(frozen=True)
class HealthResult:
    online: bool
    model: str
    effort: str
    fast: bool
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
            fast=self.fast,
            reason=self.reason,
            gate=self.gate,
        )


def _codex_reachable() -> None:
    resolve_cli("codex")


def run_health_probe(
    session_id: str,
    *,
    workspace: str | None = None,
    mark_pending_first: bool = True,
) -> HealthResult:
    """Probe configured Codex model; update session health markers."""
    loaded = load_advisor_config(workspace)
    if os.environ.get("CODEX_ADVISOR_SKIP_HEALTH") == "1":
        mark_online(
            session_id,
            model=loaded.model,
            effort=loaded.effort,
            fast=loaded.fast,
        )
        return HealthResult(
            online=True,
            model=loaded.model,
            effort=loaded.effort,
            fast=loaded.fast,
            reason="health probe skipped (CODEX_ADVISOR_SKIP_HEALTH=1)",
        )

    if loaded.error:
        result = HealthResult(
            online=False,
            model=loaded.model,
            effort=loaded.effort,
            fast=loaded.fast,
            reason=f"invalid harness config: {loaded.error}",
        )
        mark_offline(
            session_id,
            result.reason,
            model=result.model,
            effort=result.effort,
            fast=result.fast,
        )
        return result

    config = AdvisorConfig(
        model=loaded.model,
        effort=loaded.effort,
        fast=loaded.fast,
        consult_timeout_seconds=loaded.consult_timeout_seconds,
        health_timeout_seconds=loaded.health_timeout_seconds,
        source=loaded.source,
    )
    if mark_pending_first:
        mark_pending(
            session_id,
            model=config.model,
            effort=config.effort,
            fast=config.fast,
        )

    try:
        _codex_reachable()
        # require_advisor_config raises only on invalid harness; defaults are fine.
        require_advisor_config(workspace)
        output = run_codex_prompt(
            HEALTH_PROMPT,
            config=config,
            workspace=workspace,
            timeout=health_timeout_seconds(config),
        )
    except Exception as exc:  # probe must never raise into sessionStart
        result = HealthResult(
            online=False,
            model=config.model,
            effort=config.effort,
            fast=config.fast,
            reason=str(exc),
        )
        mark_offline(
            session_id,
            result.reason,
            model=result.model,
            effort=result.effort,
            fast=result.fast,
        )
        return result

    if "ADVISOR_OK" not in output:
        result = HealthResult(
            online=False,
            model=config.model,
            effort=config.effort,
            fast=config.fast,
            reason=f"unexpected health response: {output[:200]}",
        )
        mark_offline(
            session_id,
            result.reason,
            model=result.model,
            effort=result.effort,
            fast=result.fast,
        )
        return result

    clear_consulted(session_id)
    mark_online(
        session_id,
        model=config.model,
        effort=config.effort,
        fast=config.fast,
    )
    return HealthResult(
        online=True,
        model=config.model,
        effort=config.effort,
        fast=config.fast,
        reason="health probe ok",
    )
