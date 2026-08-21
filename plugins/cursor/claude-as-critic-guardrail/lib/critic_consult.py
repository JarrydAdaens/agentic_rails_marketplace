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

"""Consult an adversarial, read-only Claude critic via the local claude CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from critic_config import (  # noqa: E402
    CONSULT_TIMEOUT_ENV_VAR,
    DEFAULT_CONSULT_TIMEOUT_SECONDS,
    CriticConfig,
    require_critic_config,
    resolve_consult_timeout,
)
from windows_runtime import resolve_cli  # noqa: E402

# Back-compat aliases kept so existing callers and tests keep working after the
# move to harness config.
MODEL = "opus"
TIMEOUT_ENV = CONSULT_TIMEOUT_ENV_VAR
DEFAULT_TIMEOUT_SECONDS = DEFAULT_CONSULT_TIMEOUT_SECONDS

FIELDS = ("task", "stage", "approach", "evidence", "question")
STAGES = ("planning", "stuck", "pivot-check", "completion-review")


def timeout_seconds(config: CriticConfig | None = None) -> int:
    return resolve_consult_timeout(config)


def validate(arguments: Any) -> dict[str, str]:
    if not isinstance(arguments, dict):
        raise ValueError("consult_critic arguments must be an object")
    missing = [key for key in FIELDS if not isinstance(arguments.get(key), str) or not arguments[key].strip()]
    if missing:
        raise ValueError("missing or empty required field(s): " + ", ".join(missing))
    if arguments["stage"] not in STAGES:
        raise ValueError(f"stage must be one of: {', '.join(STAGES)}; received: {arguments['stage']}")
    return {key: arguments[key].strip() for key in FIELDS}


def build_prompt(v: dict[str, str]) -> str:
    payload = "\n".join((
        f"TASK: {v['task']}", f"STAGE: {v['stage']}", f"PLAN/APPROACH: {v['approach']}",
        f"EVIDENCE: {v['evidence']}", f"QUESTION: {v['question']}",
    ))
    return f"""You are an adversarial senior engineering advisor reviewing a coding agent from another vendor. Find the flaw, missed edge case, simpler alternative, or misread requirement. Do not implement or modify files. Inspect files only to test material claims.

Every objection must state the problem, evidence, consequence, recommended correction, and whether work can continue. Label hypotheses and name the confirming test. Attack proposals to stop as hard as the code; endorsing a stop requires the strongest case for continuing and why it fails.

Otherwise answer in at most 120 words: strongest objection or clear survival verdict, 2-4 concrete weaknesses, and one check most likely to expose a problem. No preamble or praise.

Structured consultation:\n{payload}\n"""


def command(config: CriticConfig | None = None) -> list[str]:
    cfg = config or CriticConfig()
    return [
        *resolve_cli("claude"), "-p", "--model", cfg.model, "--effort", cfg.effort,
        "--permission-mode", "plan", "--tools", "Read,Grep,Glob", "--safe-mode",
        "--no-session-persistence", "--output-format", "text",
    ]


def classify_failure(stderr: str, model: str) -> str:
    """Turn a CLI failure into a reason a human can act on."""
    detail = stderr.strip() or "The Claude CLI exited without an error message."
    lowered = detail.lower()
    if any(term in lowered for term in ("not logged in", "authentication", "unauthorized", "sign in", "login required", "api key")):
        return "Claude authentication failed; sign in with the Claude CLI and retry. " + detail
    if any(term in lowered for term in ("quota", "credit", "usage limit", "rate limit", "billing")):
        return "Claude critic quota or credits exhausted. " + detail
    if any(term in lowered for term in ("model", "not available", "not found", "unsupported")):
        return f"Critic model {model} is unavailable for this account or Claude CLI version. " + detail
    return "Claude critic failed. " + detail


def describe_timeout(limit: int, partial: Any) -> str:
    message = (
        f"Claude critic timed out after {limit} seconds. Raise consult_timeout_seconds in "
        f"harness/claude-as-critic-guardrail/config.json, or set {CONSULT_TIMEOUT_ENV_VAR}, "
        "or send narrower evidence."
    )
    if isinstance(partial, bytes):
        partial = partial.decode("utf-8", "replace")
    if isinstance(partial, str) and partial.strip():
        message += " Claude output before the timeout: " + partial.strip()[-400:]
    return message


def workspace_root(workspace: str | None = None) -> str:
    return workspace or os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd()


def run_claude_prompt(
    prompt: str,
    *,
    config: CriticConfig | None = None,
    workspace: str | None = None,
    timeout: int | None = None,
) -> str:
    """Run one ephemeral, read-only Claude session and return its text output."""
    cfg = config or require_critic_config(workspace)
    limit = timeout if timeout is not None else timeout_seconds(cfg)
    try:
        completed = subprocess.run(
            command(cfg), input=prompt, capture_output=True,
            encoding="utf-8", errors="replace", cwd=workspace_root(workspace),
            timeout=limit, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(describe_timeout(limit, exc.stderr or exc.stdout)) from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start the Claude critic: {exc}") from exc
    if completed.returncode:
        raise RuntimeError(classify_failure(completed.stderr, cfg.model))
    text = completed.stdout.strip()
    if not text:
        raise RuntimeError("Claude critic returned no critique.")
    return text


def consult(arguments: Any, workspace: str | None = None) -> str:
    values = validate(arguments)
    config = require_critic_config(workspace)
    return run_claude_prompt(build_prompt(values), config=config, workspace=workspace)
