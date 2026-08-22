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

"""Merge this plugin's Cursor hooks into the user-level hooks.json file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SOURCE_HOOKS = Path("hooks") / "cursor-hooks.json"


def default_hooks_file() -> Path:
    return Path.home() / ".cursor" / "hooks.json"


def install_user_hooks(plugin_root: Path, hooks_file: Path | None = None) -> tuple[Path, int]:
    target = hooks_file or default_hooks_file()
    payload = _load_source(plugin_root)
    document = _load_document(target)
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise RuntimeError(f"{target} has a non-object hooks field")
    _strip_plugin(hooks, plugin_root)
    added = 0
    for event, entries in payload.items():
        rewritten = [_rewrite_entry(entry, plugin_root) for entry in entries]
        existing = hooks.setdefault(event, [])
        if not isinstance(existing, list):
            raise RuntimeError(f"{target} hooks.{event} is not an array")
        existing.extend(rewritten)
        added += len(rewritten)
    _write_document(target, document)
    return target, added


def remove_user_hooks(plugin_root: Path, hooks_file: Path | None = None) -> tuple[Path, int]:
    target = hooks_file or default_hooks_file()
    if not target.is_file():
        return target, 0
    document = _load_document(target)
    hooks = document.get("hooks")
    if not isinstance(hooks, dict):
        raise RuntimeError(f"{target} has a non-object hooks field")
    removed = _strip_plugin(hooks, plugin_root)
    _write_document(target, document)
    return target, removed


def _load_source(plugin_root: Path) -> dict[str, list[dict[str, Any]]]:
    path = plugin_root / SOURCE_HOOKS
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"could not read {path}: {exc}") from exc
    hooks = raw.get("hooks")
    if not isinstance(hooks, dict) or not hooks:
        raise RuntimeError(f"{path} has no hooks object")
    parsed: dict[str, list[dict[str, Any]]] = {}
    for event, entries in hooks.items():
        if not isinstance(entries, list) or not entries:
            raise RuntimeError(f"{path} hooks.{event} must be a non-empty array")
        parsed[str(event)] = [dict(entry) for entry in entries]
    return parsed


def _load_document(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "hooks": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    raw.setdefault("version", 1)
    raw.setdefault("hooks", {})
    return raw


def _write_document(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(document, indent=2) + "\n"
    if path.is_file():
        path.with_name(path.name + ".bak").write_bytes(path.read_bytes())
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(encoded, encoding="utf-8")
    tmp.replace(path)


def _strip_plugin(hooks: dict[str, Any], plugin_root: Path) -> int:
    removed = 0
    empty: list[str] = []
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        kept = [entry for entry in entries if not _owns_entry(entry, plugin_root)]
        removed += len(entries) - len(kept)
        if kept:
            hooks[event] = kept
        else:
            empty.append(event)
    for event in empty:
        del hooks[event]
    return removed


def _owns_entry(entry: Any, plugin_root: Path) -> bool:
    if not isinstance(entry, dict):
        return False
    command = str(entry.get("command") or "")
    text = _normalize(command)
    root = _normalize(str(plugin_root.resolve()))
    if root and root in text:
        return True
    name = plugin_root.name.casefold()
    return f"/{name}/" in f"/{text}/" and "launch.py" in text


def _rewrite_entry(entry: dict[str, Any], plugin_root: Path) -> dict[str, Any]:
    rewritten = dict(entry)
    command = rewritten.get("command")
    if not isinstance(command, str) or not command.strip():
        raise RuntimeError("hook entry is missing a command")
    rewritten["command"] = _rewrite_command(command, plugin_root)
    return rewritten


def _rewrite_command(command: str, plugin_root: Path) -> str:
    launch = plugin_root / "scripts" / "launch.py"
    if not launch.is_file():
        raise RuntimeError(f"missing launcher: {launch}")
    parts: list[str] = []
    for token in command.split():
        normalized = token.replace("\\", "/")
        if normalized in {"./scripts/launch.py", "scripts/launch.py"}:
            parts.append(_quote(launch))
            continue
        if normalized.startswith("./hooks/") or normalized.startswith("hooks/"):
            rel = normalized[2:] if normalized.startswith("./") else normalized
            target = plugin_root / rel
            if not target.is_file():
                raise RuntimeError(f"missing hook script: {target}")
            parts.append(_quote(target))
            continue
        parts.append(token)
    return " ".join(parts)


def _quote(path: Path) -> str:
    return f'"{path.resolve()}"'


def _normalize(value: str) -> str:
    return value.replace("\\", "/").replace('"', "").casefold()
