"""Access diagnostics for crawl planning.

This module is intentionally diagnostic, not a bypass layer.  It identifies
when a page likely needs browser rendering, contains structured data or API
hints, or appears to be a managed challenge/CAPTCHA page.
"""
from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from .access_policy import decide_access
from .challenge_detector import detect_challenge_signal


CHALLENGE_PATTERNS = [
    "cf-challenge",
    "cf-browser-verification",
    "cf-mitigated",
    "checking your browser",
    "just a moment",
    "attention required",
    "captcha",
    "hcaptcha",
    "recaptcha",
    "geetest",
    "_incapsula_resource",
    "datadome",
    "perimeterx",
    "access denied",
]

API_HINT_RE = re.compile(
    r"""(?:"|')(?P<url>(?:mock://api/[^"']+|https?:\/\/[^"']*(?:/api(?:/|\?|$)|graphql|ajax)[^"']*|/(?:api(?:/|\?|$)[^"']*|[^"']*(?:graphql|ajax)[^"']*)))(?:"|')""",
    re.IGNORECASE,
)


def diagnose_access(
    html: str,
    url: str = "",
    target_selector: str = "",
    status_code: int | None = None,
    response_headers: dict[str, Any] | None = None,
    has_authorized_session: bool = False,
    proxy_enabled: bool = False,
) -> dict[str, Any]:
    """Return access signals, findings, and safe recommendations."""
    html = html or ""
    soup = BeautifulSoup(html, "lxml")
    text_chars = len(soup.get_text(" ", strip=True))
    scripts = soup.find_all("script")
    challenge_details = detect_challenge_signal(
        html,
        status_code=status_code,
        response_headers=response_headers,
    )
    challenge = challenge_details.primary_marker
    selector_error = ""
    target_count = 0
    if target_selector:
        try:
            target_count = len(soup.select(target_selector))
        except Exception as exc:  # soupsieve selector errors vary by version
            selector_error = str(exc)

    structured = detect_structured_data(html)
    api_hints = extract_api_hints(html)
    app_root_count = len(soup.select("#root, #app, [data-reactroot], [ng-version]"))

    signals = {
        "url": url,
        "html_chars": len(html),
        "text_chars": text_chars,
        "script_count": len(scripts),
        "app_root_count": app_root_count,
        "target_selector": target_selector,
        "target_count": target_count,
        "selector_error": selector_error,
        "challenge": challenge,
        "challenge_details": challenge_details.to_dict(),
        "structured_data": structured,
        "api_hints": api_hints[:20],
    }

    findings: list[str] = []
    recommendations: list[dict[str, Any]] = []

    if challenge:
        findings.append(f"challenge_detected:{challenge}")
        recommendations.append({
            "type": "manual_review",
            "reason": "The fetched page looks like a challenge, CAPTCHA, or access block.",
            "action": "Use permitted APIs, authorized cookies, lower rate limits, or manual review.",
        })

    if selector_error:
        findings.append("target_selector_invalid")
        recommendations.append({
            "type": "selector_tuning",
            "reason": "The target selector could not be parsed.",
            "action": "Validate CSS selectors before execution.",
        })
    elif target_selector and target_count == 0:
        findings.append("target_selector_missed")
        recommendations.append({
            "type": "selector_tuning",
            "reason": "The target selector did not match fetched HTML.",
            "action": "Inspect rendered DOM or tune selectors.",
        })

    if looks_like_js_shell(signals):
        findings.append("js_rendering_likely_required")
        recommendations.append({
            "type": "browser_rendering",
            "reason": "The page has little visible text and looks client-rendered.",
            "action": {
                "mode": "browser",
                "wait_until": "networkidle",
                "render_time": 5,
                "scroll_count": 2,
            },
        })

    if structured["json_ld_count"] or structured["next_data"] or structured["nuxt_data"]:
        findings.append("embedded_structured_data_available")
        recommendations.append({
            "type": "structured_data",
            "reason": "The page includes embedded JSON data that can be more stable than CSS selectors.",
            "action": "Prefer JSON-LD, __NEXT_DATA__, or __NUXT__ parsing where fields are present.",
        })

    if api_hints:
        findings.append("possible_api_endpoints_found")
        recommendations.append({
            "type": "network_api_review",
            "reason": "The HTML references API-like URLs.",
            "action": "Review candidates before choosing api_intercept.",
        })

    if not recommendations:
        recommendations.append({
            "type": "standard",
            "reason": "No strong access risk or browser-rendering signal was found.",
            "action": {"mode": "http"},
        })

    access_decision = decide_access(
        {"findings": findings, "signals": signals},
        status_code=status_code,
        has_authorized_session=has_authorized_session,
        proxy_enabled=proxy_enabled,
    )

    return {
        "ok": not bool(challenge),
        "findings": findings,
        "signals": signals,
        "recommendations": recommendations,
        "access_decision": access_decision.to_dict(),
    }


def detect_challenge(html: str) -> str:
    """Return the first challenge marker found in HTML, or an empty string."""
    return detect_challenge_signal(html).primary_marker


def detect_structured_data(html: str) -> dict[str, Any]:
    """Detect embedded structured-data containers without parsing large payloads."""
    soup = BeautifulSoup(html or "", "lxml")
    next_node = soup.select_one("script#__NEXT_DATA__")
    json_ld_nodes = soup.find_all("script", type="application/ld+json")
    lowered = (html or "").lower()
    return {
        "json_ld_count": len(json_ld_nodes),
        "next_data": bool(next_node),
        "nuxt_data": "__nuxt__" in lowered or "__nuxt_data__" in lowered,
        "sample_types": _json_ld_types(json_ld_nodes[:5]),
    }


def extract_api_hints(html: str) -> list[str]:
    """Extract API-like URL strings from scripts/HTML."""
    seen: set[str] = set()
    hints: list[str] = []
    for match in API_HINT_RE.finditer((html or "")[:500_000]):
        value = match.group("url")
        if value in seen or len(value) > 300:
            continue
        seen.add(value)
        hints.append(value)
    return hints


def looks_like_js_shell(signals: dict[str, Any]) -> bool:
    """Return whether access signals look like a client-rendered shell."""
    if signals.get("challenge"):
        return False
    text_chars = int(signals.get("text_chars") or 0)
    script_count = int(signals.get("script_count") or 0)
    app_root_count = int(signals.get("app_root_count") or 0)
    if text_chars < 500 and script_count >= 5:
        return True
    if app_root_count and text_chars < 1200:
        return True
    return False


def _looks_like_json_payload(text: str) -> bool:
    stripped = (text or "").lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _json_ld_types(nodes: list[Any]) -> list[str]:
    types: list[str] = []
    for node in nodes:
        try:
            payload = json.loads(node.get_text("", strip=True))
        except Exception:
            continue
        for value in _collect_types(payload):
            if value not in types:
                types.append(value)
    return types[:10]


def _collect_types(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        values: list[str] = []
        type_value = payload.get("@type")
        if isinstance(type_value, str):
            values.append(type_value)
        elif isinstance(type_value, list):
            values.extend(str(item) for item in type_value)
        for child in payload.values():
            values.extend(_collect_types(child))
        return values
    if isinstance(payload, list):
        values = []
        for item in payload:
            values.extend(_collect_types(item))
        return values
    return []
