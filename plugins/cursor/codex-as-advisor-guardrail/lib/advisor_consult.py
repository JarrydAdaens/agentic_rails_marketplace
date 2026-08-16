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

"""Ephemeral Codex consult shared by Claude MCP and Cursor CLI transports."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from advisor_config import (
    CONSULT_TIMEOUT_ENV_VAR,
    AdvisorConfig,
    DEFAULT_CONSULT_TIMEOUT_SECONDS,
    require_advisor_config,
    resolve_consult_timeout,
)
from windows_runtime import resolve_cli

PLUGIN_VERSION = "1.1.0"

# Back-compat aliases for tests and MCP re-exports
DEFAULT_TIMEOUT_SECONDS = DEFAULT_CONSULT_TIMEOUT_SECONDS
TIMEOUT_ENV_VAR = CONSULT_TIMEOUT_ENV_VAR

FIELDS = ("task", "stage", "approach", "evidence", "question")
STAGES = ("planning", "stuck", "pivot-check", "completion-review")

FIELD_DESCRIPTIONS = {
    "task": "One-paragraph statement of the overall task, in your own words.",
    "stage": "Where you are in the task: planning, stuck, pivot-check, or completion-review.",
    "approach": "The plan you are about to follow, or the approach you actually took.",
    "evidence": (
        "Concrete file paths, error messages, test output, and constraints you "
        "discovered. Thin evidence produces thin advice."
    ),
    "question": "The specific decision or verdict you want the advisor to rule on.",
}

HARD_FAILURE_HINTS = (
    "not logged in",
    "authentication",
    "unauthorized",
    "sign in",
    "login required",
    "quota",
    "credit",
    "usage limit",
    "rate limit",
    "billing",
    "model",
    "not available",
    "not found",
    "unsupported",
)


def timeout_seconds(config: AdvisorConfig | None = None) -> int:
    return resolve_consult_timeout(config)


def validate_arguments(arguments: Any) -> dict[str, str]:
    if not isinstance(arguments, dict):
        raise ValueError("consult_advisor arguments must be an object")
    missing = [
        name for name in FIELDS
        if not isinstance(arguments.get(name), str) or not arguments[name].strip()
    ]
    if missing:
        raise ValueError("missing or empty required field(s): " + ", ".join(missing))
    if arguments["stage"] not in STAGES:
        raise ValueError(
            f"stage must be one of: {', '.join(STAGES)}; received: {arguments['stage']}"
        )
    return {name: arguments[name].strip() for name in FIELDS}


def build_prompt(values: dict[str, str]) -> str:
    payload = (
        f"TASK: {values['task']}\nSTAGE: {values['stage']}\n"
        f"PLAN/APPROACH: {values['approach']}\nEVIDENCE: {values['evidence']}\n"
        f"QUESTION: {values['question']}"
    )
    return f"""You are a senior reviewer and planner advising a coding agent from another vendor. Be constructive, candid, and practical. Return exactly one of: a plan, a course correction, or a completion verdict. Do not implement or modify files. Inspect repository files only to verify relevant claims.

Never raise a concern without a forward path. Label speculation and name the cheap check that settles it. If the executor is circling, say so and give 2-4 concrete options in order. Recommending a stop requires concrete evidence, the strongest case for continuing, alternatives tried and untried, and why no other work can proceed.

You are the senior engineering voice in this exchange — "someone more senior should decide" is not available to you. Keep risk language concrete. Prefer unblockers over vetoes.

Otherwise respond in at most 120 words: (1) the recommended plan, course correction, or completion verdict in one sentence, (2) the 2-4 concrete next moves or risks that matter most, each with a forward path, (3) the one check most likely to settle the open question before proceeding. No preamble, no praise padding, and do not restate the task. If information is missing, identify it in one line rather than guessing.

Structured consultation:
{payload}
"""



def command(config: AdvisorConfig | None = None) -> list[str]:
    cfg = config or AdvisorConfig()
    argv = [
        *resolve_cli("codex"),
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--model",
        cfg.model,
        "-c",
        f'model_reasoning_effort="{cfg.effort}"',
    ]
    if cfg.fast:
        argv.extend(["-c", 'service_tier="fast"'])
    argv.append("-")
    return argv


def classify_failure(stderr: str, model: str) -> str:
    detail = stderr.strip() or "Codex exited without an error message."
    lowered = detail.lower()
    if any(
        term in lowered
        for term in ("not logged in", "authentication", "unauthorized", "sign in", "login required")
    ):
        return "Codex authentication failed; sign in with the Codex CLI and retry. " + detail
    if any(term in lowered for term in ("quota", "credit", "usage limit", "rate limit", "billing")):
        return "Codex advisor quota or credits exhausted. " + detail
    if any(term in lowered for term in ("model", "not available", "not found", "unsupported")):
        return f"Advisor model {model} is unavailable for this account or Codex version. " + detail
    return "Codex advisor failed. " + detail


def is_hard_failure_message(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in HARD_FAILURE_HINTS)


def describe_timeout(limit: int, partial: Any) -> str:
    message = (
        f"Codex advisor timed out after {limit} seconds. Raise consult_timeout_seconds in "
        f"harness/codex-as-advisor-guardrail/config.json, or set {TIMEOUT_ENV_VAR}, "
        "or send narrower evidence."
    )
    if isinstance(partial, bytes):
        partial = partial.decode("utf-8", "replace")
    if isinstance(partial, str) and partial.strip():
        message += " Codex output before the timeout: " + partial.strip()[-400:]
    return message


def workspace_root(workspace: str | None = None) -> str:
    return workspace or os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd()


def run_codex_prompt(
    prompt: str,
    *,
    config: AdvisorConfig | None = None,
    workspace: str | None = None,
    timeout: int | None = None,
) -> str:
    cfg = config or require_advisor_config(workspace)
    limit = timeout if timeout is not None else timeout_seconds(cfg)
    root = workspace_root(workspace)
    try:
        completed = subprocess.run(
            command(cfg),
            input=prompt,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            cwd=root,
            timeout=limit,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(describe_timeout(limit, exc.stderr or exc.stdout)) from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start the Codex advisor: {exc}") from exc
    if completed.returncode:
        raise RuntimeError(classify_failure(completed.stderr, cfg.model))
    text = completed.stdout.strip()
    if not text:
        raise RuntimeError("Codex advisor returned no output.")
    return text


def consult(arguments: Any, workspace: str | None = None) -> str:
    values = validate_arguments(arguments)
    config = require_advisor_config(workspace)
    return run_codex_prompt(build_prompt(values), config=config, workspace=workspace)
