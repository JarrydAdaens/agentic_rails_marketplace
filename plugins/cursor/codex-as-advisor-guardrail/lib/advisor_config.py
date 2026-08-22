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

"""Project harness config for the Codex advisor (model / effort / enabled / timeouts)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLUGIN_NAME = "codex-as-advisor-guardrail"
CONFIG_RELATIVE_PATH = Path("harness") / PLUGIN_NAME / "config.json"

DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_EFFORT = "high"
DEFAULT_FAST = False
DEFAULT_ENABLED = True
DEFAULT_CONSULT_TIMEOUT_SECONDS = 1800
DEFAULT_HEALTH_TIMEOUT_SECONDS = 90

CONSULT_TIMEOUT_ENV_VAR = "CODEX_ADVISOR_TIMEOUT_SECONDS"
HEALTH_TIMEOUT_ENV_VAR = "CODEX_ADVISOR_HEALTH_TIMEOUT_SECONDS"

EFFORTS = ("minimal", "low", "medium", "high", "xhigh", "max", "ultra")

# Written by codex-advisor-init. JSONC: // comments allowed; the loader strips them.
DEFAULT_CONFIG_TEMPLATE = """\
{
  // Set false to leave this installed advisor completely disengaged.
  "enabled": true,

  // Codex model id passed to `codex exec --model`.
  // Copy an exact id your account can use (e.g. gpt-5.6-sol, gpt-5.4-mini).
  "model": "gpt-5.6-sol",

  // Reasoning effort for consults and health probes.
  // One of: low, medium, high, xhigh, max, ultra.
  // `minimal` remains accepted only for existing config compatibility.
  "effort": "high",

  // When true, requests Codex fast service tier (`service_tier=fast`).
  // Ignored harmlessly if the model or account does not support it.
  "fast": false,

  // Maximum wall-clock seconds a full advisor consult may run before it is killed.
  // Override with env CODEX_ADVISOR_TIMEOUT_SECONDS when set.
  "consult_timeout_seconds": 1800,

  // Maximum wall-clock seconds for the session-start / manual health probe.
  // This is separate from the consult limit. Override with
  // CODEX_ADVISOR_HEALTH_TIMEOUT_SECONDS when set.
  "health_timeout_seconds": 90
}
"""


@dataclass(frozen=True)
class AdvisorConfig:
    enabled: bool = DEFAULT_ENABLED
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    fast: bool = DEFAULT_FAST
    consult_timeout_seconds: int = DEFAULT_CONSULT_TIMEOUT_SECONDS
    health_timeout_seconds: int = DEFAULT_HEALTH_TIMEOUT_SECONDS
    source: str = "defaults"  # defaults | harness | error
    error: str | None = None

    def status_line(self) -> str:
        base = (
            f"enabled {self.enabled}, model {self.model}, effort {self.effort}, fast {str(self.fast).lower()}, "
            f"consult_timeout {self.consult_timeout_seconds}s, "
            f"health_timeout {self.health_timeout_seconds}s"
        )
        if self.error:
            return f"{base} (config error: {self.error})"
        if self.source == "harness":
            return base
        return f"{base} (built-in defaults)"


def project_root(workspace: str | None = None) -> Path:
    selected = (
        workspace
        or os.environ.get("AGENTIC_RAILS_WORKSPACE")
        or os.environ.get("CURSOR_PROJECT_DIR")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.getcwd()
    )
    return Path(selected).resolve()


def config_path(workspace: str | None = None) -> Path:
    return project_root(workspace) / CONFIG_RELATIVE_PATH


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments outside of JSON strings."""
    result: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    escape = False
    while i < n:
        ch = text[i]
        if in_string:
            result.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            i += 2
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _positive_int(value: Any, field: str, path: Path, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path} field {field!r} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{path} field {field!r} must be a positive integer")
    return value


def _parse_config_object(raw: Any, path: Path) -> AdvisorConfig:
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object")
    model = raw.get("model", DEFAULT_MODEL)
    effort = raw.get("effort", DEFAULT_EFFORT)
    fast = raw.get("fast", DEFAULT_FAST)
    enabled = raw.get("enabled", DEFAULT_ENABLED)
    if not isinstance(enabled, bool):
        raise ValueError(f"{path} field 'enabled' must be true or false")
    if not isinstance(model, str) or not model.strip():
        raise ValueError(f"{path} field 'model' must be a non-empty string")
    if not isinstance(effort, str) or effort.strip() not in EFFORTS:
        raise ValueError(
            f"{path} field 'effort' must be one of: {', '.join(EFFORTS)}"
        )
    if not isinstance(fast, bool):
        raise ValueError(f"{path} field 'fast' must be a boolean")
    consult_timeout = _positive_int(
        raw.get("consult_timeout_seconds"),
        "consult_timeout_seconds",
        path,
        DEFAULT_CONSULT_TIMEOUT_SECONDS,
    )
    health_timeout = _positive_int(
        raw.get("health_timeout_seconds"),
        "health_timeout_seconds",
        path,
        DEFAULT_HEALTH_TIMEOUT_SECONDS,
    )
    return AdvisorConfig(
        enabled=enabled,
        model=model.strip(),
        effort=effort.strip(),
        fast=fast,
        consult_timeout_seconds=consult_timeout,
        health_timeout_seconds=health_timeout,
        source="harness",
    )


