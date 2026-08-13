"""Stdio MCP server exposing a read-only Claude Opus advisor."""
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

VERSION = "1.0.0"
MODEL = "opus"
FIELDS = ("task", "stage", "approach", "evidence", "question")
STAGES = ("planning", "stuck", "pivot-check", "completion-review")
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
TIMEOUT_ENV = "CLAUDE_ADVISOR_TIMEOUT_SECONDS"


def timeout_seconds():
    try: value = int(os.environ.get(TIMEOUT_ENV, ""))
    except ValueError: value = 0
    return value if value > 0 else 600


def validate(arguments):
    if not isinstance(arguments, dict): raise ValueError("consult_advisor arguments must be an object")
    missing = [key for key in FIELDS if not isinstance(arguments.get(key), str) or not arguments[key].strip()]
    if missing: raise ValueError("missing or empty required field(s): " + ", ".join(missing))
    if arguments["stage"] not in STAGES: raise ValueError(f"stage must be one of: {', '.join(STAGES)}; received: {arguments['stage']}")
    return {key: arguments[key].strip() for key in FIELDS}


def build_prompt(v):
    payload = "\n".join((f"TASK: {v['task']}", f"STAGE: {v['stage']}", f"PLAN/APPROACH: {v['approach']}", f"EVIDENCE: {v['evidence']}", f"QUESTION: {v['question']}"))
    return f"""You are a constructive senior engineering advisor to a coding agent from another vendor. Return a plan, course correction, or completion verdict. Do not implement or modify files. Inspect files only to verify material claims.

Pair every concern with a forward path. Label speculation and name the cheap check that settles it. If the executor is circling, give 2-4 alternatives in order. Recommending a stop requires concrete evidence, the strongest case for continuing, and why no other work can proceed.

Otherwise answer in at most 120 words: one-sentence direction, 2-4 important decisions or risks, and one verification. No preamble or restatement.

Structured consultation:\n{payload}\n"""


def command():
    executable = shutil.which("claude")
    if not executable: raise RuntimeError("Claude executable not found on PATH; install Claude Code and sign in, then retry.")
    return [executable, "-p", "--model", MODEL, "--effort", "high", "--permission-mode", "plan", "--tools", "Read,Grep,Glob", "--safe-mode", "--no-session-persistence", "--output-format", "text"]


def consult(arguments):
    values = validate(arguments); root = os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd()
    try: result = subprocess.run(command(), input=build_prompt(values), capture_output=True, encoding="utf-8", errors="replace", cwd=root, timeout=timeout_seconds(), check=False)
    except subprocess.TimeoutExpired as exc: raise RuntimeError(f"Claude advisor timed out. Increase {TIMEOUT_ENV} or narrow the evidence.") from exc
    except OSError as exc: raise RuntimeError(f"Could not start the Claude advisor: {exc}") from exc
    if result.returncode: raise RuntimeError("Claude advisor failed. " + (result.stderr.strip() or "No error message was returned."))
    if not result.stdout.strip(): raise RuntimeError("Claude advisor returned no advice.")
    return result.stdout.strip()


TOOL = {"name": "consult_advisor", "description": "Consult a constructive, read-only Claude Opus advisor at high effort.", "inputSchema": {"type": "object", "properties": {key: ({"type": "string", "enum": list(STAGES)} if key == "stage" else {"type": "string"}) for key in FIELDS}, "required": list(FIELDS), "additionalProperties": False}}


def reply(request_id, result=None, error=None): return {"jsonrpc": "2.0", "id": request_id, "error" if error else "result": error or result}


def dispatch(message):
    if "id" not in message: return None
    request_id, method, params = message["id"], message.get("method"), message.get("params") or {}
    if method == "initialize":
        requested = params.get("protocolVersion")
        return reply(request_id, {"protocolVersion": requested if requested in PROTOCOLS else PROTOCOLS[0], "capabilities": {"tools": {}}, "serverInfo": {"name": "claude-as-advisor-guardrail", "version": VERSION}})
    if method == "ping": return reply(request_id, {})
    if method == "tools/list":
        mark_server_ready(os.environ.get("AGENTIC_RAILS_MCP_HOST", "unknown"), os.environ.get("AGENTIC_RAILS_WORKSPACE")); return reply(request_id, {"tools": [TOOL]})
    if method == "tools/call":
        if params.get("name") != "consult_advisor": return reply(request_id, error={"code": -32601, "message": "Unknown tool"})
        try: return reply(request_id, {"content": [{"type": "text", "text": consult(params.get("arguments"))}], "isError": False})
        except (ValueError, RuntimeError) as exc: return reply(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    return reply(request_id, error={"code": -32601, "message": "Method not found"})


def writer(stream: TextIO): return io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace", write_through=True)


def main():
    stdin, stdout = sys.stdin.buffer, writer(sys.stdout)
    try:
        for raw in iter(stdin.readline, b""):
            if not raw.strip(): continue
            try: output = dispatch(json.loads(raw.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc: output = reply(None, error={"code": -32700, "message": str(exc)})
            except Exception as exc: output = reply(None, error={"code": -32603, "message": f"Internal advisor server error: {exc}"})
            if output is not None: stdout.write(json.dumps(output) + "\n"); stdout.flush()
    finally: clear_server_ready()


if __name__ == "__main__": main()
