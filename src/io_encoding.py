"""
Ensure stdout/stderr use UTF-8 on Windows so logging, tabulate, and print()
never raise UnicodeEncodeError (cp1252 / 'charmap' codec).

Import and call ensure_utf8_stdio() before logging.basicConfig in entry points.
"""

from __future__ import annotations

import sys


def ensure_utf8_stdio() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, AttributeError, ValueError, TypeError):
            pass
