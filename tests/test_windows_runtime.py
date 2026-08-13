# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
RUNTIME_PATH = ROOT / "plugins" / "local-advisor-guardrail" / "mcp" / "windows_runtime.py"
SPEC = importlib.util.spec_from_file_location("tested_windows_runtime", RUNTIME_PATH)
runtime = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(runtime)


@unittest.skipUnless(os.name == "nt", "Windows environment restoration")
class WindowsRuntimeTests(unittest.TestCase):
    def test_registry_environment_resolves_cmd_shims_and_node(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local"
            roaming = root / "roaming"
            profile = root / "profile"
            agent = local / "cursor-agent" / "agent.cmd"
            codex = roaming / "npm" / "codex.cmd"
            node = local / "pnpm" / "node.exe"
            for path in (agent, codex, node):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")

            values = {
                (r"HKCU\Volatile Environment", "USERPROFILE"): str(profile),
                (r"HKCU\Volatile Environment", "LOCALAPPDATA"): str(local),
                (r"HKCU\Volatile Environment", "APPDATA"): str(roaming),
                (r"HKCU\Environment", "Path"): (
                    r"%LOCALAPPDATA%\cursor-agent;%APPDATA%\npm;%LOCALAPPDATA%\pnpm"
                ),
                (
                    r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                    "Path",
                ): r"%SystemRoot%\System32",
            }

            def read(key: str, name: str) -> str | None:
                return values.get((key, name))

            sparse = {
                "PATH": "",
                "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
                "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
            }
            with patch.dict(os.environ, sparse, clear=True):
                agent_command = runtime.resolve_cli("agent", read)
                codex_command = runtime.resolve_cli("codex", read)
                restored_path = os.environ["PATH"]

            self.assertEqual(Path(agent_command[3]), agent.resolve())
            self.assertEqual(Path(codex_command[3]), codex.resolve())
            self.assertTrue(Path(agent_command[0]).is_absolute())
            self.assertIn(str(node.parent), restored_path)
            self.assertTrue(shutil.which("node.exe", path=restored_path))

    def test_missing_cli_reports_restored_path_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            values = {
                (r"HKCU\Volatile Environment", "USERPROFILE"): directory,
                (r"HKCU\Volatile Environment", "LOCALAPPDATA"): directory,
                (r"HKCU\Volatile Environment", "APPDATA"): directory,
                (r"HKCU\Environment", "Path"): "",
                (
                    r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                    "Path",
                ): "",
            }
            with patch.dict(os.environ, {
                "PATH": "",
                "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
            }, clear=True):
                with self.assertRaisesRegex(RuntimeError, "after restoring"):
                    runtime.resolve_cli("agent", lambda key, name: values.get((key, name)))


if __name__ == "__main__":
    unittest.main()
