"""Structured error codes for the autonomous crawler.

Each error code is a machine-readable string constant.  Human-readable
messages continue to live in ``error_log`` and ``messages`` as before;
these codes are additive metadata for API consumers and persisted state.
"""
from __future__ import annotations

from typing import Any

# --- Error code constants ---

LLM_CONFIG_INVALID = "LLM_CONFIG_INVALID"
LLM_PROVIDER_UNREACHABLE = "LLM_PROVIDER_UNREACHABLE"
LLM_RESPONSE_INVALID = "LLM_RESPONSE_INVALID"

FETCH_UNSUPPORTED_SCHEME = "FETCH_UNSUPPORTED_SCHEME"
FETCH_HTTP_ERROR = "FETCH_HTTP_ERROR"
BROWSER_RENDER_FAILED = "BROWSER_RENDER_FAILED"

EXTRACTION_EMPTY = "EXTRACTION_EMPTY"
SELECTOR_INVALID = "SELECTOR_INVALID"
VALIDATION_FAILED = "VALIDATION_FAILED"
ANTI_BOT_BLOCKED = "ANTI_BOT_BLOCKED"

RECON_FAILED = "RECON_FAILED"

# --- Exception-to-code mapping for LLM errors ---


def classify_llm_error(exc: Exception) -> str:
    """Return the most specific error code for an LLM-related exception.

    Falls back to ``LLM_RESPONSE_INVALID`` for unknown exception types.
    """
    # Lazy import to avoid circular dependency.
    from .llm.openai_compatible import LLMConfigurationError, LLMResponseError

    if isinstance(exc, LLMConfigurationError):
        return LLM_CONFIG_INVALID
    if isinstance(exc, LLMResponseError) and exc.error_code:
        return exc.error_code
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return LLM_PROVIDER_UNREACHABLE
    return LLM_RESPONSE_INVALID


def format_error_entry(code: str, message: str, **details: Any) -> str:
    """Build a human-readable error_log entry that includes the code prefix.

    The ``message`` portion is unchanged; the code is prepended so that
    both humans and machines can parse the entry.
    """
    if details:
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        return f"[{code}] {message} ({detail_str})"
    return f"[{code}] {message}"
