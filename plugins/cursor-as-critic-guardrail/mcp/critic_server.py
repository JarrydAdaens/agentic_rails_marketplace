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

"""Stdio MCP server exposing the Cursor-backed consult_critic tool.

The critic runs through the user's authenticated Cursor Agent CLI in read-only
ask mode. Its model is selectable per call and remembered independently in the
current project's harness seam.
"""

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

PLUGIN_NAME = "cursor-as-critic-guardrail"
BUILTIN_DEFAULT_MODEL = "cursor-grok-4.5-high"
CONFIG_RELATIVE_PATH = Path("harness") / PLUGIN_NAME / "config.json"
CONFIG_MODEL_KEY = "default_model"

DEFAULT_TIMEOUT_SECONDS = 600
TIMEOUT_ENV_VAR = "CURSOR_CRITIC_TIMEOUT_SECONDS"

FIELDS = ("task", "stage", "approach", "evidence", "question")
OPTIONAL_FIELDS = ("model",)
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
    "model": (
        "Optional Cursor model ID for this consultation (for example composer-2.5, "
        "claude-fable-5-thinking-high, or cursor-grok-4.5-low). A successful "
        "call remembers it as this project's default; omit it to reuse the saved default."
    ),
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
        raise ValueError(f"stage must be one of: {', '.join(STAGES)}; received: {arguments['stage']}")
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
    return f"""You are an adversarial critic reviewing the work of a coding agent from a different vendor. Your job is to find what is wrong, not to be agreeable: attack the approach, hunt for the flaw, the missed edge case, the simpler alternative, or the misread requirement. Do not implement or modify files. Inspect repository files only when useful to test a claim.

Attack the work to improve it, not to halt it. You are the senior engineering voice in this exchange — "someone more senior should decide" is not available to you. Every material objection carries five parts: the problem, the evidence, the concrete consequence, the correction you recommend, and whether work can continue meanwhile. Keep risk language concrete: not "this may regress rendering" but "this changes render-target lifetime and invalidates the three call sites that retain references across frames". Label a hypothesis as a hypothesis and name the test or experiment that would confirm it rather than escalating it.

If the executor proposes stopping, escalating, or waiting for a human, attack that proposal with the same energy you attack the code: is the blocker global or only local, can the affected part be isolated, can other work proceed, can a cheap experiment settle it, is the damage actually irreversible, is this a strategic decision or merely an implementation problem? Endorsing a stop requires you to state the strongest argument for continuing, why that argument fails, and why stopping is justified — and the word limit below does not apply to that answer.

Otherwise respond in at most 120 words: (1) your strongest objection in one sentence — or, if the approach genuinely survives attack, say so plainly, (2) the 2-4 concrete weaknesses, risks, or unexamined assumptions that matter most, (3) the one check most likely to expose a problem before proceeding. No preamble, no praise padding, and do not restate the task. If information is missing, identify it in one line rather than guessing.

Structured consultation:
{payload}
"""


