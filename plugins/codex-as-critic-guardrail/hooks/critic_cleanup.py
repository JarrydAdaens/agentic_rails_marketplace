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

"""SessionStart cleanup: delete stale critic consult and health markers."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from critic_markers import legacy_marker_dirs, marker_dir

MAX_AGE_SECONDS = 24 * 60 * 60


def sweep(directory: Path, cutoff: float) -> None:
    if not directory.is_dir():
        return
    for pattern in ("critic-consulted-*", "critic-health-*.json", "mcp-server-*.json"):
        for marker in directory.glob(pattern):
            try:
                if marker.stat().st_mtime < cutoff:
                    marker.unlink()
            except OSError:
                pass


def main() -> None:
    cutoff = time.time() - MAX_AGE_SECONDS
    sweep(marker_dir(), cutoff)
    for legacy in legacy_marker_dirs():
        sweep(legacy, cutoff)
        try:
            legacy.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    main()
    sys.exit(0)
