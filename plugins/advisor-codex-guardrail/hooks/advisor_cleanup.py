"""SessionStart cleanup: delete stale advisor-consult markers.

Markers are per-session, so old sessions leave orphaned files behind. Anything
older than 24 hours can never belong to a live session and is removed.
"""

import sys
import time

from advisor_markers import marker_dir

MAX_AGE_SECONDS = 24 * 60 * 60


def main() -> None:
    cutoff = time.time() - MAX_AGE_SECONDS
    directory = marker_dir()
    if not directory.is_dir():
        return
    for marker in directory.glob("advisor-consulted-*"):
        try:
            if marker.stat().st_mtime < cutoff:
                marker.unlink()
        except OSError:
            pass  # another session may have removed it; never block startup


if __name__ == "__main__":
    main()
    sys.exit(0)
