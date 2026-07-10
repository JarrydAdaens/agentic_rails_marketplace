"""SessionStart context injection: put the Quota Advisor Protocol into context.

A SessionStart hook's stdout is added to the session's context, which replaces
the installer-era step of appending the protocol to the target project's
CLAUDE.md. Missing protocol file exits silently — never block startup.
"""

import sys
from pathlib import Path


def main() -> None:
    protocol = Path(__file__).resolve().parent.parent / "advisor-protocol.md"
    try:
        print(protocol.read_text(encoding="utf-8"))
    except OSError:
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
