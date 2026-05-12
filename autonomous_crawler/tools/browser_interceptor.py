"""Browser request interception and JS asset capture.

This module uses Playwright's ``page.route()`` to intercept, block, and
observe page resources.  It captures JS bundles (with SHA-256) and API-like
XHR/fetch responses so the crawler can build a resource inventory, block
heavy assets, and prepare for later init-script / CDP hook work.

This module does NOT bypass challenges, solve CAPTCHAs, or implement
stealth/fingerprint features.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .browser_context import BrowserContextConfig, normalize_wait_until
from .browser_network_observer import sanitize_headers

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore[assignment]

BLOCKABLE_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}
API_RESOURCE_TYPES = {"xhr", "fetch"}


@dataclass(frozen=True)
class InterceptorConfig:
    block_resource_types: frozenset[str] = frozenset()
    capture_js: bool = True
    capture_api: bool = True
    init_script: str = ""
    max_captures: int = 200

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | "InterceptorConfig" | None) -> "InterceptorConfig":
        if isinstance(payload, InterceptorConfig):
            return payload
        payload = payload or {}
        raw_types = payload.get("block_resource_types") or []
        if isinstance(raw_types, (list, tuple, set, frozenset)):
            block_types = frozenset(str(t).strip().lower() for t in raw_types if t)
        else:
            block_types = frozenset()
        return cls(
            block_resource_types=block_types,
            capture_js=bool(payload.get("capture_js", True)),
            capture_api=bool(payload.get("capture_api", True)),
            init_script=str(payload.get("init_script") or ""),
            max_captures=_bounded_int(payload.get("max_captures"), default=200, minimum=1, maximum=10000),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_resource_types": sorted(self.block_resource_types),
            "capture_js": self.capture_js,
            "capture_api": self.capture_api,
            "init_script": bool(self.init_script),
            "max_captures": self.max_captures,
        }


@dataclass
class InterceptionResult:
    url: str
    final_url: str = ""
    status: str = "ok"
    error: str = ""
    resource_counts: dict[str, int] = field(default_factory=dict)
    blocked_urls: list[str] = field(default_factory=list)
    js_assets: list[dict[str, Any]] = field(default_factory=list)
    api_captures: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "status": self.status,
            "error": self.error,
            "resource_counts": dict(self.resource_counts),
            "blocked_urls": list(self.blocked_urls),
            "js_assets": list(self.js_assets),
            "api_captures": list(self.api_captures),
            "errors": list(self.errors),
        }


def intercept_page_resources(
    url: str,
    config: InterceptorConfig | dict[str, Any] | None = None,
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 30000,
    wait_selector: str = "",
    render_time_ms: int = 0,
    browser_context: BrowserContextConfig | dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    storage_state_path: str = "",
    proxy_url: str = "",
) -> InterceptionResult:
    """Intercept page resources, block configured types, capture JS and API responses.

    Unit tests should mock ``sync_playwright``.  Real browser execution
    requires Playwright and installed browser binaries.
    """
    if sync_playwright is None:
        return InterceptionResult(
            url=url,
            status="failed",
            error="playwright is not installed",
        )

    interceptor_cfg = (
        config if isinstance(config, InterceptorConfig)
        else InterceptorConfig.from_dict(config)
    )
    wait_until = normalize_wait_until(wait_until, default="domcontentloaded")
    context_config = (
        browser_context if isinstance(browser_context, BrowserContextConfig)
        else BrowserContextConfig.from_dict(browser_context)
    )
    context_config = context_config.with_runtime_overrides(
        headers=headers,
        storage_state_path=storage_state_path,
        proxy_url=proxy_url,
    )

    resource_counts: dict[str, int] = {}
    blocked_urls: list[str] = []
    js_assets: list[dict[str, Any]] = []
    api_captures: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_request_urls: set[str] = set()
    total_captured = 0

    def _record_resource_request(request: Any, request_url: str) -> str:
        resource_type = str(getattr(request, "resource_type", "") or "")
        resource_counts[resource_type] = resource_counts.get(resource_type, 0) + 1
        if request_url:
            seen_request_urls.add(request_url)
        return resource_type

    def _record_blocked_url(resource_type: str, request_url: str) -> None:
        if (
            resource_type in interceptor_cfg.block_resource_types
            and request_url
            and request_url not in blocked_urls
        ):
            blocked_urls.append(request_url)

    def _on_route(route: Any) -> None:
        request = route.request
        request_url = str(getattr(request, "url", ""))
        resource_type = _record_resource_request(request, request_url)
        if resource_type in interceptor_cfg.block_resource_types:
            _record_blocked_url(resource_type, request_url)
            route.abort()
        else:
            route.continue_()

    def _on_response(response: Any) -> None:
        nonlocal total_captured
        if total_captured >= interceptor_cfg.max_captures:
            return
        request = getattr(response, "request", None)
        resource_type = str(getattr(request, "resource_type", "") or "")
        content_type = _header_value(
            getattr(response, "headers", {}) or {},
            "content-type",
        ).lower()
        response_url = str(getattr(response, "url", ""))
        status_code = getattr(response, "status", None)
        if response_url not in seen_request_urls:
            _record_resource_request(request, response_url)
        _record_blocked_url(resource_type, response_url)

        is_js = resource_type == "script" and interceptor_cfg.capture_js
        is_api = (
            (resource_type in API_RESOURCE_TYPES or "application/json" in content_type)
            and interceptor_cfg.capture_api
        )

        if is_js:
            entry = _capture_js_asset(response, response_url, status_code, content_type, errors)
            if entry:
                js_assets.append(entry)
                total_captured += 1
        elif is_api:
            method = str(getattr(request, "method", "GET") or "GET") if request else "GET"
            api_captures.append({
                "url": response_url,
                "method": method,
                "status_code": status_code,
                "content_type": content_type,
            })
            total_captured += 1

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**context_config.launch_options())
            try:
                context = browser.new_context(**context_config.context_options())
                page = context.new_page()

                if interceptor_cfg.init_script:
                    page.add_init_script(script=interceptor_cfg.init_script)

                page.route("**/*", _on_route)
                page.on("response", _on_response)

                page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                if render_time_ms > 0:
                    page.wait_for_timeout(render_time_ms)

                final_url = getattr(page, "url", url)
                return InterceptionResult(
                    url=url,
                    final_url=final_url,
                    resource_counts=resource_counts,
                    blocked_urls=blocked_urls,
                    js_assets=js_assets,
                    api_captures=api_captures,
                    errors=errors,
                )
            finally:
                browser.close()
    except Exception as exc:
        return InterceptionResult(
            url=url,
            status="failed",
            error=str(exc),
            resource_counts=resource_counts,
            blocked_urls=blocked_urls,
            js_assets=js_assets,
            api_captures=api_captures,
            errors=errors,
        )


def _capture_js_asset(
    response: Any,
    url: str,
    status_code: int | None,
    content_type: str,
    errors: list[str],
) -> dict[str, Any] | None:
    try:
        body_bytes: bytes = response.body()
    except Exception as exc:
        errors.append(f"body_read_error:{url}:{exc}")
        return None
    body_text = body_bytes.decode("utf-8", errors="replace") if body_bytes else ""
    sha256 = hashlib.sha256(body_bytes).hexdigest() if body_bytes else ""
    return {
        "url": url,
        "status_code": status_code,
        "content_type": content_type,
        "size_bytes": len(body_bytes),
        "sha256": sha256,
    }


def _header_value(headers: dict[str, Any], name: str) -> str:
    target = name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return str(value)
    return ""


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))
