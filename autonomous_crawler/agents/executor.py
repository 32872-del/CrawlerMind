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
from ..tools.access_config import resolve_access_config
from ..tools.proxy_manager import ProxyManager
from ..tools.proxy_trace import ProxyTrace
from ..tools.artifact_manifest import build_browser_artifact_manifest, persist_artifact_bundle
from ..tools.browser_fetch import fetch_rendered_html
from ..tools.fnspider_adapter import load_goods_rows, run_fnspider_site_spec
from ..tools.html_recon import MOCK_RANKING_HTML
from ..tools.api_candidates import (
    fetch_graphql_api,
    fetch_json_api,
    fetch_paginated_api,
    normalize_api_records,
    extract_records_from_json,
    PaginationSpec,
)
from ..runtime import (
    RuntimeRequest,
    RuntimeResponse,
    RuntimeSelectorRequest,
    ScraplingBrowserRuntime,
    ScraplingParserRuntime,
    ScraplingStaticRuntime,
)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
}

API_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
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

    # Build proxy trace for evidence chain (CAP-3.3 / CAP-6.2)
    recon_report = state.get("recon_report", {})
    _access_config = resolve_access_config(state, recon_report if isinstance(recon_report, dict) else {})
    _proxy_trace = ProxyTrace.from_manager(
        ProxyManager(_access_config.proxy), target_url,
    )
    _trace_dict = _proxy_trace.to_dict()

    if target_url in {"mock://products", "mock://catalog"}:
        return {
            "status": "executed",
            "visited_urls": [target_url],
            "raw_html": {target_url: MOCK_PRODUCT_HTML},
            "api_responses": [],
            "proxy_trace": _trace_dict,
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
            "proxy_trace": _trace_dict,
            "messages": state.get("messages", []) + [
                f"[Executor] Mode={mode}, loaded mock ranking fixture"
            ],
        }

    if target_url == "mock://json-direct" and mode == "api_intercept":
        items = [
            {"title": "JSON Alpha", "index": 0},
            {"title": "JSON Beta", "index": 1},
        ]
        return {
            "status": "executed",
            "visited_urls": [target_url],
            "raw_html": {},
            "api_responses": [{
                "ok": True,
                "url": target_url,
                "data": [{"title": "JSON Alpha"}, {"title": "JSON Beta"}],
                "status_code": 200,
            }],
            "extracted_data": {
                "items": items,
                "fields_found": ["index", "title"],
                "confidence": 1.0,
                "item_count": len(items),
            },
            "proxy_trace": _trace_dict,
            "messages": state.get("messages", []) + [
                f"[Executor] Mode=api_intercept, loaded direct JSON fixture, rows={len(items)}"
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
                "proxy_trace": _trace_dict,
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
            "proxy_trace": _trace_dict,
            "messages": state.get("messages", []) + [
                f"[Executor] Engine=fnspider failed: {result.error}"
            ],
        }

    if engine == "scrapling" and mode != "api_intercept":
        return _execute_scrapling_runtime(
            state=state,
            target_url=target_url,
            strategy=strategy,
            access_config=_access_config,
            proxy_trace=_trace_dict,
        )

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
            headers=_access_config.session_profile.headers_for(target_url),
            storage_state_path=_access_config.session_profile.storage_state_path,
            proxy_url=_access_config.proxy_for(target_url),
            browser_context=_access_config.browser_context,
        )

        if browser_result.status == "ok":
            manifest = build_browser_artifact_manifest(
                target_url=target_url,
                final_url=browser_result.url,
                browser_context=browser_result.browser_context,
                screenshot_path=browser_result.screenshot_path,
                access_decision=state.get("recon_report", {}).get("access_diagnostics", {}).get("access_decision", {})
                if isinstance(state.get("recon_report"), dict)
                else {},
            )
            persisted_manifest = persist_artifact_bundle(
                manifest,
                run_id=str(state.get("task_id") or target_url),
                html=browser_result.html,
            )
            return {
                "status": "executed",
                "visited_urls": [browser_result.url],
                "raw_html": {browser_result.url: browser_result.html},
                "api_responses": [],
                "screenshot_path": browser_result.screenshot_path,
                "browser_context": browser_result.browser_context,
                "artifact_manifest": persisted_manifest,
                "proxy_trace": _trace_dict,
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
            "proxy_trace": _trace_dict,
            "messages": state.get("messages", []) + [
                f"[Executor] Mode=browser, failed to fetch {target_url}: {browser_result.error}"
            ],
        }

    if mode == "api_intercept":
        api_endpoint = strategy.get("api_endpoint") or target_url
        headers = {**API_DEFAULT_HEADERS, **strategy.get("headers", {})}
        max_items = int(strategy.get("max_items", 0) or 0)
        pagination_cfg = strategy.get("pagination", {})
        pagination_type = pagination_cfg.get("type", "none") if isinstance(pagination_cfg, dict) else "none"

        try:
            if strategy.get("extraction_method") == "graphql_json":
                result = fetch_graphql_api(
                    api_endpoint,
                    query=str(strategy.get("graphql_query", "")),
                    variables=strategy.get("graphql_variables") or {},
                    headers=headers,
                )
                records = extract_records_from_json(result.get("data"))
                items = normalize_api_records(records, max_items=max_items)
                all_api_responses = [result]
            elif pagination_type in {"page", "offset", "cursor"}:
                spec = PaginationSpec(
                    type=pagination_type,
                    page_param=pagination_cfg.get("param", "page"),
                    limit_param=pagination_cfg.get("limit_param", "limit"),
                    offset_param=pagination_cfg.get("param", "offset"),
                    cursor_param=pagination_cfg.get("param", "cursor"),
                    limit=int(pagination_cfg.get("limit", 10)),
                    max_pages=int(pagination_cfg.get("max_pages", 10)),
                )
                paginated = fetch_paginated_api(
                    api_endpoint,
                    pagination=spec,
                    headers=headers,
                    method=strategy.get("api_method", "GET"),
                    post_data=strategy.get("api_post_data"),
                    max_items=max_items,
                )
                items = paginated.all_items
                all_api_responses = paginated.api_responses
            else:
                result = fetch_json_api(
                    api_endpoint,
                    headers=headers,
                    method=strategy.get("api_method", "GET"),
                    post_data=strategy.get("api_post_data"),
                )
                records = extract_records_from_json(result.get("data"))
                items = normalize_api_records(records, max_items=max_items)
                all_api_responses = [result]
        except Exception as exc:
            return {
                "status": "failed",
                "visited_urls": [api_endpoint],
                "raw_html": {},
                "api_responses": [],
                "error_code": FETCH_HTTP_ERROR,
                "error_log": state.get("error_log", []) + [
                    format_error_entry(FETCH_HTTP_ERROR, f"API fetch failed: {exc}")
                ],
                "proxy_trace": _trace_dict,
                "messages": state.get("messages", []) + [
                    f"[Executor] Mode=api_intercept, failed to fetch {api_endpoint}: {exc}"
                ],
            }
        fields_found = sorted({key for item in items for key, value in item.items() if value})
        return {
            "status": "executed",
            "visited_urls": [api_endpoint],
            "raw_html": {},
            "api_responses": all_api_responses,
            "extracted_data": {
                "items": items,
                "fields_found": fields_found,
                "confidence": 1.0 if items else 0.0,
                "item_count": len(items),
            },
            "proxy_trace": _trace_dict,
            "messages": state.get("messages", []) + [
                f"[Executor] Mode=api_intercept, fetched {api_endpoint}, rows={len(items)}"
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
            "proxy_trace": _trace_dict,
            "messages": state.get("messages", []) + [
                f"[Executor] Unsupported URL scheme: {target_url}"
            ],
        }

    headers = {**DEFAULT_HEADERS, **strategy.get("headers", {})}
    proxy_url = _access_config.proxy_for(target_url)

    try:
        client_kwargs: dict[str, Any] = {
            "follow_redirects": True,
            "timeout": httpx.Timeout(20.0, connect=10.0),
            "headers": headers,
        }
        if proxy_url:
            client_kwargs["proxy"] = proxy_url
        with httpx.Client(**client_kwargs) as client:
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
            "proxy_trace": _trace_dict,
            "messages": state.get("messages", []) + [
                f"[Executor] Mode={mode}, failed to fetch {target_url}: {exc}"
            ],
        }

    return {
        "status": "executed",
        "visited_urls": [target_url],
        "raw_html": {str(response.url): response.text},
        "api_responses": [],
        "proxy_trace": _trace_dict,
        "messages": state.get("messages", []) + [
            f"[Executor] Mode={mode}, fetched {response.url} ({response.status_code}, {len(response.text)} chars)"
        ],
    }


