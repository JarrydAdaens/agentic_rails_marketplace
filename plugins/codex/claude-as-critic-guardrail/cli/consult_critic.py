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

"""Shell transport: stdin JSON consult_critic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))

from critic_consult import consult  # noqa: E402
from windows_runtime import restore_windows_environment  # noqa: E402


def main() -> int:
    restore_windows_environment()
    try:
        raw = sys.stdin.read()
        arguments = json.loads(raw) if raw.strip() else None
    except json.JSONDecodeError as exc:
        print(f"consult_critic stdin must be a JSON object: {exc}", file=sys.stderr)
        return 2

    try:
        advice = consult(arguments)
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(advice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
