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

"""Shared marker-path helper for the advisor-guardrail hooks.

Consult markers are per-session flags: advisor_marker.py creates one when the
advisor subagent is consulted, advisor_gate.py checks for it before allowing
the session's first write, and advisor_cleanup.py removes stale ones. They
live in the system temp directory — session IDs are globally unique, and
keeping markers out of the target project means the guardrail needs no
.gitignore entry there.
"""

from __future__ import annotations

import tempfile
from pathlib import Path


def marker_dir() -> Path:
    return Path(tempfile.gettempdir()) / "advisor-guardrail-markers"


def legacy_marker_dir() -> Path:
    return Path(tempfile.gettempdir()) / "claude-advisor-markers"


def marker_path(session_id: str) -> Path:
    return marker_dir() / f"advisor-consulted-{session_id}"


def legacy_marker_path(session_id: str) -> Path:
    return legacy_marker_dir() / f"advisor-consulted-{session_id}"


def has_marker(session_id: str) -> bool:
    return marker_path(session_id).exists() or legacy_marker_path(session_id).exists()
