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

"""Consult a read-only Claude Opus advisor at high effort via the local claude CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from windows_runtime import resolve_cli  # noqa: E402

MODEL = "opus"
FIELDS = ("task", "stage", "approach", "evidence", "question")
STAGES = ("planning", "stuck", "pivot-check", "completion-review")
TIMEOUT_ENV = "CLAUDE_ADVISOR_TIMEOUT_SECONDS"


def timeout_seconds() -> int:
    try:
        value = int(os.environ.get(TIMEOUT_ENV, ""))
    except ValueError:
        value = 0
    return value if value > 0 else 600


def validate(arguments: Any) -> dict[str, str]:
    if not isinstance(arguments, dict):
        raise ValueError("consult_advisor arguments must be an object")
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
    return f"""You are a constructive senior engineering advisor to a coding agent from another vendor. Return a plan, course correction, or completion verdict. Do not implement or modify files. Inspect files only to verify material claims.

Pair every concern with a forward path. Label speculation and name the cheap check that settles it. If the executor is circling, give 2-4 alternatives in order. Recommending a stop requires concrete evidence, the strongest case for continuing, and why no other work can proceed.

Otherwise answer in at most 120 words: one-sentence direction, 2-4 important decisions or risks, and one verification. No preamble or restatement.

Structured consultation:\n{payload}\n"""


def command() -> list[str]:
    return [
        *resolve_cli("claude"), "-p", "--model", MODEL, "--effort", "high",
        "--permission-mode", "plan", "--tools", "Read,Grep,Glob", "--safe-mode",
        "--no-session-persistence", "--output-format", "text",
    ]


def consult(arguments: Any) -> str:
    values = validate(arguments)
    root = os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd()
    try:
        result = subprocess.run(
            command(), input=build_prompt(values), capture_output=True,
            encoding="utf-8", errors="replace", cwd=root,
            timeout=timeout_seconds(), check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Claude advisor timed out. Increase {TIMEOUT_ENV} or narrow the evidence.") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start the Claude advisor: {exc}") from exc
    if result.returncode:
        raise RuntimeError("Claude advisor failed. " + (result.stderr.strip() or "No error message was returned."))
    if not result.stdout.strip():
        raise RuntimeError("Claude advisor returned no advice.")
    return result.stdout.strip()
