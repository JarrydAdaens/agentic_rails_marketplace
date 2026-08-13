"""Stdio MCP server exposing a constructive Codex-backed advisor."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, TextIO

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
sys.path.insert(0, str(HOOKS))
from advisor_markers import clear_server_ready, mark_server_ready  # noqa: E402

MODEL = "gpt-5.6-sol"
VERSION = "1.0.0"
FIELDS = ("task", "stage", "approach", "evidence", "question")
STAGES = ("planning", "stuck", "pivot-check", "completion-review")
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
TIMEOUT_ENV = "CODEX_ADVISOR_TIMEOUT_SECONDS"


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


def prompt(values: dict[str, str]) -> str:
    payload = "\n".join((f"TASK: {values['task']}", f"STAGE: {values['stage']}", f"PLAN/APPROACH: {values['approach']}", f"EVIDENCE: {values['evidence']}", f"QUESTION: {values['question']}"))
    return f"""You are a senior reviewer and planner advising a coding agent from another vendor. Be constructive, candid, and practical. Return exactly one of: a plan, a course correction, or a completion verdict. Do not implement or modify files. Inspect repository files only to verify relevant claims.

Never raise a concern without a forward path. Label speculation and name the cheap check that settles it. If the executor is circling, say so and give 2-4 concrete options in order. Recommending a stop requires concrete evidence, the strongest case for continuing, alternatives tried and untried, and why no other work can proceed.

Otherwise answer in at most 120 words: one-sentence direction, the 2-4 decisions or risks that matter, and one verification before proceeding. No preamble or restatement.

Structured consultation:\n{payload}\n"""


def command() -> list[str]:
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("Codex executable not found on PATH; install Codex and sign in, then retry.")
    return [executable, "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only", "--model", MODEL, "-c", 'model_reasoning_effort="high"', "-"]


def consult(arguments: Any) -> str:
    values = validate(arguments)
    root = os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd()
    try:
        result = subprocess.run(command(), input=prompt(values), capture_output=True, encoding="utf-8", errors="replace", cwd=root, timeout=timeout_seconds(), check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Codex advisor timed out. Increase {TIMEOUT_ENV} or narrow the evidence.") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start the Codex advisor: {exc}") from exc
    if result.returncode:
        raise RuntimeError("Codex advisor failed. " + (result.stderr.strip() or "No error message was returned."))
    if not result.stdout.strip():
        raise RuntimeError("Codex advisor returned no advice.")
    return result.stdout.strip()


TOOL = {"name": "consult_advisor", "description": "Consult a constructive, read-only GPT-5.6 Sol advisor at high reasoning.", "inputSchema": {"type": "object", "properties": {key: ({"type": "string", "enum": list(STAGES)} if key == "stage" else {"type": "string"}) for key in FIELDS}, "required": list(FIELDS), "additionalProperties": False}}


def reply(request_id: Any, result=None, error=None):
    return {"jsonrpc": "2.0", "id": request_id, "error" if error else "result": error or result}


def dispatch(message: dict[str, Any]):
    if "id" not in message:
        return None
    request_id, method, params = message["id"], message.get("method"), message.get("params") or {}
    if method == "initialize":
        requested = params.get("protocolVersion")
        return reply(request_id, {"protocolVersion": requested if requested in PROTOCOLS else PROTOCOLS[0], "capabilities": {"tools": {}}, "serverInfo": {"name": "codex-as-advisor-guardrail", "version": VERSION}})
    if method == "ping":
        return reply(request_id, {})
    if method == "tools/list":
        mark_server_ready(os.environ.get("AGENTIC_RAILS_MCP_HOST", "unknown"), os.environ.get("AGENTIC_RAILS_WORKSPACE"))
        return reply(request_id, {"tools": [TOOL]})
    if method == "tools/call":
        if params.get("name") != "consult_advisor":
            return reply(request_id, error={"code": -32601, "message": "Unknown tool"})
        try:
            text = consult(params.get("arguments"))
            return reply(request_id, {"content": [{"type": "text", "text": text}], "isError": False})
        except (ValueError, RuntimeError) as exc:
            return reply(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    return reply(request_id, error={"code": -32601, "message": "Method not found"})


def writer(stream: TextIO) -> TextIO:
    return io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace", write_through=True)


def main() -> None:
    stdin, stdout = sys.stdin.buffer, writer(sys.stdout)
    try:
        for raw in iter(stdin.readline, b""):
            if not raw.strip():
                continue
            try:
                output = dispatch(json.loads(raw.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
                output = reply(None, error={"code": -32700, "message": str(exc)})
            except Exception as exc:
                output = reply(None, error={"code": -32603, "message": f"Internal advisor server error: {exc}"})
            if output is not None:
                stdout.write(json.dumps(output) + "\n")
                stdout.flush()
    finally:
        clear_server_ready()


if __name__ == "__main__":
    main()
