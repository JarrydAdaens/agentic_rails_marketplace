"""Shared marker-path helper for the advisor-codex-guardrail hooks.

Consult markers are per-session flags: advisor_marker.py creates one when the
consult_advisor tool is used, advisor_gate.py checks for it before allowing the
session's first apply_patch, and advisor_cleanup.py removes stale ones. They
live in the system temp directory — session IDs are globally unique, and
keeping markers out of the target project means the guardrail needs no
.gitignore entry there.
"""

from __future__ import annotations

import tempfile
from pathlib import Path


def marker_dir() -> Path:
    return Path(tempfile.gettempdir()) / "advisor-codex-guardrail-markers"


def marker_path(session_id: str) -> Path:
    return marker_dir() / f"advisor-consulted-{session_id}"


def has_marker(session_id: str) -> bool:
    return marker_path(session_id).exists()
