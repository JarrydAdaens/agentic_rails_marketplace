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

"""Stdio MCP server exposing the host-specific ``consult_advisor`` tool."""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
from typing import Any, TextIO

PLUGIN_NAME = "advisor-guardrail"
CODEX_MODEL = "gpt-5.6-sol"
CURSOR_MODEL = "cursor-grok-4.5-high"
DEFAULT_TIMEOUT_SECONDS = 600
TIMEOUT_ENV_VAR = "ADVISOR_GUARDRAIL_TIMEOUT_SECONDS"
FIELDS = ("task", "stage", "approach", "evidence", "question")
STAGES = ("planning", "stuck", "pivot-check", "completion-review")
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")


def timeout_seconds() -> int:
    try:
        configured = int(os.environ.get(TIMEOUT_ENV_VAR, ""))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    return configured if configured > 0 else DEFAULT_TIMEOUT_SECONDS


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
        raise ValueError("stage must be one of: " + ", ".join(STAGES))
    return {name: arguments[name].strip() for name in FIELDS}


def build_prompt(values: dict[str, str]) -> str:
    payload = (
        f"TASK: {values['task']}\nSTAGE: {values['stage']}\n"
        f"PLAN/APPROACH: {values['approach']}\nEVIDENCE: {values['evidence']}\n"
        f"QUESTION: {values['question']}"
    )
    return f"""You are a senior reviewer and planner advising a coding agent. Be constructive, candid, and practical. Return exactly one of: a plan, a course correction, or a completion verdict. Do not implement or modify files. Inspect repository files only when useful to verify a claim.

Work like a pair-programming partner who intends to finish. Never raise a concern without a forward path: pair it with a mitigation, experiment, narrower scope, fallback, decomposition, or deferral boundary. Label speculation and name the cheap check that would settle it. If the executor is repeating an approach without new evidence, say so and give two to four alternatives in the order you would try them.

Recommending that the executor stop, escalate, or wait for a human requires a concrete case, and the word limit below does not apply to that answer. Give all of: proposed stop reason; concrete evidence; strongest case for continuing; alternatives attempted; alternatives not attempted and why; why no other work can proceed; why human input is needed now. Otherwise recommend continuing.

Respond in at most 120 words: (1) verdict or direction in one sentence, (2) the 2-4 decisions or risks that matter, and (3) one thing to verify. No preamble or task restatement. If information is missing, identify it in one line rather than guessing.

Structured consultation:
{payload}
"""


def project_root(workspace: str | None = None) -> str:
    selected = (
        workspace
        or os.environ.get("CURSOR_PROJECT_DIR")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.getcwd()
    )
    return os.path.abspath(selected)


def codex_command() -> list[str]:
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("Codex executable not found on PATH; install Codex and sign in, then retry.")
    return [
        executable,
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--model",
        CODEX_MODEL,
        "-c",
        'model_reasoning_effort="high"',
        "-",
    ]


def cursor_command(workspace: str) -> list[str]:
    executable = shutil.which("agent")
    if not executable:
        raise RuntimeError(
            "Cursor Agent executable 'agent' not found on PATH; install Cursor Agent "
            "and sign in, then retry."
        )
    return [
        executable,
        "--print",
        "--output-format",
        "text",
        "--mode",
        "ask",
        "--sandbox",
        "disabled",
        "--trust",
        "--workspace",
        workspace,
        "--model",
        CURSOR_MODEL,
    ]


def command(host: str, workspace: str) -> list[str]:
    if host == "codex":
        return codex_command()
    if host == "cursor":
        return cursor_command(workspace)
    raise ValueError(f"unsupported advisor host: {host}")


def classify_failure(host: str, stderr: str) -> str:
    detail = stderr.strip() or f"{host.title()} exited without an error message."
    lowered = detail.lower()
    if any(term in lowered for term in ("not logged in", "authentication", "unauthorized", "sign in", "login required")):
        instruction = "sign in with the Codex CLI" if host == "codex" else "run 'agent login'"
        return f"{host.title()} authentication failed; {instruction} and retry. {detail}"
    if any(term in lowered for term in ("model", "not available", "not found", "unsupported")):
        model = CODEX_MODEL if host == "codex" else CURSOR_MODEL
        return f"Advisor model {model} is unavailable for this account or CLI version. {detail}"
    return f"{host.title()} advisor failed. {detail}"


def consult(host: str, arguments: Any, workspace: str | None = None) -> str:
    values = validate_arguments(arguments)
    root = project_root(workspace)
    limit = timeout_seconds()
    try:
        completed = subprocess.run(
            command(host, root),
            input=build_prompt(values),
            capture_output=True,
            encoding="utf-8",
            errors="strict",
            cwd=root,
            timeout=limit,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{host.title()} advisor timed out after {limit} seconds.") from exc
    except UnicodeError as exc:
        raise RuntimeError(f"Advisor input or output was not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start the {host.title()} advisor: {exc}") from exc
    if completed.returncode:
        raise RuntimeError(classify_failure(host, completed.stderr))
    advice = completed.stdout.strip()
    if not advice:
        raise RuntimeError(f"{host.title()} advisor returned no advice.")
    return advice


def tool(host: str) -> dict[str, Any]:
    model = CODEX_MODEL if host == "codex" else CURSOR_MODEL
    return {
        "name": "consult_advisor",
        "description": (
            f"Consult the constructive, read-only {model} senior advisor before "
            "substantive work, during a pivot, when stuck, or before completion."
        ),
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


def negotiate_protocol_version(params: Any) -> str:
    requested = params.get("protocolVersion") if isinstance(params, dict) else None
    return requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]


def dispatch(host: str, message: dict[str, Any]) -> dict[str, Any] | None:
    if "id" not in message:
        return None
    method = message.get("method")
    request_id = message["id"]
    params = message.get("params") or {}
    if method == "initialize":
        return response(request_id, {
            "protocolVersion": negotiate_protocol_version(params),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": PLUGIN_NAME, "version": "2.0.0"},
        })
    if method == "ping":
        return response(request_id, {})
    if method == "tools/list":
        return response(request_id, {"tools": [tool(host)]})
    if method == "tools/call":
        if params.get("name") != "consult_advisor":
            return response(request_id, error={"code": -32601, "message": "Unknown tool"})
        try:
            advice = consult(host, params.get("arguments"))
            return response(request_id, {
                "content": [{"type": "text", "text": advice}],
                "isError": False,
            })
        except (ValueError, RuntimeError) as exc:
            return response(request_id, {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            })
    return response(request_id, error={"code": -32601, "message": "Method not found"})


def utf8_writer(stream: TextIO) -> TextIO:
    return io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace", write_through=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", choices=("codex", "cursor"), required=True)
    args = parser.parse_args()
    stdin, stdout = sys.stdin.buffer, utf8_writer(sys.stdout)
    for raw in iter(stdin.readline, b""):
        try:
            message = json.loads(raw.decode("utf-8"))
            output = dispatch(args.host, message)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            output = response(None, error={"code": -32700, "message": str(exc)})
        except Exception as exc:
            output = response(None, error={"code": -32603, "message": f"Internal advisor server error: {exc}"})
        if output is not None:
            stdout.write(json.dumps(output) + "\n")
            stdout.flush()


if __name__ == "__main__":
    main()
