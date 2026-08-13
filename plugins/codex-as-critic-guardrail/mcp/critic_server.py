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

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, TextIO

HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))
from critic_markers import clear_server_ready, mark_server_ready  # noqa: E402

MODEL = "gpt-5.6-sol"
PLUGIN_VERSION = "1.1.0"

# Measured consult latency on real work: median 51s, p90 132s, longest success
# 178s. The original 180s cap sat inside that distribution, so consults in large
# or unfamiliar repositories failed outright. Claude Code does not impose a
# competing limit -- a stdio server has no per-request timer, and an unset
# MCP_TOOL_TIMEOUT defaults to roughly 28 hours -- so this cap is the only one
# that matters. Raise it further for very large repositories.
DEFAULT_TIMEOUT_SECONDS = 600
TIMEOUT_ENV_VAR = "CODEX_CRITIC_TIMEOUT_SECONDS"

FIELDS = ("task", "stage", "approach", "evidence", "question")
STAGES = ("planning", "stuck", "pivot-check", "completion-review")

# Newest first. initialize answers with the client's requested version when it
# is one of these, and with the newest otherwise.
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

FIELD_DESCRIPTIONS = {
    "task": "One-paragraph statement of the overall task, in your own words.",
    "stage": "Where you are in the task: planning, stuck, pivot-check, or completion-review.",
    "approach": "The plan you are about to follow, or the approach you actually took.",
    "evidence": "Concrete file paths, error messages, test output, and constraints you discovered. Thin evidence produces a thin critique.",
    "question": "The specific decision or verdict you want the critic to rule on.",
}


def timeout_seconds() -> int:
    """Consult timeout in seconds, overridable per environment."""
    try:
        configured = int(os.environ.get(TIMEOUT_ENV_VAR, ""))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    return configured if configured > 0 else DEFAULT_TIMEOUT_SECONDS


def validate_arguments(arguments: Any) -> dict[str, str]:
    if not isinstance(arguments, dict):
        raise ValueError("consult_critic arguments must be an object")
    missing = [name for name in FIELDS if not isinstance(arguments.get(name), str) or not arguments[name].strip()]
    if missing:
        raise ValueError("missing or empty required field(s): " + ", ".join(missing))
    if arguments["stage"] not in STAGES:
        # Echo what arrived: it tells the caller what to correct, and it is the
        # one place a payload is reflected back verbatim across the transport.
        raise ValueError(f"stage must be one of: {', '.join(STAGES)}; received: {arguments['stage']}")
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


def command() -> list[str]:
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("Codex executable not found on PATH; install Codex and sign in, then retry.")
    return [
        # --skip-git-repo-check keeps the critic usable in workspaces that are not
        # git repositories; without it Codex refuses to start there at all.
        executable, "exec", "--ephemeral", "--skip-git-repo-check",
        "--sandbox", "read-only", "--model", MODEL,
        "-c", 'model_reasoning_effort="high"', "-",
    ]


def classify_failure(stderr: str) -> str:
    detail = stderr.strip() or "Codex exited without an error message."
    lowered = detail.lower()
    if any(term in lowered for term in ("not logged in", "authentication", "unauthorized", "sign in", "login required")):
        return "Codex authentication failed; sign in with the Codex CLI and retry. " + detail
    if any(term in lowered for term in ("model", "not available", "not found", "unsupported")):
        return f"Critic model {MODEL} is unavailable for this account or Codex version. " + detail
    return "Codex critic failed. " + detail


def describe_timeout(limit: int, partial: Any) -> str:
    """Timeout message carrying whatever Codex managed to emit before the cut."""
    message = (
        f"Codex critic timed out after {limit} seconds. Set {TIMEOUT_ENV_VAR} to a "
        f"larger number of seconds if this workspace needs longer, or send narrower evidence."
    )
    if isinstance(partial, bytes):
        partial = partial.decode("utf-8", "replace")
    if isinstance(partial, str) and partial.strip():
        message += " Codex output before the timeout: " + partial.strip()[-400:]
    return message


