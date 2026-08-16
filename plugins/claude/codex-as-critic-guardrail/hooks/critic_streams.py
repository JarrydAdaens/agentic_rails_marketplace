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

"""Shared stdio helpers for the codex-as-critic-guardrail hooks.

A host speaks UTF-8 to a hook in both directions, but Windows works against that
twice. A piped stdio stream defaults to the ANSI code page (cp1252), so an em
dash in the protocol markdown mangles on the way out. Separately, the Cursor CLI
prefixes the payload it pipes in with a UTF-8 BOM, which `json.loads` rejects --
and because a gate fails open when it cannot parse its payload, the BOM alone is
enough to allow the very write the gate was installed to deny.

`utf-8-sig` discards a leading BOM when decoding but *emits* one when encoding,
so it is applied to stdin only. Stdout stays plain UTF-8: a BOM there would
corrupt the decision JSON the host reads back.
"""

from __future__ import annotations

import json
import sys
from typing import IO, Any

BOM = "﻿"


def _reconfigure(stream: IO[Any] | None, encoding: str) -> None:
    """Re-encode one stream, leaving alone any stream that cannot be changed.

    A StringIO substituted by a test has no `reconfigure`; that is not an error.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding=encoding, errors="replace")


def force_utf8(*streams: IO[Any]) -> None:
    """Re-encode stdio as UTF-8, tolerating a BOM on the way in.

    With no arguments this configures the three standard streams. Explicit
    streams are treated as output and get plain UTF-8.
    """
    if streams:
        for stream in streams:
            _reconfigure(stream, "utf-8")
        return
    _reconfigure(sys.stdin, "utf-8-sig")
    _reconfigure(sys.stdout, "utf-8")
    _reconfigure(sys.stderr, "utf-8")


def read_hook_payload() -> dict[str, Any] | None:
    """Return the hook payload as a dict, or None when it cannot be read.

    None is the fail-open signal: the caller allows the action rather than block
    on a payload it does not understand. Every failure is reported on stderr,
    because a gate that fails open silently is indistinguishable from a gate that
    is working -- which is exactly how a BOM disabled these gates unnoticed.
    """
    try:
        raw = sys.stdin.read()
    except (OSError, UnicodeDecodeError) as exc:
        print(
            f"critic hook could not read stdin ({type(exc).__name__}: {exc}); allowing.",
            file=sys.stderr,
        )
        return None

    # Belt and braces: utf-8-sig already strips a BOM off a real pipe, but the
    # character still arrives when a caller hands us an already-decoded stream.
    text = raw.lstrip(BOM)
    if not text.strip():
        return None

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        print(
            f"critic hook received invalid JSON on stdin ({exc}); "
            f"payload starts with {text[:40]!r}; allowing.",
            file=sys.stderr,
        )
        return None

    if not isinstance(payload, dict):
        print(
            f"critic hook received a {type(payload).__name__} on stdin, expected an object; allowing.",
            file=sys.stderr,
        )
        return None

    return payload
