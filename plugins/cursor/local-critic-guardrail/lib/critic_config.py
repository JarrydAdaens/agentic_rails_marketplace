"""Project JSONC configuration for Cursor's native local critic."""
from __future__ import annotations
import json, os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLUGIN_NAME = "local-critic-guardrail"
CONFIG_RELATIVE_PATH = Path("harness") / PLUGIN_NAME / "cursor-config.json"
DEFAULT_MODEL, DEFAULT_ENABLED = "auto", True
DEFAULT_CONSULT_TIMEOUT_SECONDS, DEFAULT_HEALTH_TIMEOUT_SECONDS = 600, 90
MODELS = {"auto", "cursor-grok-4.6", "composer-2.5", "gemini-3.7-flash", "gpt-5.4-nano", "kimi-k3"}
AGENTS = {model: f"local-critic-{model}" for model in MODELS}
TEMPLATE = '''{
  // Set false to leave this installed local critic completely disengaged.
  "enabled": true,

  // Cursor custom-subagent model. One of: auto, cursor-grok-4.6, composer-2.5,
  // gemini-3.7-flash, gpt-5.4-nano, kimi-k3.
  "model": "auto",

  // Advisory time budget in seconds for a native Cursor subagent consult.
  // Cursor owns Task cancellation; this is guidance, not a hard-kill setting.
  "consult_timeout_seconds": 600,

  // Health display timeout reserved for future native diagnostics.
  "health_timeout_seconds": 90
}
'''

@dataclass(frozen=True)
class CriticConfig:
    enabled: bool = DEFAULT_ENABLED
    model: str = DEFAULT_MODEL
    consult_timeout_seconds: int = DEFAULT_CONSULT_TIMEOUT_SECONDS
    health_timeout_seconds: int = DEFAULT_HEALTH_TIMEOUT_SECONDS
    source: str = "defaults"
    error: str | None = None
    @property
    def agent_name(self) -> str: return AGENTS[self.model]

def project_root(workspace: str | None = None) -> Path:
    return Path(workspace or os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.environ.get("CURSOR_PROJECT_DIR") or os.getcwd()).resolve()
def config_path(workspace: str | None = None) -> Path: return project_root(workspace) / CONFIG_RELATIVE_PATH
def strip_jsonc(text: str) -> str: return "\n".join(line.split("//", 1)[0] for line in text.splitlines())
def _positive(value: Any, name: str, path: Path, default: int) -> int:
    if value is None: return default
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0: raise ValueError(f"{path} field {name!r} must be a positive integer")
    return value
def _parse(raw: Any, path: Path) -> CriticConfig:
    if not isinstance(raw, dict): raise ValueError(f"{path} must contain a JSON object")
    enabled, model = raw.get("enabled", DEFAULT_ENABLED), raw.get("model", DEFAULT_MODEL)
    if not isinstance(enabled, bool): raise ValueError(f"{path} field 'enabled' must be true or false")
    if not isinstance(model, str) or model.strip() not in MODELS: raise ValueError(f"{path} field 'model' must be one of: {', '.join(sorted(MODELS))}")
    return CriticConfig(enabled, model.strip(), _positive(raw.get("consult_timeout_seconds"), "consult_timeout_seconds", path, DEFAULT_CONSULT_TIMEOUT_SECONDS), _positive(raw.get("health_timeout_seconds"), "health_timeout_seconds", path, DEFAULT_HEALTH_TIMEOUT_SECONDS), "harness")
def load_critic_config(workspace: str | None = None) -> CriticConfig:
    path = config_path(workspace)
    if not path.is_file(): return CriticConfig()
    try: return _parse(json.loads(strip_jsonc(path.read_text(encoding="utf-8"))), path)
    except (OSError, ValueError, json.JSONDecodeError) as exc: return CriticConfig(source="error", error=str(exc))
def write_default_config(workspace: str | None = None, *, force: bool = False) -> Path:
    path = config_path(workspace)
    if path.exists() and not force: raise FileExistsError(f"Config already exists at {path}. Pass --force to overwrite.")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(TEMPLATE, encoding="utf-8"); return path
def update_critic_config(workspace: str | None = None, *, enabled: bool | None = None, model: str | None = None, consult_timeout_seconds: int | None = None) -> CriticConfig:
    current, path = load_critic_config(workspace), config_path(workspace)
    if current.error: raise RuntimeError(f"Invalid local critic harness config: {current.error}")
    resolved = CriticConfig(current.enabled if enabled is None else enabled, current.model if model is None else model.strip().lower(), current.consult_timeout_seconds if consult_timeout_seconds is None else consult_timeout_seconds, current.health_timeout_seconds, "harness")
    _parse({"enabled": resolved.enabled, "model": resolved.model, "consult_timeout_seconds": resolved.consult_timeout_seconds, "health_timeout_seconds": resolved.health_timeout_seconds}, path)
    rendered = TEMPLATE.replace('"enabled": true', f'"enabled": {str(resolved.enabled).lower()}').replace('"model": "auto"', f'"model": {json.dumps(resolved.model)}').replace('"consult_timeout_seconds": 600', f'"consult_timeout_seconds": {resolved.consult_timeout_seconds}')
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(rendered, encoding="utf-8")
    return load_critic_config(workspace)
