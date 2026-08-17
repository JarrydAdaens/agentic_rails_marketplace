from __future__ import annotations
import tempfile
from pathlib import Path

PLUGIN_NAME = "claude-as-critic-guardrail"


def marker_dir(): return Path(tempfile.gettempdir()) / f"{PLUGIN_NAME}-markers"
def marker_path(session_id): return marker_dir() / f"critic-consulted-{session_id}"
def has_marker(session_id): return marker_path(session_id).exists()
