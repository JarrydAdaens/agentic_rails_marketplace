from __future__ import annotations
import tempfile
from pathlib import Path
def marker_dir() -> Path: return Path(tempfile.gettempdir()) / "local-critic-guardrail-markers"
def marker_path(session_id: str) -> Path: return marker_dir() / f"critic-consulted-{session_id}"
def has_marker(session_id: str) -> bool: return marker_path(session_id).exists()
