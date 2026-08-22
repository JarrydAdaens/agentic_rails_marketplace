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

"""Cursor-only fence: deny agent access under Claude Code's home tree (~/.claude).

Pure path/text match, no LLM judgment. Always emits valid JSON on stdout so
failClosed hooks never brick unrelated tools on empty/malformed stdin.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from windows_toast import notify_guardrail_online

DENY_REASON = (
    "claude-home-fence-guardrail: access to ~/.claude is banned in Cursor. "
    "Use Cursor-native skills/plugins under ~/.cursor or the agentic_rails_tooling / "
    "marketplace sources instead. Do not read, grep, glob, or shell into Claude Code's home."
)

SESSION_POLICY = (
    "HARD POLICY (claude-home-fence-guardrail): Do not read, grep, glob, write, "
    "delete, or shell into ~/.claude (Claude Code's home: skills, plugins, agents, rules, cache). "
    "Those paths are banned in Cursor. Prefer ~/.cursor skills/plugins, workspace sources, "
    "or agentic_rails_tooling / agentic_rails_marketplace. If a listed skill path is under "
    "~/.claude, ignore it and use a Cursor-native equivalent."
)

CLAUDE_HOME_TEXT_PATTERNS = (
    re.compile(r'(^|[\\/\s"\'`(=])~[\\/]\.claude([\\/]|$)', re.IGNORECASE),
    re.compile(r"%USERPROFILE%[\\/]\.claude([\\/]|$)", re.IGNORECASE),
    re.compile(r"\$env:USERPROFILE[\\/]\.claude([\\/]|$)", re.IGNORECASE),
    re.compile(r"\$\{env:USERPROFILE\}[\\/]\.claude([\\/]|$)", re.IGNORECASE),
    re.compile(r"\$HOME[\\/]\.claude([\\/]|$)", re.IGNORECASE),
    re.compile(r"\$\{HOME\}[\\/]\.claude([\\/]|$)", re.IGNORECASE),
    re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s\"'`]+[\\/]\.claude([\\/]|$)", re.IGNORECASE),
    re.compile(r"/Users/[^\\/\s\"'`]+/\.claude([\\/]|$)", re.IGNORECASE),
    re.compile(r"/home/[^\\/\s\"'`]+/\.claude([\\/]|$)", re.IGNORECASE),
)

SHELL_TOKEN_PATTERN = re.compile(
    r'(?i)(%USERPROFILE%|\$env:USERPROFILE|\$\{env:USERPROFILE\}|\$HOME|\$\{HOME\}|~'
    r'|[A-Za-z]:[\\/][^\s"\'`]+|/[^\s"\'`]+)'
)

PATH_KEYS = (
    "path",
    "file_path",
    "target_directory",
    "working_directory",
    "target_notebook",
    "notebook_path",
)


BOM = "﻿"


def force_utf8() -> None:
    """Re-encode stdio as UTF-8, tolerating a BOM on the way in.

    The Cursor CLI prefixes the payload it pipes to a hook on Windows with a
    UTF-8 BOM. `utf-8-sig` discards it when decoding but *emits* one when
    encoding, so it applies to stdin only -- a BOM on stdout would corrupt the
    decision JSON Cursor reads back.
    """
    for stream, encoding in ((sys.stdin, "utf-8-sig"), (sys.stdout, "utf-8"), (sys.stderr, "utf-8")):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding=encoding, errors="replace")


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def emit_allow() -> None:
    emit({"permission": "allow"})


def emit_deny(event: str) -> None:
    if event in ("beforeReadFile", "beforeTabFileRead"):
        emit({"permission": "deny", "user_message": DENY_REASON})
        return
    emit(
        {
            "permission": "deny",
            "user_message": DENY_REASON,
            "agent_message": DENY_REASON,
        }
    )


def emit_session_policy() -> None:
    emit({"additional_context": SESSION_POLICY})


def read_payload() -> dict[str, Any] | None:
    """Return the hook payload, or None when it cannot be read.

    None is the fail-open signal. Every failure is reported on stderr, because a
    fence that silently fails open is indistinguishable from one that is
    working -- which is exactly how a BOM disabled these hooks unnoticed.
    """
    raw = sys.stdin.read()
    # Belt and braces: utf-8-sig already strips a BOM off a real pipe, but the
    # character still arrives when a caller hands us an already-decoded stream.
    text = raw.lstrip(BOM) if raw else ""
    if not text.strip():
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(
            f"claude-home-fence received invalid JSON on stdin ({exc}); "
            f"payload starts with {text[:40]!r}; allowing.",
            file=sys.stderr,
        )
        return None
    if not isinstance(data, dict):
        print(
            f"claude-home-fence received a {type(data).__name__} on stdin, expected an object; allowing.",
            file=sys.stderr,
        )
        return None
    return data


def project_root(hook: dict[str, Any]) -> Path:
    roots = hook.get("workspace_roots") or []
    if isinstance(roots, list) and roots:
        first = roots[0]
        if isinstance(first, str) and first.strip():
            return Path(first)
    cwd = hook.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        return Path(cwd)
    return Path.cwd()


def config_disabled(root: Path) -> bool:
    config_path = root / "harness" / "claude-home-fence-guardrail" / "cursor-config.json"
    if not config_path.is_file():
        return False
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    return "enabled" in data and data["enabled"] is False


def blocked_root() -> Path | None:
    profile = os.environ.get("USERPROFILE") or os.environ.get("HOME")
    if not profile or not str(profile).strip():
        return None
    try:
        return Path(profile).expanduser().resolve() / ".claude"
    except OSError:
        return Path(profile) / ".claude"


def normalize_path_text(path_text: str) -> str | None:
    trimmed = path_text.strip().strip('"').strip("'")
    if not trimmed:
        return None
    return trimmed.replace("/", "\\")


def expand_home_placeholders(normalized: str) -> str:
    expanded = normalized
    user_profile = normalize_path_text(os.environ.get("USERPROFILE", "") or "")
    home_env = normalize_path_text(os.environ.get("HOME", "") or "")

    # Longer placeholders first so ${HOME} is not partially eaten by $HOME.
    replacements: list[tuple[str, str]] = []
    if user_profile:
        replacements.extend(
            (
                ("${env:USERPROFILE}", user_profile),
                ("$env:USERPROFILE", user_profile),
                ("%USERPROFILE%", user_profile),
            )
        )
    if home_env:
        replacements.extend(
            (
                ("${HOME}", home_env),
                ("$HOME", home_env),
            )
        )
    for needle, value in replacements:
        pattern = re.compile(re.escape(needle), re.IGNORECASE)
        expanded = pattern.sub(lambda _match, replacement=value: replacement, expanded)

    if expanded == "~" or expanded.startswith("~\\") or expanded.startswith("~/"):
        home_root = user_profile or home_env
        if home_root:
            if expanded == "~":
                expanded = home_root
            else:
                expanded = str(Path(home_root) / expanded[2:].replace("/", "\\"))
    return expanded


def path_under_claude_home(candidate: str, blocked: Path) -> bool:
    if not candidate or not str(candidate).strip():
        return False
    normalized = normalize_path_text(candidate)
    if normalized is None:
        return False

    expanded = expand_home_placeholders(normalized)
    blocked_norm = normalize_path_text(str(blocked))
    if blocked_norm is None:
        return False
    blocked_norm = blocked_norm.rstrip("\\")

    if expanded.lower() in {blocked_norm.lower(), (blocked_norm + "\\").lower()}:
        return True

    # Relative paths are not Claude-home unless already expanded to a rooted path.
    if not (len(expanded) >= 2 and expanded[1] == ":") and not expanded.startswith("\\"):
        if not expanded.startswith("/"):
            return False

    try:
        full = str(Path(expanded).resolve())
    except (OSError, RuntimeError, ValueError):
        full = expanded

    full_norm = (normalize_path_text(full) or full).rstrip("\\")
    if full_norm.lower() == blocked_norm.lower():
        return True
    prefix = blocked_norm + "\\"
    return full_norm.lower().startswith(prefix.lower())


def text_references_claude_home(text: str) -> bool:
    if not text or not text.strip():
        return False
    return any(pattern.search(text) for pattern in CLAUDE_HOME_TEXT_PATTERNS)


def tool_input_object(hook: dict[str, Any]) -> dict[str, Any] | None:
    raw = hook.get("tool_input")
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    if isinstance(raw, dict):
        return raw
    return None


def collect_candidate_paths(hook: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    file_path = hook.get("file_path")
    if isinstance(file_path, str) and file_path.strip():
        paths.append(file_path)

    tool_input = tool_input_object(hook)
    if tool_input:
        for name in PATH_KEYS:
            value = tool_input.get(name)
            if isinstance(value, str) and value.strip():
                paths.append(value)
    return paths


def shell_command(hook: dict[str, Any]) -> str | None:
    command = hook.get("command")
    if isinstance(command, str) and command.strip():
        return command
    tool_input = tool_input_object(hook)
    if tool_input:
        value = tool_input.get("command")
        if isinstance(value, str) and value.strip():
            return value
    return None


def should_deny(hook: dict[str, Any], blocked: Path) -> bool:
    for candidate in collect_candidate_paths(hook):
        if path_under_claude_home(candidate, blocked):
            return True

    command = shell_command(hook)
    if not command:
        return False
    if text_references_claude_home(command):
        return True
    for match in SHELL_TOKEN_PATTERN.finditer(command):
        if path_under_claude_home(match.group(0), blocked):
            return True
    return False


def main() -> None:
    force_utf8()
    try:
        hook = read_payload()
        if hook is None:
            # Empty/malformed stdin: allow. Never fail-closed the whole agent here.
            emit_allow()
            return

        event = str(hook.get("hook_event_name") or "")

        if event == "sessionStart":
            root = project_root(hook)
            if not config_disabled(root):
                notify_guardrail_online()
            emit_session_policy()
            return

        root = project_root(hook)
        if config_disabled(root):
            emit_allow()
            return

        blocked = blocked_root()
        if blocked is None:
            emit_allow()
            return

        if should_deny(hook, blocked):
            emit_deny(event)
            return

        emit_allow()
    except Exception:
        # Unexpected errors must not brick Cursor under failClosed.
        emit_allow()


if __name__ == "__main__":
    main()
