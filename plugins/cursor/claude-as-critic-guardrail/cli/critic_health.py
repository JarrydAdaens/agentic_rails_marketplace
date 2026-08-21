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

"""Explicit health retest for mid-session critic re-enable."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))

from critic_health import run_health_probe  # noqa: E402
from windows_runtime import restore_windows_environment  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    restore_windows_environment()
    parser = argparse.ArgumentParser(description="Retest Claude-as-critic health for a session.")
    parser.add_argument(
        "--session-id",
        default=os.environ.get("CURSOR_SESSION_ID")
        or os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("AGENTIC_RAILS_SESSION_ID")
        or "manual",
        help="Session id whose health markers should be updated",
    )
    parser.add_argument(
        "--workspace",
        default=os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd(),
        help="Project root containing harness/claude-as-critic-guardrail/config.json",
    )
    args = parser.parse_args(argv)

    result = run_health_probe(args.session_id, workspace=args.workspace, mark_pending_first=True)
    print(result.status_block())
    return 0 if result.online else 1


if __name__ == "__main__":
    raise SystemExit(main())
