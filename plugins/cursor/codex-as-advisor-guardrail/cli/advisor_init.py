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

"""Write the default harness config for codex-as-advisor-guardrail."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(_LIB))

from advisor_config import (  # noqa: E402
    CONFIG_RELATIVE_PATH,
    write_default_config,
)
from windows_runtime import restore_windows_environment  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    restore_windows_environment()
    parser = argparse.ArgumentParser(
        description="Write harness/codex-as-advisor-guardrail/config.json with defaults and comments."
    )
    parser.add_argument(
        "--workspace",
        default=os.environ.get("AGENTIC_RAILS_WORKSPACE") or os.getcwd(),
        help="Project root where the harness config should be created",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing config file",
    )
    args = parser.parse_args(argv)

    try:
        path = write_default_config(args.workspace, force=args.force)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Could not write advisor config: {exc}", file=sys.stderr)
        return 1

    print("Codex-as-advisor config initialized")
    print(f"Path: {path}")
    print(f"Relative: {CONFIG_RELATIVE_PATH.as_posix()}")
    print(
        "Edit that JSONC file to change enabled, model, effort, fast, "
        "consult_timeout_seconds, and health_timeout_seconds. "
        "// comments are allowed. Env vars CODEX_ADVISOR_TIMEOUT_SECONDS and "
        "CODEX_ADVISOR_HEALTH_TIMEOUT_SECONDS override the matching timeout fields when set."
    )
    print("The generated file documents both timeout fields directly above their values.")
    print("Re-run the codex-advisor-health skill (or start a new session) after edits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
