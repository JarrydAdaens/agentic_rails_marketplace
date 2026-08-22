"""Print the installed Claude critic Cursor-plugin version and file timestamp."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def main() -> int:
    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    try:
        version = version_file.read_text(encoding="utf-8").strip()
        edited = datetime.fromtimestamp(version_file.stat().st_mtime).astimezone()
    except OSError as exc:
        print(f"Could not read critic version: {exc}")
        return 1
    print(f"Version is {version} last edited {edited.strftime('%H:%M %d-%m-%Y')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