def _execute_scrapling_runtime(
    *,
    state: dict[str, Any],
    target_url: str,
    strategy: dict[str, Any],
    access_config: Any,
    proxy_trace: dict[str, Any],
) -> dict[str, Any]:
    """Execute the Scrapling-first CLM runtime path."""
    mode = str(strategy.get("mode", "http") or "http")
    runtime_mode = _scrapling_runtime_mode(strategy)
    request = _build_scrapling_request(
        target_url=target_url,
        strategy=strategy,
        access_config=access_config,
        runtime_mode=runtime_mode,
    )

    runtime: Any
    if runtime_mode in {"dynamic", "protected"}:
        runtime = ScraplingBrowserRuntime()
        response = runtime.render(request)
        failure_code = BROWSER_RENDER_FAILED
    else:
        runtime = ScraplingStaticRuntime()
        response = runtime.fetch(request)
        failure_code = FETCH_HTTP_ERROR

    selector_results = []
    html = response.html or response.text
    if html:
        parser = ScraplingParserRuntime()
        selector_results = parser.parse(
            html,
            request.selectors,
            url=response.final_url or target_url,
        )

    engine_result = _scrapling_engine_result(response, selector_results)
    selected_proxy_trace = (
        response.proxy_trace.to_dict()
        if response.proxy_trace.selected or response.proxy_trace.source != "none"
        else proxy_trace
    )

    if not response.ok:
        return {
            "status": "failed",
            "visited_urls": [response.final_url or target_url],
            "raw_html": {},
            "api_responses": [],
            "engine_result": engine_result,
            "runtime_events": [event.to_dict() for event in response.runtime_events],
            "error_code": failure_code,
            "error_log": state.get("error_log", []) + [
                format_error_entry(
                    failure_code,
                    f"Scrapling runtime failed: {response.error or response.status_code}",
                )
            ],
            "proxy_trace": selected_proxy_trace,
            "messages": state.get("messages", []) + [
                f"[Executor] Engine=scrapling {runtime.name} failed: {response.error or response.status_code}"
            ],
        }

    final_url = response.final_url or target_url
    return {
        "status": "executed",
        "visited_urls": [final_url],
        "raw_html": {final_url: html},
        "api_responses": [],
        "engine_result": engine_result,
        "runtime_events": [event.to_dict() for event in response.runtime_events],
        "proxy_trace": selected_proxy_trace,
        "messages": state.get("messages", []) + [
            f"[Executor] Engine=scrapling {runtime.name} fetched {final_url} ({response.status_code}, {len(html)} chars)"
        ],
    }


