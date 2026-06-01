"""Crawler-Mind: AI-powered autonomous web crawler agent."""
from __future__ import annotations

import sys

# Fix Windows console encoding for Unicode characters (GBP, EUR, CJK, etc.)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
