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

from critic_config import (
    CONSULT_TIMEOUT_ENV_VAR,
    CriticConfig,
    DEFAULT_CONSULT_TIMEOUT_SECONDS,
    require_critic_config,
    resolve_consult_timeout,
)
from windows_runtime import resolve_cli

PLUGIN_VERSION = "1.2.0"

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
        "discovered. Thin evidence produces a thin critique."
    ),
    "question": "The specific decision or verdict you want the critic to rule on.",
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


def timeout_seconds(config: CriticConfig | None = None) -> int:
    return resolve_consult_timeout(config)


def validate_arguments(arguments: Any) -> dict[str, str]:
    if not isinstance(arguments, dict):
        raise ValueError("consult_critic arguments must be an object")
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
    return f"""You are an adversarial critic reviewing the work of a coding agent from a different vendor. Your job is to find what is wrong, not to be agreeable: attack the approach, hunt for the flaw, the missed edge case, the simpler alternative, or the misread requirement. Do not implement or modify files. Inspect repository files only when useful to test a claim.

Attack the work to improve it, not to halt it. You are the senior engineering voice in this exchange — "someone more senior should decide" is not available to you. Every material objection carries five parts: the problem, the evidence, the concrete consequence, the correction you recommend, and whether work can continue meanwhile. Keep risk language concrete: not "this may regress rendering" but "this changes render-target lifetime and invalidates the three call sites that retain references across frames". Label a hypothesis as a hypothesis and name the test or experiment that would confirm it rather than escalating it.

If the executor proposes stopping, escalating, or waiting for a human, attack that proposal with the same energy you attack the code: is the blocker global or only local, can the affected part be isolated, can other work proceed, can a cheap experiment settle it, is the damage actually irreversible, is this a strategic decision or merely an implementation problem? Endorsing a stop requires you to state the strongest argument for continuing, why that argument fails, and why stopping is justified — and the word limit below does not apply to that answer.

Otherwise respond in at most 120 words: (1) your strongest objection in one sentence — or, if the approach genuinely survives attack, say so plainly, (2) the 2-4 concrete weaknesses, risks, or unexamined assumptions that matter most, (3) the one check most likely to expose a problem before proceeding. No preamble, no praise padding, and do not restate the task. If information is missing, identify it in one line rather than guessing.

Structured consultation:
{payload}
"""


def command(config: CriticConfig | None = None) -> list[str]:
    cfg = config or CriticConfig()
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
        return "Codex critic quota or credits exhausted. " + detail
    if any(term in lowered for term in ("model", "not available", "not found", "unsupported")):
        return f"Critic model {model} is unavailable for this account or Codex version. " + detail
    return "Codex critic failed. " + detail


def is_hard_failure_message(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in HARD_FAILURE_HINTS)


def describe_timeout(limit: int, partial: Any) -> str:
    message = (
        f"Codex critic timed out after {limit} seconds. Raise consult_timeout_seconds in "
        f"harness/codex-as-critic-guardrail/config.json, or set {TIMEOUT_ENV_VAR}, "
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
    config: CriticConfig | None = None,
    workspace: str | None = None,
    timeout: int | None = None,
) -> str:
    cfg = config or require_critic_config(workspace)
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
        raise RuntimeError(f"Could not start the Codex critic: {exc}") from exc
    if completed.returncode:
        raise RuntimeError(classify_failure(completed.stderr, cfg.model))
    text = completed.stdout.strip()
    if not text:
        raise RuntimeError("Codex critic returned no output.")
    return text


def consult(arguments: Any, workspace: str | None = None) -> str:
    values = validate_arguments(arguments)
    config = require_critic_config(workspace)
    return run_codex_prompt(build_prompt(values), config=config, workspace=workspace)
