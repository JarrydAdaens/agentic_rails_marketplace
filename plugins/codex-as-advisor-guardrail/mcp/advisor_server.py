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

"""Claude Code stdio MCP server for consult_advisor (thin JSON-RPC over lib/)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any, TextIO

MCP_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = MCP_DIR.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))
sys.path.insert(0, str(PLUGIN_ROOT / "hooks"))

from advisor_consult import (  # noqa: E402
    DEFAULT_TIMEOUT_SECONDS,
    FIELD_DESCRIPTIONS,
    FIELDS,
    PLUGIN_VERSION,
    STAGES,
    TIMEOUT_ENV_VAR,
    build_prompt,
    classify_failure,
    command,
    consult,
    is_hard_failure_message,
    timeout_seconds,
    validate_arguments,
)
from advisor_session import mark_offline  # noqa: E402

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

TOOL = {
    "name": "consult_advisor",
    "description": (
        "Consult the constructive, read-only Codex advisor for a cross-vendor second "
        "opinion before substantive work or completion."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": FIELD_DESCRIPTIONS["task"]},
            "stage": {
                "type": "string",
                "enum": list(STAGES),
                "description": FIELD_DESCRIPTIONS["stage"],
            },
            "approach": {"type": "string", "description": FIELD_DESCRIPTIONS["approach"]},
            "evidence": {"type": "string", "description": FIELD_DESCRIPTIONS["evidence"]},
            "question": {"type": "string", "description": FIELD_DESCRIPTIONS["question"]},
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

    method, request_id, params = message.get("method"), message["id"], message.get("params") or {}
    if method == "initialize":
        return response(request_id, {
            "protocolVersion": negotiate_protocol_version(params),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "codex-as-advisor-guardrail", "version": PLUGIN_VERSION},
        })
    if method == "ping":
        return response(request_id, {})
    if method == "tools/list":
        return response(request_id, {"tools": [TOOL]})
    if method == "tools/call":
        if params.get("name") != "consult_advisor":
            return response(request_id, error={"code": -32601, "message": "Unknown tool"})
        try:
            advice = consult(params.get("arguments"))
            return response(request_id, {"content": [{"type": "text", "text": advice}], "isError": False})
        except (ValueError, RuntimeError) as exc:
            text = str(exc)
            session = os_environ_session()
            if session and is_hard_failure_message(text):
                mark_offline(session, text)
            return response(request_id, {"content": [{"type": "text", "text": text}], "isError": True})
    return response(request_id, error={"code": -32601, "message": "Method not found"})


def os_environ_session() -> str | None:
    import os

    return os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("AGENTIC_RAILS_SESSION_ID")


def utf8_writer(stream: TextIO) -> TextIO:
    return io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace", write_through=True)


def handle(line: str) -> dict[str, Any] | None:
    try:
        return dispatch(json.loads(line))
    except (json.JSONDecodeError, TypeError) as exc:
        return response(None, error={"code": -32700, "message": str(exc)})
    except Exception as exc:  # noqa: BLE001 — one bad message must never kill the server
        return response(None, error={"code": -32603, "message": f"Internal advisor server error: {exc}"})


def main() -> None:
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
