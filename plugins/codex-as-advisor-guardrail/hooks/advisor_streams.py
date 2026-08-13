"""UTF-8 helpers for hook stdio."""
import sys


def force_utf8(*streams):
    for stream in streams or (sys.stdin, sys.stdout):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")
