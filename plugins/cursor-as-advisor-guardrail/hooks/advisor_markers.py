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

"""Per-session marker paths for Cursor advisor consultation hooks."""

from __future__ import annotations

import tempfile
from pathlib import Path

MARKER_DIR_NAMES = ("cursor-as-advisor-guardrail-markers",)


def marker_dir() -> Path:
    return Path(tempfile.gettempdir()) / MARKER_DIR_NAMES[0]


def legacy_marker_dirs() -> list[Path]:
    return [Path(tempfile.gettempdir()) / name for name in MARKER_DIR_NAMES[1:]]


def marker_path(session_id: str) -> Path:
    return marker_dir() / f"advisor-consulted-{session_id}"


def has_marker(session_id: str) -> bool:
    return marker_path(session_id).exists()
