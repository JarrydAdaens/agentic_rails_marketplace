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

"""Stdio MCP server exposing a Cursor-backed consult_advisor tool."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, TextIO

HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))
from advisor_markers import clear_server_ready, mark_server_ready  # noqa: E402

PLUGIN_NAME = "cursor-as-advisor-guardrail"
BUILTIN_DEFAULT_MODEL = "cursor-grok-4.6-high"
CONFIG_RELATIVE_PATH = Path("harness") / PLUGIN_NAME / "config.json"
CONFIG_MODEL_KEY = "default_model"

DEFAULT_TIMEOUT_SECONDS = 600
TIMEOUT_ENV_VAR = "CURSOR_ADVISOR_TIMEOUT_SECONDS"

FIELDS = ("task", "stage", "approach", "evidence", "question")
OPTIONAL_FIELDS = ("model",)
STAGES = ("planning", "stuck", "pivot-check", "completion-review")
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

FIELD_DESCRIPTIONS = {
    "task": "One-paragraph statement of the overall task, in your own words.",
    "stage": "Where you are in the task: planning, stuck, pivot-check, or completion-review.",
    "approach": "The plan you are about to follow, or the approach you actually took.",
    "evidence": (
        "Concrete file paths, error messages, test output, and constraints you "
        "discovered. Thin evidence produces thin advice."
    ),
    "question": "The specific decision or verdict you want the advisor to address.",
    "model": (
        "Optional Cursor model ID for this consultation. A successful call "
        "remembers it as this project's default; omit it to reuse the saved default."
    ),
}


def timeout_seconds() -> int:
    """Return the positive configured timeout or the built-in default."""
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
        raise ValueError(
            f"stage must be one of: {', '.join(STAGES)}; received: {arguments['stage']}"
        )
    model = arguments.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError("model must be a non-empty Cursor model ID when provided")
    names = FIELDS + OPTIONAL_FIELDS
    return {name: arguments[name].strip() for name in names if name in arguments}


def build_prompt(values: dict[str, str]) -> str:
    payload = (
        f"TASK: {values['task']}\nSTAGE: {values['stage']}\n"
        f"PLAN/APPROACH: {values['approach']}\nEVIDENCE: {values['evidence']}\n"
        f"QUESTION: {values['question']}"
    )
    return f"""You are a senior reviewer and planner advising a coding agent from a different vendor. Be constructive, candid, and practical. Your job is to improve the executor's decisions, not to implement the task and not to manufacture objections. Return exactly one of: a plan, a course correction, or a completion verdict. Do not modify files. Inspect repository files only when useful to verify a claim.

Work like a pair-programming partner who intends to finish. Your instinct on seeing a problem is "what else can we try?", never "who can we escalate this to?". Never raise a concern without a forward path: pair it with a mitigation, an experiment, a narrower scope, a fallback, a decomposition, or a deferral boundary. Label speculation as speculation and name the cheap check that would settle it instead of treating it as a reason to halt. If the executor is circling the same approach without new evidence, say so plainly and give two to four concrete options in the order you would try them.

Recommending that the executor stop, escalate, or wait for a human requires a concrete case, and the word limit below does not apply to that answer. Give all of: proposed stop reason; concrete evidence; the strongest case for continuing; alternatives attempted; alternatives not attempted and why; why no other work can proceed meanwhile; why human input is needed now. If you cannot make that case concretely, recommend continuing.

Otherwise respond in at most 120 words: (1) your verdict or direction in one sentence, (2) the 2-4 decisions, risks, or opportunities that actually matter, (3) one thing to verify before proceeding. No preamble, no praise padding, and do not restate the task. If information is missing, identify exactly what is missing in one line rather than guessing. Calibrate the advice to a capable executor that needs an independent perspective, not step-by-step supervision.

Structured consultation:
{payload}
"""


def project_root(workspace: str | None = None) -> Path:
    selected = (workspace or os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.environ.get("CURSOR_PROJECT_DIR") or
                os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    return Path(selected).resolve()


def config_path(workspace: str | None = None) -> Path:
    return project_root(workspace) / CONFIG_RELATIVE_PATH


def read_project_default(workspace: str | None = None) -> tuple[str, bool]:
    path = config_path(workspace)
    if not path.is_file():
        return BUILTIN_DEFAULT_MODEL, False
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read Cursor advisor config {path}: {exc}") from exc
    model = config.get(CONFIG_MODEL_KEY) if isinstance(config, dict) else None
    if not isinstance(model, str) or not model.strip():
        raise RuntimeError(
            f"Cursor advisor config {path} must contain a non-empty "
            f"{CONFIG_MODEL_KEY!r} string."
        )
    return model.strip(), True


def write_project_default(model: str, workspace: str | None = None) -> Path:
    """Atomically remember a model in the target project's harness seam."""
    path = config_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    config: dict[str, Any] = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not update Cursor advisor config {path}: {exc}") from exc
        if not isinstance(existing, dict):
            raise RuntimeError(f"Cursor advisor config {path} must contain a JSON object.")
        config.update(existing)
    config[CONFIG_MODEL_KEY] = model

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".cursor-advisor-config-", suffix=".tmp", delete=False,
        ) as temporary:
            temporary_name = temporary.name
            json.dump(config, temporary, indent=2)
            temporary.write("\n")
        Path(temporary_name).replace(path)
    except OSError as exc:
        if temporary_name:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise RuntimeError(f"Could not remember Cursor advisor model in {path}: {exc}") from exc
    return path


