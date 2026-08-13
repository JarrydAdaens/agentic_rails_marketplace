# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.

"""Exercise a consultation server's real CLI resolver under Cursor's empty PATH."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def load_server(path: Path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(f"sparse_{path.parent.parent.name}", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: cursor-cli-resolution-smoke.py SERVER PROVIDER")
    server_path = Path(sys.argv[1]).resolve()
    provider = sys.argv[2]
    module = load_server(server_path)

    os.environ["PATH"] = ""
    for name in ("USERPROFILE", "LOCALAPPDATA", "APPDATA"):
        os.environ.pop(name, None)

    if server_path.parent.parent.name == "local-advisor-guardrail":
        command = module.cursor_command(str(Path.cwd()))
    elif provider == "cursor":
        model = getattr(module, "BUILTIN_DEFAULT_MODEL", "cursor-grok-4.6-high")
        command = module.command(model)
    else:
        command = module.command()

    first = Path(command[0])
    if not first.is_absolute() or not first.is_file():
        raise RuntimeError(f"{provider} command does not start with an absolute executable: {command}")
    prefix = command[:4] if first.name.casefold() == "cmd.exe" else command[:1]
    if len(prefix) == 4:
        shim = Path(prefix[3])
        if not shim.is_absolute() or not shim.is_file():
            raise RuntimeError(f"{provider} shim is not absolute and existing: {prefix}")
    if provider == "codex" and len(prefix) == 4 and not shutil.which("node.exe"):
        raise RuntimeError("Codex npm shim resolved without a spawnable node.exe on PATH")

    completed = subprocess.run(
        [*prefix, "--help"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"{provider} resolved but could not spawn --help ({completed.returncode}): "
            f"{completed.stderr or completed.stdout}"
        )
    print(json.dumps({
        "provider": provider,
        "command": command,
        "node": shutil.which("node.exe"),
        "path": os.environ.get("PATH", ""),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
