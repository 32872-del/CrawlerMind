"""Recon Agent - Analyzes target website structure.

Responsibilities (README Section 7):
- Detect frontend framework
- Detect SPA / SSR
- Discover APIs / XHR / GraphQL
- Detect anti-bot
- Analyze DOM / pagination

Tools (README Section 10):
- detect_framework()
- discover_api_endpoints()
- detect_anti_bot()
- analyze_dom_structure()
"""
from __future__ import annotations

from typing import Any

from .base import preserve_state
from ..tools.html_recon import build_recon_report, fetch_html


@preserve_state
def recon_node(state: dict[str, Any]) -> dict[str, Any]:
    """Recon the target URL and produce a recon_report.

    This MVP implementation uses deterministic local HTML heuristics. It can be
    replaced or enriched with MCP crawler recon tools without changing the
    downstream Strategy contract.
    """
    target_url = state.get("target_url", "")
    existing_report = state.get("recon_report", {})

    fetch_result = fetch_html(target_url)
    if fetch_result.error:
        return {
            "status": "recon_failed",
            "recon_report": {
                **existing_report,
                "target_url": target_url,
                "recon_error": fetch_result.error,
            },
            "error_log": state.get("error_log", []) + [
                f"Recon fetch failed: {fetch_result.error}"
            ],
            "messages": state.get("messages", []) + [
                f"[Recon] Failed to fetch {target_url}: {fetch_result.error}"
            ],
        }

    inferred_report = build_recon_report(fetch_result.url, fetch_result.html)
    recon_report = {
        **existing_report,
        **inferred_report,
        "fetch": {
            "status_code": fetch_result.status_code,
            "html_chars": len(fetch_result.html),
        },
    }

    return {
        "status": "recon_done",
        "recon_report": recon_report,
        "messages": state.get("messages", []) + [
            (
                f"[Recon] Analyzed {target_url} - "
                f"framework={recon_report['frontend_framework']}, "
                f"items={recon_report['dom_structure'].get('item_count', 0)}, "
                f"anti_bot={recon_report['anti_bot']['detected']}"
            )
        ],
    }
