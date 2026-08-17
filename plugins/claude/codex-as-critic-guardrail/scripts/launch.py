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

"""Cross-platform launcher: restore PATH on Windows, then run a plugin Python script via uv."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
LIB = PLUGIN_ROOT / "lib"
sys.path.insert(0, str(LIB))

from windows_runtime import resolve_cli, restore_windows_environment  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("launch.py requires a Python script path (and optional args).", file=sys.stderr)
        return 64

    restore_windows_environment()
    target = Path(args[0])
    if not target.is_file():
        candidate = PLUGIN_ROOT / args[0]
        if candidate.is_file():
            target = candidate
        else:
            print(f"Script not found: {args[0]}", file=sys.stderr)
            return 66

    try:
        uv = resolve_cli("uv")
    except RuntimeError as exc:
        # Fall back to the current interpreter when uv is unavailable.
        print(f"uv not found ({exc}); using {sys.executable}", file=sys.stderr)
        command = [sys.executable, str(target), *args[1:]]
    else:
        command = [*uv, "run", "--no-project", "python", str(target), *args[1:]]

    env = os.environ.copy()
    completed = subprocess.run(command, check=False, env=env)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
