"""Executor Agent - Executes the crawl strategy.

Executor Modes (README Section 9):
- HTTP Mode
- Browser Mode
- API Intercept Mode
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from .base import preserve_state
from ..errors import (
    BROWSER_RENDER_FAILED,
    FETCH_HTTP_ERROR,
    FETCH_UNSUPPORTED_SCHEME,
    format_error_entry,
)
from ..tools.browser_fetch import fetch_rendered_html
from ..tools.fnspider_adapter import load_goods_rows, run_fnspider_site_spec
from ..tools.html_recon import MOCK_RANKING_HTML


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
}


MOCK_PRODUCT_HTML = """
<main class="catalog-grid">
    <article class="catalog-card">
        <a class="product-link" href="/products/alpha">
            <img class="product-photo" src="/images/alpha.jpg" />
            <h2 class="product-name">Alpha Jacket</h2>
            <span class="product-price">$129.90</span>
        </a>
    </article>
    <article class="catalog-card">
        <a class="product-link" href="/products/beta">
            <img class="product-photo" src="/images/beta.jpg" />
            <h2 class="product-name">Beta Pants</h2>
            <span class="product-price">$89.50</span>
        </a>
    </article>
</main>
"""


@preserve_state
def executor_node(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the crawl strategy and collect raw data.

    Browser and API-intercept modes are still future work, but HTTP mode now
    performs a real request. Tests can use mock://products for deterministic
    fixture HTML without touching the network.
    """
    target_url = state.get("target_url", "")
    strategy = state.get("crawl_strategy", {})
    mode = strategy.get("mode", "http")
    engine = strategy.get("engine", "")

    if target_url in {"mock://products", "mock://catalog"}:
        return {
            "status": "executed",
            "visited_urls": [target_url],
            "raw_html": {target_url: MOCK_PRODUCT_HTML},
            "api_responses": [],
            "messages": state.get("messages", []) + [
                f"[Executor] Mode={mode}, loaded mock product fixture"
            ],
        }

    if target_url == "mock://ranking":
        return {
            "status": "executed",
            "visited_urls": [target_url],
            "raw_html": {target_url: MOCK_RANKING_HTML},
            "api_responses": [],
            "messages": state.get("messages", []) + [
                f"[Executor] Mode={mode}, loaded mock ranking fixture"
            ],
        }

    if engine == "fnspider":
        result = run_fnspider_site_spec(strategy.get("site_spec_draft", {}))
        rows = load_goods_rows(result.db_path) if result.db_path else []
        if result.status == "completed":
            return {
                "status": "executed",
                "visited_urls": [target_url],
                "raw_html": {},
                "api_responses": [],
                "engine_result": {
                    "engine": "fnspider",
                    "db_path": result.db_path,
                    "spec_path": result.spec_path,
                    "item_count": result.item_count,
                },
                "extracted_data": {
                    "items": rows,
                    "fields_found": sorted({k for row in rows for k, v in row.items() if v}),
                    "confidence": 1.0 if rows else 0.0,
                    "item_count": len(rows),
                },
                "messages": state.get("messages", []) + [
                    f"[Executor] Engine=fnspider completed, rows={len(rows)}"
                ],
            }
        return {
            "status": "failed",
            "visited_urls": [target_url],
            "raw_html": {},
            "api_responses": [],
            "engine_result": {
                "engine": "fnspider",
                "error": result.error,
                "spec_path": result.spec_path,
            },
            "error_code": FETCH_HTTP_ERROR,
            "error_log": state.get("error_log", []) + [
                format_error_entry(FETCH_HTTP_ERROR, f"fnspider execution failed: {result.error}")
            ],
            "messages": state.get("messages", []) + [
                f"[Executor] Engine=fnspider failed: {result.error}"
            ],
        }

    if mode == "browser":
        wait_selector = strategy.get("wait_selector", "")
        wait_until = strategy.get("wait_until", "domcontentloaded")
        timeout_ms = int(strategy.get("timeout_ms", 30000))
        screenshot = bool(strategy.get("screenshot", False))

        browser_result = fetch_rendered_html(
            url=target_url,
            wait_selector=wait_selector,
            wait_until=wait_until,
            timeout_ms=timeout_ms,
            screenshot=screenshot,
        )

        if browser_result.status == "ok":
            return {
                "status": "executed",
                "visited_urls": [browser_result.url],
                "raw_html": {browser_result.url: browser_result.html},
                "api_responses": [],
                "screenshot_path": browser_result.screenshot_path,
                "messages": state.get("messages", []) + [
                    f"[Executor] Mode=browser, fetched {browser_result.url} ({len(browser_result.html)} chars)"
                ],
            }
        return {
            "status": "failed",
            "visited_urls": [target_url],
            "raw_html": {},
            "api_responses": [],
            "error_code": BROWSER_RENDER_FAILED,
            "error_log": state.get("error_log", []) + [
                format_error_entry(BROWSER_RENDER_FAILED, f"Browser fetch failed: {browser_result.error}")
            ],
            "messages": state.get("messages", []) + [
                f"[Executor] Mode=browser, failed to fetch {target_url}: {browser_result.error}"
            ],
        }

    parsed = urlparse(target_url)
    if parsed.scheme not in {"http", "https"}:
        return {
            "status": "failed",
            "visited_urls": [],
            "raw_html": {},
            "api_responses": [],
            "error_code": FETCH_UNSUPPORTED_SCHEME,
            "error_log": state.get("error_log", []) + [
                format_error_entry(FETCH_UNSUPPORTED_SCHEME, f"Unsupported URL scheme for executor: {target_url}")
            ],
            "messages": state.get("messages", []) + [
                f"[Executor] Unsupported URL scheme: {target_url}"
            ],
        }

    headers = {**DEFAULT_HEADERS, **strategy.get("headers", {})}

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers=headers,
        ) as client:
            response = client.get(target_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "status": "failed",
            "visited_urls": [target_url],
            "raw_html": {},
            "api_responses": [],
            "error_code": FETCH_HTTP_ERROR,
            "error_log": state.get("error_log", []) + [
                format_error_entry(FETCH_HTTP_ERROR, f"HTTP fetch failed: {exc}")
            ],
            "messages": state.get("messages", []) + [
                f"[Executor] Mode={mode}, failed to fetch {target_url}: {exc}"
            ],
        }

    return {
        "status": "executed",
        "visited_urls": [target_url],
        "raw_html": {str(response.url): response.text},
        "api_responses": [],
        "messages": state.get("messages", []) + [
            f"[Executor] Mode={mode}, fetched {response.url} ({response.status_code}, {len(response.text)} chars)"
        ],
    }
