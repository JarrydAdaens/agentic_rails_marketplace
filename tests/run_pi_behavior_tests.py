# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.
"""Behavioral test runner for the pi guardrail TypeScript modules.

The repository's automated suite is Python; the pi guardrails are TypeScript
extensions tested with no dev dependency — pi's own bundled Node runs the
behavioral test files directly via native type stripping (the Q2 resolution
in the pi-marketplace-and-guardrail-port plan).

Usage (from the repository root):

    python tests/run_pi_behavior_tests.py

Node resolution order:
  1. ``PI_NODE_EXE`` environment variable (explicit override)
  2. ``%LOCALAPPDATA%\\pi-node\\current\\node.exe`` (pi's bundled Node)
  3. ``node`` on PATH (fallback; type stripping requires Node >= 22.18)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def find_node() -> str:
    env = os.environ.get("PI_NODE_EXE")
    if env and Path(env).is_file():
        return env

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidate = Path(local_appdata) / "pi-node" / "current" / "node.exe"
        if candidate.is_file():
            return str(candidate)

    on_path = shutil.which("node")
    if on_path:
        return on_path

    raise SystemExit(
        "No Node.js found. Set PI_NODE_EXE to a node executable "
        "(pi's bundled one lives at %LOCALAPPDATA%\\pi-node\\current\\node.exe)."
    )


def main() -> int:
    node = find_node()
    tests = sorted(ROOT.glob("plugins/pi/*/tests/*.behavior.test.ts"))
    if not tests:
        print("FAIL: no behavioral test files found under plugins/pi/*/tests/", file=sys.stderr)
        return 1

    print(f"Node: {node}")
    failures = 0
    for test in tests:
        print(f"\n=== {test.relative_to(ROOT)} ===")
        result = subprocess.run([node, str(test)], cwd=ROOT)
        if result.returncode != 0:
            failures += 1
            print(f"FAIL: {test.relative_to(ROOT)} (exit {result.returncode})")

    if failures:
        print(f"\n{failures} of {len(tests)} behavioral test file(s) failed.")
        return 1
    print(f"\nAll {len(tests)} behavioral test file(s) passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
