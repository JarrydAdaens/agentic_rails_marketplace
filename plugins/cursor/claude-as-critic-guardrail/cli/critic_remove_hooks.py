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

"""Remove this plugin's hooks from the user-level Cursor hooks.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PLUGIN / "lib"))

from user_hooks import remove_user_hooks  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hooks-file")
    args = parser.parse_args(argv)
    try:
        path, removed = remove_user_hooks(
            _PLUGIN,
            Path(args.hooks_file) if args.hooks_file else None,
        )
    except (OSError, RuntimeError) as exc:
        print(f"Could not remove critic hooks: {exc}", file=sys.stderr)
        return 1
    print(f"Claude-as-critic hooks removed ({removed} entries)")
    print(f"Path: {path}")
    print("Start a new CLI session for the change to take effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
