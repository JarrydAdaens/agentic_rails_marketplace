"""Print the installed Cursor advisor plugin version and edit timestamp."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

def main() -> int:
    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    version = version_file.read_text(encoding="utf-8").strip()
    edited = datetime.fromtimestamp(version_file.stat().st_mtime).strftime("%H:%M %d-%m-%Y")
    print(f"Version is {version} last edited {edited}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
