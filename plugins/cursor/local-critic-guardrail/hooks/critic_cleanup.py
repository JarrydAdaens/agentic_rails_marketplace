from __future__ import annotations
import time
from critic_markers import marker_dir
MAX_AGE_SECONDS = 24 * 60 * 60
def main() -> None:
    directory = marker_dir()
    if not directory.is_dir(): return
    for marker in directory.glob("critic-consulted-*"):
        try:
            if marker.stat().st_mtime < time.time() - MAX_AGE_SECONDS: marker.unlink()
        except OSError: pass
if __name__ == "__main__": main()
