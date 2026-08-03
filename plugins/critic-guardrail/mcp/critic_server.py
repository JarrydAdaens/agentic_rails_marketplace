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

"""Stdio MCP server exposing the Codex-backed consult_critic tool.

The critic is deliberately outside the executor's model family: a Claude Code
executor gets an adversarial second opinion from GPT-5.6-Sol at high reasoning,
so shared blind spots between same-family models are less likely to survive.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Any

MODEL = "gpt-5.6-sol"
TIMEOUT_SECONDS = 180
FIELDS = ("task", "stage", "approach", "evidence", "question")
STAGES = ("planning", "stuck", "pivot-check", "completion-review")


def validate_arguments(arguments: Any) -> dict[str, str]:
    if not isinstance(arguments, dict):
        raise ValueError("consult_critic arguments must be an object")
    missing = [name for name in FIELDS if not isinstance(arguments.get(name), str) or not arguments[name].strip()]
    if missing:
        raise ValueError("missing or empty required field(s): " + ", ".join(missing))
    if arguments["stage"] not in STAGES:
        raise ValueError("stage must be one of: " + ", ".join(STAGES))
    return {name: arguments[name].strip() for name in FIELDS}


def build_prompt(values: dict[str, str]) -> str:
    payload = (
        f"TASK: {values['task']}\nSTAGE: {values['stage']}\n"
        f"PLAN/APPROACH: {values['approach']}\nEVIDENCE: {values['evidence']}\n"
        f"QUESTION: {values['question']}"
    )
    return f"""You are an adversarial critic reviewing the work of a coding agent from a different vendor. Your job is to find what is wrong, not to be agreeable: attack the approach, hunt for the flaw, the missed edge case, the simpler alternative, or the misread requirement. Do not implement or modify files. Inspect repository files only when useful to test a claim.

Respond in at most 120 words: (1) your strongest objection in one sentence — or, if the approach genuinely survives attack, say so plainly, (2) the 2-4 concrete weaknesses, risks, or unexamined assumptions that matter most, (3) the one check most likely to expose a problem before proceeding. No preamble, no praise padding, and do not restate the task. If information is missing, identify it in one line rather than guessing.

Structured consultation:
{payload}
"""


def command() -> list[str]:
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("Codex executable not found on PATH; install Codex and sign in, then retry.")
    return [
        executable, "exec", "--ephemeral", "--sandbox", "read-only",
        "--model", MODEL, "-c", 'model_reasoning_effort="high"', "-",
    ]


def classify_failure(stderr: str) -> str:
    detail = stderr.strip() or "Codex exited without an error message."
    lowered = detail.lower()
    if any(term in lowered for term in ("not logged in", "authentication", "unauthorized", "sign in", "login required")):
        return "Codex authentication failed; sign in with the Codex CLI and retry. " + detail
    if any(term in lowered for term in ("model", "not available", "not found", "unsupported")):
        return f"Critic model {MODEL} is unavailable for this account or Codex version. " + detail
    return "Codex critic failed. " + detail


def consult(arguments: Any, workspace: str | None = None) -> str:
    values = validate_arguments(arguments)
    try:
        completed = subprocess.run(
            command(), input=build_prompt(values), capture_output=True,
            encoding="utf-8", errors="replace",
            cwd=workspace or os.getcwd(), timeout=TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Codex critic timed out after {TIMEOUT_SECONDS} seconds.") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start the Codex critic: {exc}") from exc
    if completed.returncode:
        raise RuntimeError(classify_failure(completed.stderr))
    critique = completed.stdout.strip()
    if not critique:
        raise RuntimeError("Codex critic returned no critique.")
    return critique


TOOL = {
    "name": "consult_critic",
    "description": "Consult the adversarial, read-only GPT-5.6-Sol critic for a cross-vendor second opinion before substantive work or completion.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "task": {"type": "string"},
            "stage": {"type": "string", "enum": list(STAGES)},
            "approach": {"type": "string"},
            "evidence": {"type": "string"},
            "question": {"type": "string"},
        },
        "required": list(FIELDS),
        "additionalProperties": False,
    },
}


def response(request_id: Any, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    message["error" if error else "result"] = error or result
    return message


def dispatch(message: dict[str, Any]) -> dict[str, Any] | None:
    method, request_id = message.get("method"), message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return response(request_id, {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "critic-guardrail", "version": "1.0.0"}})
    if method == "tools/list":
        return response(request_id, {"tools": [TOOL]})
    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != "consult_critic":
            return response(request_id, error={"code": -32601, "message": "Unknown tool"})
        try:
            critique = consult(params.get("arguments"))
            return response(request_id, {"content": [{"type": "text", "text": critique}], "isError": False})
        except (ValueError, RuntimeError) as exc:
            return response(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    return response(request_id, error={"code": -32601, "message": "Method not found"})


def main() -> None:
    for line in sys.stdin:
        try:
            output = dispatch(json.loads(line))
        except (json.JSONDecodeError, TypeError) as exc:
            output = response(None, error={"code": -32700, "message": str(exc)})
        if output is not None:
            print(json.dumps(output), flush=True)


if __name__ == "__main__":
    main()
