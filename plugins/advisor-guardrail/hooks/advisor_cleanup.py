"""SessionStart cleanup: delete stale advisor-consult markers.

Markers are per-session, so old sessions leave orphaned files behind. Anything
older than 24 hours can never belong to a live session and is removed.
"""

import sys
import time

from advisor_markers import legacy_marker_dir, marker_dir

MAX_AGE_SECONDS = 24 * 60 * 60


def main() -> None:
    cutoff = time.time() - MAX_AGE_SECONDS
    for directory in (marker_dir(), legacy_marker_dir()):
        if not directory.is_dir():
            continue
        for marker in directory.glob("advisor-consulted-*"):
            try:
                if marker.stat().st_mtime < cutoff:
                    marker.unlink()
            except OSError:
                pass  # another session may have removed it; never block startup


if __name__ == "__main__":
    main()
    sys.exit(0)
