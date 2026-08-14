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

"""Shared UTF-8 stdio helper for the codex-as-advisor-guardrail hooks.

Claude Code speaks UTF-8 to a hook in both directions, but on Windows a piped
stdio stream defaults to the ANSI code page (cp1252). Left alone, a hook payload
decodes into mojibake and any non-cp1252 character a hook prints -- an em dash in
the protocol markdown, for instance -- either mangles or raises on the way out.
"""

from __future__ import annotations

import sys
from typing import IO, Any


def force_utf8(*streams: IO[Any]) -> None:
    """Re-encode the given stdio streams as UTF-8, defaulting to stdin and stdout.

    Streams that cannot be reconfigured (a StringIO substituted by a test, for
    example) are left alone rather than treated as an error.
    """
    for stream in streams or (sys.stdin, sys.stdout):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
