from __future__ import annotations
from datetime import datetime
from pathlib import Path
def main() -> int:
    version=Path(__file__).resolve().parents[1] / "VERSION"
    print(f"Version is {version.read_text(encoding='utf-8').strip()} last edited {datetime.fromtimestamp(version.stat().st_mtime).strftime('%H:%M %d-%m-%Y')}"); return 0
if __name__ == "__main__": raise SystemExit(main())
