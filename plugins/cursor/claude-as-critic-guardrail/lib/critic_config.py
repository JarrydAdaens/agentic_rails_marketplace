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

"""Project harness config for the Claude critic (model / effort / timeouts)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLUGIN_NAME = "claude-as-critic-guardrail"
CONFIG_RELATIVE_PATH = Path("harness") / PLUGIN_NAME / "config.json"

DEFAULT_MODEL = "opus"
DEFAULT_EFFORT = "high"
DEFAULT_CONSULT_TIMEOUT_SECONDS = 600
DEFAULT_HEALTH_TIMEOUT_SECONDS = 90

CONSULT_TIMEOUT_ENV_VAR = "CLAUDE_CRITIC_TIMEOUT_SECONDS"
HEALTH_TIMEOUT_ENV_VAR = "CLAUDE_CRITIC_HEALTH_TIMEOUT_SECONDS"

# The levels `claude --effort` accepts. The Claude CLI has no fast-tier flag,
# so this plugin's config carries no `fast` field.
EFFORTS = ("low", "medium", "high", "xhigh", "max")

# Written by claude-critic-init. JSONC: // comments allowed; the loader strips them.
DEFAULT_CONFIG_TEMPLATE = """\
{
  // Model alias or id passed to `claude --model`.
  // An alias tracks the latest of that family (opus, sonnet, fable);
  // a full id (e.g. claude-opus-5) pins it.
  "model": "opus",

  // Reasoning effort for consults and health probes.
  // One of: low, medium, high, xhigh, max
  "effort": "high",

  // Wall-clock seconds for a full critic consult before hard kill.
  // Override with env CLAUDE_CRITIC_TIMEOUT_SECONDS when set.
  "consult_timeout_seconds": 600,

  // Wall-clock seconds for the session-start / skill health probe.
  // Override with env CLAUDE_CRITIC_HEALTH_TIMEOUT_SECONDS when set.
  "health_timeout_seconds": 90
}
"""


@dataclass(frozen=True)
class CriticConfig:
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    consult_timeout_seconds: int = DEFAULT_CONSULT_TIMEOUT_SECONDS
    health_timeout_seconds: int = DEFAULT_HEALTH_TIMEOUT_SECONDS
    source: str = "defaults"  # defaults | harness | error
    error: str | None = None

    def status_line(self) -> str:
        base = (
            f"model {self.model}, effort {self.effort}, "
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


def _parse_config_object(raw: Any, path: Path) -> CriticConfig:
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object")
    model = raw.get("model", DEFAULT_MODEL)
    effort = raw.get("effort", DEFAULT_EFFORT)
    if not isinstance(model, str) or not model.strip():
        raise ValueError(f"{path} field 'model' must be a non-empty string")
    if not isinstance(effort, str) or effort.strip() not in EFFORTS:
        raise ValueError(f"{path} field 'effort' must be one of: {', '.join(EFFORTS)}")
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
    return CriticConfig(
        model=model.strip(),
        effort=effort.strip(),
        consult_timeout_seconds=consult_timeout,
        health_timeout_seconds=health_timeout,
        source="harness",
    )


def load_critic_config(workspace: str | None = None) -> CriticConfig:
    """Load harness config or fall back to built-in defaults.

    A missing file is not an error: the harness seam is optional, and a project
    that never adopts it gets the defaults. Malformed JSON or an invalid field
    returns a config marked with source='error' carrying the built-in defaults,
    so status display stays safe; callers that must fail hard check
    ``config.error``.
    """
    path = config_path(workspace)
    if not path.is_file():
        return CriticConfig()
    try:
        text = strip_jsonc(path.read_text(encoding="utf-8"))
        raw = json.loads(text)
        return _parse_config_object(raw, path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return CriticConfig(source="error", error=str(exc))


def require_critic_config(workspace: str | None = None) -> CriticConfig:
    """Like load_critic_config, but raises when the harness file is invalid."""
    config = load_critic_config(workspace)
    if config.error:
        raise RuntimeError(f"Invalid critic harness config: {config.error}")
    return config


def resolve_consult_timeout(config: CriticConfig | None = None) -> int:
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


def resolve_health_timeout(config: CriticConfig | None = None) -> int:
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