def project_root(workspace: str | None = None) -> Path:
    """Return the target project root used for both the config and Cursor run."""
    selected = (workspace or os.environ.get("CURSOR_PROJECT_DIR") or
                os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    return Path(selected).resolve()


def config_path(workspace: str | None = None) -> Path:
    return project_root(workspace) / CONFIG_RELATIVE_PATH


def read_project_default(workspace: str | None = None) -> tuple[str, bool]:
    """Return (model, config_exists), falling back silently when absent."""
    path = config_path(workspace)
    if not path.is_file():
        return BUILTIN_DEFAULT_MODEL, False
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read Cursor critic config {path}: {exc}") from exc
    model = config.get(CONFIG_MODEL_KEY) if isinstance(config, dict) else None
    if not isinstance(model, str) or not model.strip():
        raise RuntimeError(f"Cursor critic config {path} must contain a non-empty {CONFIG_MODEL_KEY!r} string.")
    return model.strip(), True


def write_project_default(model: str, workspace: str | None = None) -> Path:
    """Atomically remember a model in this project's harness seam."""
    path = config_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    config: dict[str, Any] = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not update Cursor critic config {path}: {exc}") from exc
        if not isinstance(existing, dict):
            raise RuntimeError(f"Cursor critic config {path} must contain a JSON object.")
        config.update(existing)
    config[CONFIG_MODEL_KEY] = model

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".cursor-critic-config-", suffix=".tmp", delete=False,
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
        raise RuntimeError(f"Could not remember Cursor critic model in {path}: {exc}") from exc
    return path


def select_model(values: dict[str, str], workspace: str | None = None) -> tuple[str, bool]:
    """Select the requested/project/built-in model and whether it needs saving."""
    requested = values.get("model")
    if requested:
        saved, exists = read_project_default(workspace)
        return requested, not exists or requested != saved
    saved, exists = read_project_default(workspace)
    return saved, not exists


def command(model: str) -> list[str]:
    executable = shutil.which("agent")
    if not executable:
        raise RuntimeError("Cursor Agent executable 'agent' not found on PATH; install Cursor Agent and sign in, then retry.")
    return [
        executable,
        "--print",
        "--output-format", "text",
        "--mode", "ask",
        # Cursor's OS sandbox is unavailable on Windows. Ask mode itself is the
        # read-only execution boundary; do not add --force or approval bypasses.
        "--sandbox", "disabled",
        # Non-interactive Cursor refuses unseen workspaces without this
        # acknowledgement. It trusts workspace contents; it does not override
        # ask mode or grant write/tool permissions.
        "--trust",
        "--model", model,
    ]


def classify_failure(stderr: str, model: str) -> str:
    detail = stderr.strip() or "Cursor Agent exited without an error message."
    lowered = detail.lower()
    if any(term in lowered for term in ("not logged in", "authentication", "unauthorized", "sign in", "login required")):
        return "Cursor authentication failed; run 'agent login' and retry. " + detail
    if any(term in lowered for term in ("model", "not available", "not found", "unsupported")):
        return f"Cursor critic model {model} is unavailable for this account or Cursor Agent version. " + detail
    return "Cursor critic failed. " + detail


def describe_timeout(limit: int, partial: Any) -> str:
    """Timeout message carrying whatever Cursor managed to emit before the cut."""
    message = (
        f"Cursor critic timed out after {limit} seconds. Set {TIMEOUT_ENV_VAR} to a "
        f"larger number of seconds if this workspace needs longer, or send narrower evidence."
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
            encoding="utf-8", errors="strict",
            cwd=root, timeout=limit, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(describe_timeout(limit, exc.stderr or exc.stdout)) from exc
    except UnicodeError as exc:
        raise RuntimeError(f"Cursor critic input or output was not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start the Cursor critic: {exc}") from exc
    if completed.returncode:
        raise RuntimeError(classify_failure(completed.stderr, model))
    critique = completed.stdout.strip()
    if not critique:
        raise RuntimeError("Cursor critic returned no critique.")
    if remember:
        write_project_default(model, str(root))
    return critique


TOOL = {
    "name": "consult_critic",
    "description": "Consult an adversarial, read-only Cursor critic before substantive work or completion; model selection is remembered per project.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": FIELD_DESCRIPTIONS["task"]},
            "stage": {"type": "string", "enum": list(STAGES), "description": FIELD_DESCRIPTIONS["stage"]},
            "approach": {"type": "string", "description": FIELD_DESCRIPTIONS["approach"]},
            "evidence": {"type": "string", "description": FIELD_DESCRIPTIONS["evidence"]},
            "question": {"type": "string", "description": FIELD_DESCRIPTIONS["question"]},
            "model": {"type": "string", "description": FIELD_DESCRIPTIONS["model"]},
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
    if "id" not in message:
        return None

    method, request_id, params = message.get("method"), message["id"], message.get("params") or {}
    if method == "initialize":
        return response(request_id, {
            "protocolVersion": negotiate_protocol_version(params),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": PLUGIN_NAME, "version": "1.0.0"},
        })
    if method == "ping":
        return response(request_id, {})
    if method == "tools/list":
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
    """Re-wrap an output stream as UTF-8 for the MCP stdio transport."""
    return io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace", write_through=True)


def handle(line: str) -> dict[str, Any] | None:
    try:
        return dispatch(json.loads(line))
    except (json.JSONDecodeError, TypeError) as exc:
        return response(None, error={"code": -32700, "message": str(exc)})
    except Exception as exc:  # one bad message must never kill the server
        return response(None, error={"code": -32603, "message": f"Internal critic server error: {exc}"})


def main() -> None:
    """Serve JSON-RPC over stdio until the client closes the transport."""
    stdin, stdout = sys.stdin.buffer, utf8_writer(sys.stdout)
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


if __name__ == "__main__":
    main()
