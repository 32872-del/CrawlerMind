"""LLM audit helpers for bounded, redacted decision records."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

MAX_PREVIEW_LENGTH = 2000

_SECRET_PATTERNS = [
    re.compile(r"(api_key[\"'\s:=]+)[^\n,;}\"]*", re.I),
    re.compile(r"(authorization[\"'\s:=]+)[^\n,;}\"]*", re.I),
    re.compile(r"(cookie[\"'\s:=]+)[^\n,;}\"]*", re.I),
    re.compile(r"(token[\"'\s:=]+)[^\n,;}\"]*", re.I),
    re.compile(r"(password[\"'\s:=]+)[^\n,;}\"]*", re.I),
    re.compile(r"(secret[\"'\s:=]+)[^\n,;}\"]*", re.I),
]

_REDACTED = r"\1[REDACTED]"


def redact_preview(text: str) -> tuple[str, bool]:
    """Redact common secret patterns from text.

    Returns (redacted_text, was_modified).
    """
    modified = False
    result = text
    for pattern in _SECRET_PATTERNS:
        new_result = pattern.sub(_REDACTED, result)
        if new_result != result:
            modified = True
            result = new_result
    return result, modified


def build_decision_record(
    node: str,
    advisor: Any,
    input_summary: str,
    raw_response: Any,
    parsed_decision: dict[str, Any],
    accepted_fields: list[str],
    rejected_fields: list[str],
    fallback_used: bool,
) -> dict[str, Any]:
    """Build a bounded, redacted LLM decision record."""
    try:
        raw_str = json.dumps(raw_response, ensure_ascii=False, default=str)
    except Exception:
        raw_str = str(raw_response)

    raw_str = raw_str[:MAX_PREVIEW_LENGTH]
    raw_preview, secrets_redacted = redact_preview(raw_str)

    provider = getattr(advisor, "provider", "unknown")
    model = getattr(advisor, "model", "unknown")

    return {
        "node": node,
        "provider": provider,
        "model": model,
        "input_summary": input_summary[:500],
        "raw_response_preview": raw_preview,
        "secrets_redacted": secrets_redacted,
        "parsed_decision": parsed_decision,
        "accepted_fields": accepted_fields,
        "rejected_fields": rejected_fields,
        "fallback_used": fallback_used,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