def consult(arguments: Any, workspace: str | None = None) -> str:
    values = validate_arguments(arguments)
    limit = timeout_seconds()
    root = workspace or os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd()
    try:
        completed = subprocess.run(
            command(), input=build_prompt(values), capture_output=True,
            encoding="utf-8", errors="replace",
            cwd=root, timeout=limit, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(describe_timeout(limit, exc.stderr or exc.stdout)) from exc
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
            "task": {"type": "string", "description": FIELD_DESCRIPTIONS["task"]},
            "stage": {"type": "string", "enum": list(STAGES), "description": FIELD_DESCRIPTIONS["stage"]},
            "approach": {"type": "string", "description": FIELD_DESCRIPTIONS["approach"]},
            "evidence": {"type": "string", "description": FIELD_DESCRIPTIONS["evidence"]},
            "question": {"type": "string", "description": FIELD_DESCRIPTIONS["question"]},
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


def dispatch(message: dict[str, Any]) -> dict[str, Any] | None:
    """Answer one JSON-RPC message, or return None when no response is owed."""
    # A message carrying no id is a notification, and JSON-RPC forbids replying
    # to one. This covers notifications/initialized, notifications/cancelled,
    # and anything else the client sends without expecting an answer.
    if "id" not in message:
        return None

    method, request_id, params = message.get("method"), message["id"], message.get("params") or {}
    if method == "initialize":
        return response(request_id, {
            "protocolVersion": negotiate_protocol_version(params),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "codex-as-critic-guardrail", "version": PLUGIN_VERSION},
        })
    if method == "ping":
        return response(request_id, {})  # the spec requires an empty result here, not an error
    if method == "tools/list":
        mark_server_ready(
            host=os.environ.get("AGENTIC_RAILS_MCP_HOST", "unknown"),
            workspace=os.environ.get("AGENTIC_RAILS_WORKSPACE"),
        )
        return response(request_id, {"tools": [TOOL]})
    if method == "tools/call":
        if params.get("name") != "consult_critic":
            return response(request_id, error={"code": -32601, "message": "Unknown tool"})
        try:
            critique = consult(params.get("arguments"))
            return response(request_id, {"content": [{"type": "text", "text": critique}], "isError": False})
        except (ValueError, RuntimeError) as exc:
            return response(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    return response(request_id, error={"code": -32601, "message": "Method not found"})


def utf8_writer(stream: TextIO) -> TextIO:
    """Re-wrap an output stream as UTF-8.

    Windows gives a piped stdio stream the ANSI code page (cp1252). The MCP stdio
    transport is UTF-8 by specification, so say so rather than inherit the
    console's encoding.
    """
    return io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace", write_through=True)


def handle(line: str) -> dict[str, Any] | None:
    try:
        return dispatch(json.loads(line))
    except (json.JSONDecodeError, TypeError) as exc:
        return response(None, error={"code": -32700, "message": str(exc)})
    except Exception as exc:  # one bad message must never kill the server
        return response(None, error={"code": -32603, "message": f"Internal critic server error: {exc}"})


def main() -> None:
    """Serve JSON-RPC over stdio until the client closes the transport.

    Lines are read as bytes and decoded per message. Decoding strictly matters --
    silently replacing bad bytes would corrupt a payload, which is the defect
    being fixed -- but a decode failure must not be fatal either: an exception
    escaping this loop kills the server, and a client with a call in flight then
    hangs until its own idle timeout instead of seeing an error. Decoding one
    line at a time gives strictness and recovery at once.
    """
    stdin, stdout = sys.stdin.buffer, utf8_writer(sys.stdout)
    try:
        while True:
            raw = stdin.readline()
            if not raw:
                return  # client closed the transport
            try:
                line = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                output = response(None, error={"code": -32700, "message": f"stdin is not valid UTF-8: {exc}"})
            else:
                if not line.strip():
                    continue
                output = handle(line)
            if output is not None:
                stdout.write(json.dumps(output) + "\n")
                stdout.flush()
    finally:
        clear_server_ready()


if __name__ == "__main__":
    main()
