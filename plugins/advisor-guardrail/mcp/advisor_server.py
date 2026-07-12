"""Stdio MCP server exposing the Codex-backed consult_advisor tool."""

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
        raise ValueError("consult_advisor arguments must be an object")
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
    return f"""You are a senior reviewer and planner advising a coding agent. Do not implement or modify files. Inspect repository files only when useful, and return exactly one plan, course correction, or completion verdict.

Respond in at most 120 words: (1) verdict or direction in one sentence, (2) the 2-4 decisions or risks that matter, (3) one thing to verify before proceeding. No preamble and do not restate the task. If information is missing, identify it in one line rather than guessing. Calibrate concrete advice to a mid-level engineer.

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
        return f"Advisor model {MODEL} is unavailable for this account or Codex version. " + detail
    return "Codex advisor failed. " + detail


def consult(arguments: Any, workspace: str | None = None) -> str:
    values = validate_arguments(arguments)
    try:
        completed = subprocess.run(
            command(), input=build_prompt(values), text=True, capture_output=True,
            cwd=workspace or os.getcwd(), timeout=TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Codex advisor timed out after {TIMEOUT_SECONDS} seconds.") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start the Codex advisor: {exc}") from exc
    if completed.returncode:
        raise RuntimeError(classify_failure(completed.stderr))
    advice = completed.stdout.strip()
    if not advice:
        raise RuntimeError("Codex advisor returned no advice.")
    return advice


TOOL = {
    "name": "consult_advisor",
    "description": "Consult the read-only GPT-5.6-Sol senior advisor before substantive work or completion.",
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
        return response(request_id, {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "advisor-guardrail", "version": "1.0.0"}})
    if method == "tools/list":
        return response(request_id, {"tools": [TOOL]})
    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != "consult_advisor":
            return response(request_id, error={"code": -32601, "message": "Unknown tool"})
        try:
            advice = consult(params.get("arguments"))
            return response(request_id, {"content": [{"type": "text", "text": advice}], "isError": False})
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
