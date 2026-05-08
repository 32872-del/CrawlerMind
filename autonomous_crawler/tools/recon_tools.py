"""LangChain-compatible wrappers around deterministic HTML recon helpers."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from .html_recon import (
    build_recon_report,
    detect_anti_bot as detect_anti_bot_from_html,
    detect_framework as detect_framework_from_html,
    discover_api_endpoints as discover_api_endpoints_from_html,
    fetch_html,
)
from .access_diagnostics import diagnose_access as diagnose_access_from_html


@tool
def detect_framework(url: str) -> str:
    """Detect frontend framework markers from fetched HTML."""
    fetch = fetch_html(url)
    if fetch.error:
        return _json({"framework": "unknown", "confidence": 0.0, "error": fetch.error})
    framework = detect_framework_from_html(fetch.html)
    return _json(
        {
            "framework": framework,
            "confidence": 0.8 if framework != "unknown" else 0.0,
            "status_code": fetch.status_code,
        }
    )


@tool
def discover_api_endpoints(url: str) -> str:
    """Discover API-like endpoint references in fetched HTML."""
    fetch = fetch_html(url)
    if fetch.error:
        return _json({"endpoints": [], "total": 0, "error": fetch.error})
    endpoints = discover_api_endpoints_from_html(fetch.html, base_url=fetch.url)
    return _json({"endpoints": endpoints, "total": len(endpoints)})


@tool
def detect_anti_bot(url: str) -> str:
    """Detect common anti-bot challenge markers in fetched HTML."""
    fetch = fetch_html(url)
    if fetch.error:
        return _json(
            {
                "detected": True,
                "type": "fetch_error",
                "severity": "unknown",
                "indicators": [fetch.error],
            }
        )
    return _json(detect_anti_bot_from_html(fetch.html))


@tool
def analyze_dom_structure(url: str) -> str:
    """Analyze repeated DOM containers and candidate field selectors."""
    fetch = fetch_html(url)
    if fetch.error:
        return _json(
            {
                "has_pagination": False,
                "pagination_type": "none",
                "product_selector": "",
                "item_count": 0,
                "field_selectors": {},
                "candidates": [],
                "error": fetch.error,
            }
        )
    report = build_recon_report(fetch.url, fetch.html)
    return _json(report["dom_structure"])


@tool
def diagnose_access(url: str, target_selector: str = "") -> str:
    """Diagnose challenge, JS shell, structured data, and API-hint signals."""
    fetch = fetch_html(url)
    if fetch.error:
        return _json({
            "ok": False,
            "findings": ["fetch_failed"],
            "signals": {"url": url, "error": fetch.error},
            "recommendations": [{
                "type": "fetch_error",
                "reason": "The page could not be fetched for access diagnostics.",
                "action": "Check URL, network, or permitted access.",
            }],
        })
    return _json(diagnose_access_from_html(fetch.html, url=fetch.url, target_selector=target_selector))


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