def select_model(values: dict[str, str], workspace: str | None = None) -> tuple[str, bool]:
    requested = values.get("model")
    if requested:
        saved, exists = read_project_default(workspace)
        return requested, not exists or requested != saved
    saved, exists = read_project_default(workspace)
    return saved, not exists


def command(model: str) -> list[str]:
    executable = shutil.which("agent")
    if not executable:
        raise RuntimeError(
            "Cursor Agent executable 'agent' not found on PATH; install Cursor Agent "
            "and sign in, then retry."
        )
    return [
        executable,
        "--print",
        "--output-format", "text",
        "--mode", "ask",
        "--sandbox", "disabled",
        "--trust",
        "--model", model,
    ]


def classify_failure(stderr: str, model: str) -> str:
    detail = stderr.strip() or "Cursor Agent exited without an error message."
    lowered = detail.lower()
    auth_terms = ("not logged in", "authentication", "unauthorized", "sign in", "login required")
    if any(term in lowered for term in auth_terms):
        return "Cursor authentication failed; run 'agent login' and retry. " + detail
    if any(term in lowered for term in ("model", "not available", "not found", "unsupported")):
        return (
            f"Cursor advisor model {model} is unavailable for this account or "
            f"Cursor Agent version. {detail}"
        )
    return "Cursor advisor failed. " + detail


def describe_timeout(limit: int, partial: Any) -> str:
    message = (
        f"Cursor advisor timed out after {limit} seconds. Set {TIMEOUT_ENV_VAR} to a "
        "larger number of seconds if this workspace needs longer, or send narrower evidence."
    )
    if isinstance(partial, bytes):
        partial = partial.decode("utf-8", "replace")
    if isinstance(partial, str) and partial.strip():
        message += " Cursor output before the timeout: " + partial.strip()[-400:]
    return message


def consult(arguments: Any, workspace: str | None = None) -> str:
    values = validate_arguments(arguments)
    root = project_root(workspace)
    model, remember = select_model(values, str(root))
    limit = timeout_seconds()
    try:
        completed = subprocess.run(
            command(model), input=build_prompt(values), capture_output=True,
            encoding="utf-8", errors="strict", cwd=root, timeout=limit, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(describe_timeout(limit, exc.stderr or exc.stdout)) from exc
    except UnicodeError as exc:
        raise RuntimeError(f"Cursor advisor input or output was not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start the Cursor advisor: {exc}") from exc
    if completed.returncode:
        raise RuntimeError(classify_failure(completed.stderr, model))
    advice = completed.stdout.strip()
    if not advice:
        raise RuntimeError("Cursor advisor returned no advice.")
    if remember:
        write_project_default(model, str(root))
    return advice


TOOL = {
    "name": "consult_advisor",
    "description": (
        "Consult a constructive, read-only Cursor advisor before substantive work, "
        "during a pivot, when stuck, or before completion; model selection is "
        "remembered per project."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": FIELD_DESCRIPTIONS["task"]},
            "stage": {
                "type": "string", "enum": list(STAGES),
                "description": FIELD_DESCRIPTIONS["stage"],
            },
            "approach": {"type": "string", "description": FIELD_DESCRIPTIONS["approach"]},
            "evidence": {"type": "string", "description": FIELD_DESCRIPTIONS["evidence"]},
            "question": {"type": "string", "description": FIELD_DESCRIPTIONS["question"]},
            "model": {"type": "string", "description": FIELD_DESCRIPTIONS["model"]},
        },
        "required": list(FIELDS),
        "additionalProperties": False,
    },
}


def response(
    request_id: Any,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    message["error" if error else "result"] = error or result
    return message


def negotiate_protocol_version(params: Any) -> str:
    requested = params.get("protocolVersion") if isinstance(params, dict) else None
    return requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]


def dispatch(message: dict[str, Any]) -> dict[str, Any] | None:
    if "id" not in message:
        return None

    method = message.get("method")
    request_id = message["id"]
    params = message.get("params") or {}
    if method == "initialize":
        return response(request_id, {
            "protocolVersion": negotiate_protocol_version(params),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": PLUGIN_NAME, "version": "1.0.0"},
        })
    if method == "ping":
        return response(request_id, {})
    if method == "tools/list":
        mark_server_ready(os.environ.get("AGENTIC_RAILS_MCP_HOST", "unknown"), os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd())
        return response(request_id, {"tools": [TOOL]})
    if method == "tools/call":
        if params.get("name") != "consult_advisor":
            return response(request_id, error={"code": -32601, "message": "Unknown tool"})
        try:
            advice = consult(params.get("arguments"))
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


def handle(line: str) -> dict[str, Any] | None:
    try:
        return dispatch(json.loads(line))
    except (json.JSONDecodeError, TypeError) as exc:
        return response(None, error={"code": -32700, "message": str(exc)})
    except Exception as exc:
        return response(None, error={
            "code": -32603,
            "message": f"Internal advisor server error: {exc}",
        })


def main() -> None:
    stdin, stdout = sys.stdin.buffer, utf8_writer(sys.stdout)
    try:
        while True:
            raw = stdin.readline()
            if not raw:
                return
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
