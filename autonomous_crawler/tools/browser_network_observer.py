"""Browser network observation for API/XHR/GraphQL discovery.

This module observes browser traffic and summarizes public data-loading
signals. It does not bypass access controls, solve challenges, or replay
private authenticated requests.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore[assignment]


SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
    "x-xsrf-token",
}


@dataclass
class NetworkEntry:
    url: str
    method: str = "GET"
    resource_type: str = ""
    status_code: int | None = None
    request_headers: dict[str, str] = field(default_factory=dict)
    response_headers: dict[str, str] = field(default_factory=dict)
    post_data_preview: str = ""
    json_preview: Any = None
    kind: str = "other"
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "method": self.method,
            "resource_type": self.resource_type,
            "status_code": self.status_code,
            "request_headers": dict(self.request_headers),
            "response_headers": dict(self.response_headers),
            "post_data_preview": self.post_data_preview,
            "json_preview": self.json_preview,
            "kind": self.kind,
            "score": self.score,
            "reasons": list(self.reasons),
        }


@dataclass
class NetworkObservationResult:
    url: str
    final_url: str = ""
    status: str = "ok"
    error: str = ""
    entries: list[NetworkEntry] = field(default_factory=list)
    api_candidates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "status": self.status,
            "error": self.error,
            "entries": [entry.to_dict() for entry in self.entries],
            "api_candidates": list(self.api_candidates),
        }


def observe_browser_network(
    url: str,
    wait_selector: str = "",
    wait_until: str = "networkidle",
    timeout_ms: int = 30000,
    max_entries: int = 50,
    capture_json_preview: bool = True,
    render_time_ms: int = 0,
) -> NetworkObservationResult:
    """Observe browser network traffic and return API candidates.

    Unit tests should mock ``sync_playwright``. Real browser execution requires
    Playwright and installed browser binaries.
    """
    if sync_playwright is None:
        return NetworkObservationResult(
            url=url,
            status="failed",
            error="playwright is not installed",
        )

    valid_wait_until = {"domcontentloaded", "load", "networkidle"}
    if wait_until not in valid_wait_until:
        wait_until = "networkidle"

    entries: list[NetworkEntry] = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()

                def on_response(response: Any) -> None:
                    if len(entries) >= max_entries:
                        return
                    entry = _entry_from_response(
                        response,
                        capture_json_preview=capture_json_preview,
                    )
                    entry.score, entry.reasons, entry.kind = score_network_entry(entry)
                    if _should_keep_entry(entry):
                        entries.append(entry)

                page.on("response", on_response)
                page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                if render_time_ms > 0:
                    page.wait_for_timeout(render_time_ms)

                final_url = getattr(page, "url", url)
                candidates = build_api_candidates_from_entries(entries)
                return NetworkObservationResult(
                    url=url,
                    final_url=final_url,
                    entries=entries,
                    api_candidates=candidates,
                )
            finally:
                browser.close()
    except Exception as exc:
        return NetworkObservationResult(
            url=url,
            status="failed",
            error=str(exc),
            entries=entries,
            api_candidates=build_api_candidates_from_entries(entries),
        )


def score_network_entry(entry: NetworkEntry) -> tuple[int, list[str], str]:
    """Score and classify a captured network response."""
    reasons: list[str] = []
    score = 0
    kind = "other"
    lowered_url = entry.url.lower()
    content_type = _header_value(entry.response_headers, "content-type").lower()
    post_data = entry.post_data_preview.lower()

    if entry.status_code and 200 <= entry.status_code < 300:
        score += 10
        reasons.append("status_ok")
    elif entry.status_code in {401, 403, 429, 503}:
        score -= 10
        reasons.append(f"blocked_or_limited:{entry.status_code}")

    if entry.resource_type in {"xhr", "fetch"}:
        score += 18
        reasons.append("xhr_fetch")

    if "application/json" in content_type or entry.json_preview is not None:
        score += 20
        reasons.append("json")
        kind = "json"

    if _looks_like_graphql(lowered_url, post_data):
        score += 24
        reasons.append("graphql_signal")
        kind = "graphql"

    if any(token in lowered_url for token in ("api", "ajax", "search", "list", "rank", "product", "graphql")):
        score += 12
        reasons.append("api_url_keywords")

    if entry.method.upper() == "POST":
        score += 4
        reasons.append("post")

    if _looks_like_static_asset(lowered_url, content_type):
        score -= 30
        reasons.append("static_asset")

    return score, reasons, kind


def build_api_candidates_from_entries(entries: list[NetworkEntry]) -> list[dict[str, Any]]:
    """Convert observed entries into Strategy-friendly API candidates."""
    from .api_candidates import is_tracking_url

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in sorted(entries, key=lambda item: item.score, reverse=True):
        if entry.score < 20:
            continue
        if is_tracking_url(entry.url):
            continue
        key = (entry.method.upper(), entry.url)
        if key in seen:
            continue
        seen.add(key)
        candidate: dict[str, Any] = {
            "url": entry.url,
            "method": entry.method.upper(),
            "kind": entry.kind,
            "score": entry.score,
            "reason": "browser_network_observation",
            "resource_type": entry.resource_type,
            "status_code": entry.status_code,
        }
        if entry.kind == "graphql" or (
            entry.method.upper() == "POST" and entry.post_data_preview
        ):
            candidate["post_data_preview"] = entry.post_data_preview
        candidates.append(candidate)
    return candidates


def sanitize_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    """Remove or redact sensitive headers before persisting observations."""
    safe: dict[str, str] = {}
    for key, value in (headers or {}).items():
        key_str = str(key)
        if key_str.lower() in SENSITIVE_HEADER_NAMES:
            safe[key_str] = "[redacted]"
        else:
            safe[key_str] = _truncate(str(value), 300)
    return safe


def _entry_from_response(response: Any, capture_json_preview: bool) -> NetworkEntry:
    request = getattr(response, "request", None)
    method = str(getattr(request, "method", "GET") or "GET")
    resource_type = str(getattr(request, "resource_type", "") or "")
    post_data = getattr(request, "post_data", "") or ""

    entry = NetworkEntry(
        url=str(getattr(response, "url", "")),
        method=method,
        resource_type=resource_type,
        status_code=getattr(response, "status", None),
        request_headers=sanitize_headers(getattr(request, "headers", {}) if request else {}),
        response_headers=sanitize_headers(_response_headers(response)),
        post_data_preview=_truncate(post_data, 1000),
    )

    if capture_json_preview and _response_looks_json(entry.response_headers, entry.url):
        try:
            entry.json_preview = _truncate_json(response.json())
        except Exception:
            entry.json_preview = None
    return entry


def _response_headers(response: Any) -> dict[str, Any]:
    headers = getattr(response, "headers", {})
    return headers or {}


def _response_looks_json(headers: dict[str, str], url: str) -> bool:
    content_type = _header_value(headers, "content-type").lower()
    lowered_url = url.lower()
    return "application/json" in content_type or lowered_url.endswith(".json")


def _header_value(headers: dict[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return str(value)
    return ""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _truncate_json(value: Any, limit: int = 2000) -> Any:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= limit:
        return value
    return {"preview": text[:limit] + "...[truncated]"}


def _looks_like_graphql(lowered_url: str, lowered_post_data: str) -> bool:
    if "graphql" in lowered_url or "graphql" in lowered_post_data:
        return True
    if not lowered_post_data:
        return False

    try:
        payload = json.loads(lowered_post_data)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        query = payload.get("query")
        if isinstance(query, str):
            stripped = query.strip()
            if stripped.startswith(("query ", "mutation ", "subscription ")):
                return True
            if stripped.startswith("{") and "}" in stripped:
                return True
        return False

    stripped = lowered_post_data.strip()
    return stripped.startswith(("query ", "mutation ", "subscription "))


def _looks_like_static_asset(lowered_url: str, content_type: str) -> bool:
    if any(lowered_url.split("?")[0].endswith(ext) for ext in (
        ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".woff2", ".ico"
    )):
        return True
    return any(token in content_type for token in ("image/", "font/", "text/css", "javascript"))


def _should_keep_entry(entry: NetworkEntry) -> bool:
    if entry.score >= 10:
        return True
    if entry.resource_type in {"xhr", "fetch"}:
        return True
    return False