def load_advisor_config(workspace: str | None = None) -> AdvisorConfig:
    """Load harness config or fall back to built-in defaults.

    Missing file is not an error. Malformed JSON or invalid fields return a
    config marked with source='error' and the built-in defaults for safe status
    display; callers that must fail hard should check ``config.error``.
    """
    path = config_path(workspace)
    if not path.is_file():
        return AdvisorConfig()
    try:
        text = strip_jsonc(path.read_text(encoding="utf-8"))
        raw = json.loads(text)
        return _parse_config_object(raw, path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return AdvisorConfig(source="error", error=str(exc))


def require_advisor_config(workspace: str | None = None) -> AdvisorConfig:
    """Like load_advisor_config, but raises when the harness file is invalid."""
    config = load_advisor_config(workspace)
    if config.error:
        raise RuntimeError(f"Invalid advisor harness config: {config.error}")
    return config


def resolve_consult_timeout(config: AdvisorConfig | None = None) -> int:
    """Env override, then harness config, then built-in default."""
    try:
        configured = int(os.environ.get(CONSULT_TIMEOUT_ENV_VAR, ""))
    except ValueError:
        configured = 0
    if configured > 0:
        return configured
    if config is not None:
        return config.consult_timeout_seconds
    return DEFAULT_CONSULT_TIMEOUT_SECONDS


def resolve_health_timeout(config: AdvisorConfig | None = None) -> int:
    try:
        configured = int(os.environ.get(HEALTH_TIMEOUT_ENV_VAR, ""))
    except ValueError:
        configured = 0
    if configured > 0:
        return configured
    if config is not None:
        return config.health_timeout_seconds
    return DEFAULT_HEALTH_TIMEOUT_SECONDS


def write_default_config(workspace: str | None = None, *, force: bool = False) -> Path:
    """Write the commented default harness config; refuse overwrite unless force."""
    path = config_path(workspace)
    if path.exists() and not force:
        raise FileExistsError(
            f"Config already exists at {path}. Pass --force to overwrite, or edit it in place."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
    return path.resolve()


def update_advisor_config(
    workspace: str | None = None, *, enabled: bool | None = None,
    model: str | None = None, effort: str | None = None,
    consult_timeout_seconds: int | None = None,
) -> AdvisorConfig:
    """Validate and persist user-controlled settings as JSONC."""
    path = config_path(workspace)
    current = load_advisor_config(workspace)
    if current.error:
        raise RuntimeError(f"Invalid advisor harness config: {current.error}")
    resolved_model = model.strip() if model is not None else current.model
    resolved_effort = effort.strip() if effort is not None else current.effort
    resolved_enabled = current.enabled if enabled is None else enabled
    resolved_consult_timeout = (
        current.consult_timeout_seconds
        if consult_timeout_seconds is None else consult_timeout_seconds
    )
    if not resolved_model:
        raise ValueError("model must be a non-empty identifier")
    if resolved_effort not in EFFORTS:
        raise ValueError(f"effort must be one of: {', '.join(EFFORTS)}")
    candidate = {
        "enabled": resolved_enabled, "model": resolved_model, "effort": resolved_effort,
        "fast": current.fast, "consult_timeout_seconds": resolved_consult_timeout,
        "health_timeout_seconds": current.health_timeout_seconds,
    }
    _parse_config_object(candidate, path)
    rendered = "{\n"
    rendered += "  // Set false to leave this installed advisor completely disengaged.\n"
    rendered += f'  "enabled": {str(resolved_enabled).lower()},\n\n'
    rendered += "  // Codex model id passed to `codex exec --model`.\n"
    rendered += f'  "model": {json.dumps(resolved_model)},\n\n'
    rendered += "  // Reasoning effort: low, medium, high, xhigh, max, or ultra.\n"
    rendered += f'  "effort": {json.dumps(resolved_effort)},\n\n'
    rendered += "  // Legacy optional fast service-tier setting.\n"
    rendered += f'  "fast": {str(current.fast).lower()},\n\n'
    rendered += "  // Maximum wall-clock seconds for a full advisor consult.\n"
    rendered += f'  "consult_timeout_seconds": {resolved_consult_timeout},\n\n'
    rendered += "  // Maximum wall-clock seconds for the session-start / manual health probe.\n"
    rendered += f'  "health_timeout_seconds": {current.health_timeout_seconds}\n'
    rendered += "}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return require_advisor_config(workspace)