def _build_scrapling_request(
    *,
    target_url: str,
    strategy: dict[str, Any],
    access_config: Any,
    runtime_mode: str,
) -> RuntimeRequest:
    headers = {
        **DEFAULT_HEADERS,
        **strategy.get("headers", {}),
        **access_config.session_profile.headers_for(target_url),
    }
    cookies = (
        dict(access_config.session_profile.cookies)
        if access_config.session_profile.applies_to(target_url)
        else {}
    )
    proxy_url = access_config.proxy_for(target_url)
    browser_config = _browser_config_for_scrapling(access_config, strategy)
    session_profile = {
        "headers": access_config.session_profile.headers_for(target_url),
        "cookies": cookies,
        "storage_state_path": access_config.session_profile.storage_state_path,
    }
    return RuntimeRequest(
        url=target_url,
        method=str(strategy.get("method") or "GET").upper(),
        mode=runtime_mode,
        headers=headers,
        cookies=cookies,
        selectors=_runtime_selectors(strategy.get("selectors", {})),
        browser_config=browser_config,
        session_profile=session_profile,
        proxy_config={"proxy": proxy_url} if proxy_url else {},
        capture_xhr=str(strategy.get("capture_xhr", "")),
        wait_selector=str(strategy.get("wait_selector", "")),
        wait_until=str(strategy.get("wait_until", "domcontentloaded")),
        timeout_ms=int(strategy.get("timeout_ms", 30000) or 30000),
        max_items=int(strategy.get("max_items", 0) or 0),
        meta={"engine": "scrapling", "strategy_mode": strategy.get("mode", "")},
    )


def _browser_config_for_scrapling(access_config: Any, strategy: dict[str, Any]) -> dict[str, Any]:
    context = access_config.browser_context
    browser_config = {
        "headless": context.headless,
        "useragent": context.user_agent,
        "locale": context.locale,
        "timezone_id": context.timezone_id,
        "extra_headers": context.extra_http_headers,
        "ignore_https_errors": context.ignore_https_errors,
    }
    overrides = strategy.get("browser_config") or {}
    if isinstance(overrides, dict):
        browser_config.update(overrides)
    return browser_config


def _scrapling_runtime_mode(strategy: dict[str, Any]) -> str:
    configured = str(strategy.get("runtime_mode") or "").strip().lower()
    if configured in {"static", "dynamic", "protected"}:
        return configured
    mode = str(strategy.get("mode", "http") or "http")
    if mode == "browser":
        return "protected" if strategy.get("protected") else "dynamic"
    return "static"


def _runtime_selectors(selectors: dict[str, str]) -> list[RuntimeSelectorRequest]:
    requests: list[RuntimeSelectorRequest] = []
    if not isinstance(selectors, dict):
        return requests
    for name, expression in selectors.items():
        if name == "item_container" or not expression:
            continue
        selector = str(expression)
        attribute = ""
        if "@" in selector:
            selector, attribute = selector.rsplit("@", 1)
        requests.append(RuntimeSelectorRequest(
            name=str(name),
            selector=selector,
            attribute=attribute,
            selector_type="css",
            many=True,
        ))
    return requests


def _scrapling_engine_result(
    response: RuntimeResponse,
    selector_results: list[Any],
) -> dict[str, Any]:
    return {
        "engine": "scrapling",
        "backend": response.engine_result.get("engine", ""),
        "ok": response.ok,
        "final_url": response.final_url,
        "status_code": response.status_code,
        "selector_results": [result.to_dict() for result in selector_results],
        "captured_xhr": response.to_dict().get("captured_xhr", []),
        "runtime_events": [event.to_dict() for event in response.runtime_events],
        "artifacts": [artifact.to_dict() for artifact in response.artifacts],
        "error": response.error,
    }
