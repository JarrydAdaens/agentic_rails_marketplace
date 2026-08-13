"""Restore Cursor's stripped Windows environment and resolve local CLI shims."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Callable

RegistryReader = Callable[[str, str], str | None]
_PERCENT_VAR = re.compile(r"%([^%]+)%")


def _registry_value(key_path: str, name: str) -> str | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        hive_name, relative = key_path.split("\\", 1)
        hive = winreg.HKEY_CURRENT_USER if hive_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        with winreg.OpenKey(hive, relative) as key:
            value, _kind = winreg.QueryValueEx(key, name)
        return str(value) if value else None
    except (OSError, ValueError):
        return None


def _expand(value: str, environment: dict[str, str]) -> str:
    lookup = {key.casefold(): item for key, item in environment.items()}
    expanded = value
    for _ in range(4):
        replacement = _PERCENT_VAR.sub(
            lambda match: lookup.get(match.group(1).casefold(), match.group(0)),
            expanded,
        )
        if replacement == expanded:
            break
        expanded = replacement
    return expanded


def _prepend_path(environment: dict[str, str], entries: list[str]) -> None:
    combined = entries + environment.get("PATH", "").split(os.pathsep)
    unique: list[str] = []
    seen: set[str] = set()
    for entry in combined:
        clean = entry.strip().strip('"')
        if not clean:
            continue
        key = os.path.normcase(os.path.normpath(clean))
        if key not in seen:
            seen.add(key)
            unique.append(clean)
    environment["PATH"] = os.pathsep.join(unique)


def restore_windows_environment(
    registry_reader: RegistryReader | None = None,
) -> dict[str, str]:
    """Restore the process environment Cursor omits before resolving child CLIs."""
    environment = os.environ
    if os.name != "nt":
        return environment

    read = registry_reader or _registry_value
    volatile = r"HKCU\Volatile Environment"
    for name in ("USERPROFILE", "LOCALAPPDATA", "APPDATA"):
        if not environment.get(name):
            value = read(volatile, name)
            if value:
                environment[name] = _expand(value, environment)

    system_root = environment.get("SystemRoot") or environment.get("WINDIR") or r"C:\Windows"
    environment.setdefault("SystemRoot", system_root)
    environment.setdefault("WINDIR", system_root)
    user_path = read(r"HKCU\Environment", "Path") or ""
    machine_path = read(
        r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        "Path",
    ) or ""

    candidates = [
        str(Path(system_root) / "System32"),
        system_root,
        str(Path(system_root) / "System32" / "Wbem"),
        str(Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0"),
    ]
    for registry_path in (user_path, machine_path):
        candidates.extend(
            _expand(registry_path, environment).split(os.pathsep)
            if registry_path
            else []
        )

    local = environment.get("LOCALAPPDATA")
    roaming = environment.get("APPDATA")
    profile = environment.get("USERPROFILE")
    program_files = environment.get("ProgramFiles", r"C:\Program Files")
    if local:
        candidates.extend([
            str(Path(local) / "Microsoft" / "WinGet" / "Links"),
            str(Path(local) / "cursor-agent"),
            str(Path(local) / "pnpm"),
            str(Path(local) / "Programs" / "OpenAI" / "Codex" / "bin"),
            str(Path(local) / "OpenAI" / "Codex" / "bin"),
        ])
    if roaming:
        candidates.append(str(Path(roaming) / "npm"))
    if profile:
        candidates.extend([
            str(Path(profile) / ".local" / "bin"),
            str(Path(profile) / ".cargo" / "bin"),
            str(Path(profile) / ".volta" / "bin"),
        ])
    candidates.append(str(Path(program_files) / "nodejs"))
    _prepend_path(environment, candidates)
    return environment


def _known_candidates(name: str, environment: dict[str, str]) -> list[Path]:
    local = environment.get("LOCALAPPDATA")
    roaming = environment.get("APPDATA")
    profile = environment.get("USERPROFILE")
    values: list[Path] = []
    if name == "agent" and local:
        values.extend([
            Path(local) / "cursor-agent" / "agent.cmd",
            Path(local) / "cursor-agent" / "agent.exe",
        ])
    elif name == "codex":
        if local:
            values.extend([
                Path(local) / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe",
                Path(local) / "OpenAI" / "Codex" / "bin" / "codex.exe",
            ])
        if roaming:
            values.append(Path(roaming) / "npm" / "codex.cmd")
    elif name == "claude":
        if local:
            values.append(Path(local) / "pnpm" / "claude.cmd")
        if roaming:
            values.append(Path(roaming) / "npm" / "claude.cmd")
        if profile:
            values.extend([
                Path(profile) / ".local" / "bin" / "claude.exe",
                Path(profile) / ".claude" / "local" / "claude.exe",
            ])
    return values


def _ensure_node(environment: dict[str, str]) -> None:
    node = shutil.which("node.exe", path=environment.get("PATH"))
    if node:
        return
    local = environment.get("LOCALAPPDATA")
    roaming = environment.get("APPDATA")
    profile = environment.get("USERPROFILE")
    program_files = environment.get("ProgramFiles", r"C:\Program Files")
    candidates = [Path(program_files) / "nodejs" / "node.exe"]
    if local:
        candidates.extend([
            Path(local) / "pnpm" / "node.exe",
            Path(local) / "Programs" / "nodejs" / "node.exe",
        ])
    if roaming:
        candidates.append(Path(roaming) / "npm" / "node.exe")
    if profile:
        candidates.append(Path(profile) / ".volta" / "bin" / "node.exe")
    nvm_symlink = environment.get("NVM_SYMLINK")
    if nvm_symlink:
        candidates.append(Path(nvm_symlink) / "node.exe")
    for candidate in candidates:
        if candidate.is_file():
            _prepend_path(environment, [str(candidate.parent)])
            return
    raise RuntimeError(
        "Codex uses an npm command shim, but node.exe was not found after "
        "restoring the Windows user and machine PATH."
    )


def resolve_cli(
    name: str,
    registry_reader: RegistryReader | None = None,
) -> list[str]:
    """Return an absolute, Windows-spawnable command prefix for a local CLI."""
    environment = restore_windows_environment(registry_reader)
    executable = next(
        (str(candidate.resolve()) for candidate in _known_candidates(name, environment) if candidate.is_file()),
        None,
    )
    if not executable:
        executable = shutil.which(name, path=environment.get("PATH"))
    if not executable:
        raise RuntimeError(
            f"{name.title()} executable was not found after restoring the "
            "Windows user and machine PATH."
        )
    executable = str(Path(executable).resolve())
    if Path(executable).suffix.casefold() in {".cmd", ".bat"}:
        if name == "codex":
            _ensure_node(environment)
        system_root = environment.get("SystemRoot", r"C:\Windows")
        command_processor = Path(system_root) / "System32" / "cmd.exe"
        if not command_processor.is_file():
            raise RuntimeError(f"Windows command processor not found at {command_processor}.")
        return [str(command_processor), "/d", "/c", executable]
    return [executable]
