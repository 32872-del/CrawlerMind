"""CLM-native Playwright browser runtime.

This module is the first SCRAPLING-ABSORB-2 native browser slice. It turns the
browser/session/proxy/XHR behavior that CLM has been proving in tools into a
runtime backend owned by CLM. It does not import or call Scrapling.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from autonomous_crawler.tools.browser_fingerprint import build_fingerprint_report
from autonomous_crawler.tools.browser_context import (
    BrowserContextConfig,
    normalize_wait_until,
)
from autonomous_crawler.tools.challenge_detector import detect_challenge_signal
from autonomous_crawler.tools.proxy_manager import redact_proxy_url
from autonomous_crawler.tools.proxy_trace import redact_error_message
from autonomous_crawler.tools.session_profile import redact_storage_state_path
from autonomous_crawler.tools.visual_recon import analyze_runtime_artifacts

from .browser_pool import BrowserContextLease, BrowserPoolManager, BrowserProfile, BrowserProfileHealth, BrowserProfileRotator
from .models import (
    RuntimeArtifact,
    RuntimeEvent,
    RuntimeProxyTrace,
    RuntimeRequest,
    RuntimeResponse,
)

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - exercised by explicit tests
    sync_playwright = None  # type: ignore[assignment]


SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "tools" / "runtime" / "screenshots" / "native_browser"
VALID_BROWSER_MODES = {"dynamic", "protected"}
VALID_WAIT_STATES = {"attached", "detached", "visible", "hidden"}
DEFAULT_BLOCK_RESOURCE_TYPES = frozenset[str]()
API_RESOURCE_TYPES = {"xhr", "fetch"}
BLOCKED_STATUS_CODES = {401, 403, 407, 429, 444, 500, 502, 503, 504}
PROTECTED_MODE_FLAGS = (
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
)
PROTECTED_MODE_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = window.chrome || { runtime: {} };
""".strip()


@dataclass(frozen=True)
class NativeBrowserConfig:
    """Resolved options for the native Playwright runtime."""

    mode: str = "dynamic"
    wait_selector_state: str = "attached"
    render_time_ms: int = 0
    block_resource_types: frozenset[str] = DEFAULT_BLOCK_RESOURCE_TYPES
    blocked_domains: frozenset[str] = field(default_factory=frozenset)
    capture_api: bool = True
    capture_js: bool = False
    max_captures: int = 200
    max_body_preview_chars: int = 2000
    screenshot: bool = False
    init_script: str = ""
    cdp_url: str = ""
    executable_path: str = ""
    channel: str = ""
    extra_flags: tuple[str, ...] = ()
    user_data_dir: str = ""
    storage_state_output_path: str = ""
    close_persistent_context: bool = True
    visual_recon: bool = False

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "wait_selector_state": self.wait_selector_state,
            "render_time_ms": self.render_time_ms,
            "block_resource_types": sorted(self.block_resource_types),
            "blocked_domains": sorted(self.blocked_domains),
            "capture_api": self.capture_api,
            "capture_js": self.capture_js,
            "max_captures": self.max_captures,
            "max_body_preview_chars": self.max_body_preview_chars,
            "screenshot": self.screenshot,
            "init_script": bool(self.init_script),
            "cdp_url": bool(self.cdp_url),
            "executable_path": bool(self.executable_path),
            "channel": self.channel,
            "extra_flags": list(self.extra_flags),
            "user_data_dir": redact_storage_state_path(self.user_data_dir),
            "storage_state_output_path": redact_storage_state_path(self.storage_state_output_path),
            "close_persistent_context": self.close_persistent_context,
            "visual_recon": self.visual_recon,
        }


class NativeBrowserRuntime:
    """CLM-owned ``BrowserRuntime`` backed by Playwright."""

    name: str = "native_browser"

    def __init__(
        self,
        pool: BrowserPoolManager | None = None,
        rotator: BrowserProfileRotator | None = None,
    ) -> None:
        self._pool = pool
        self._rotator = rotator
        self._pw: Any = None  # persistent Playwright instance for pool mode
        self._pw_cm: Any = None  # context manager for cleanup

    def close(self) -> None:
        """Close persistent Playwright instance if pool mode was used."""
        if self._pool is not None:
            self._pool.close_all()
        if self._pw_cm is not None:
            try:
                self._pw_cm.__exit__(None, None, None)
            except Exception:
                pass
            self._pw = None
            self._pw_cm = None

    def render(self, request: RuntimeRequest) -> RuntimeResponse:
        start_time = time.time()

        # Apply profile rotation if configured
        active_profile: BrowserProfile | None = None
        if self._rotator is not None:
            active_profile = self._rotator.next_profile()
            if active_profile is not None:
                request = _apply_profile_to_request(request, active_profile)

        config = resolve_native_browser_config(request)
        proxy_trace = _proxy_trace_for(request)
        context_config = _browser_context_for_request(request)
        fingerprint_report = build_fingerprint_report(context_config).to_dict()
        session_mode = _session_mode_for(config, context_config)
        events: list[RuntimeEvent] = [
            RuntimeEvent(
                type="browser_render_start",
                message="native browser render started",
                data={
                    "url": request.url,
                    "mode": config.mode,
                    "session_mode": session_mode,
                    "wait_until": normalize_wait_until(request.wait_until),
                    "wait_selector": bool(request.wait_selector),
                    "proxy": redact_proxy_url(_proxy_url_for(request)),
                    "profile_id": active_profile.profile_id if active_profile else None,
                },
            )
        ]

        if sync_playwright is None:
            failure = _classify_browser_failure(
                error="playwright is not installed",
                status_code=0,
                html="",
                headers={},
                proxy_selected=proxy_trace.selected,
            )
            events.append(RuntimeEvent(
                type="browser_render_error",
                message="playwright is not installed",
                data={"failure_classification": failure},
            ))
            return _browser_failure_response(
                final_url=request.url,
                error="playwright is not installed",
                engine=self.name,
                config=config,
                context_config=context_config,
                session_mode=session_mode,
                fingerprint_report=fingerprint_report,
                failure_classification=failure,
                events=events,
                proxy_trace=proxy_trace,
            )

        resource_counts: dict[str, int] = {}
        blocked_urls: list[str] = []
        captured_xhr: list[dict[str, Any]] = []
        js_assets: list[dict[str, Any]] = []
        errors: list[str] = []
        seen_request_urls: set[str] = set()
        capture_count = 0

        def _record_request(playwright_request: Any) -> tuple[str, str]:
            resource_type = str(getattr(playwright_request, "resource_type", "") or "")
            request_url = str(getattr(playwright_request, "url", "") or "")
            resource_counts[resource_type] = resource_counts.get(resource_type, 0) + 1
            if request_url:
                seen_request_urls.add(request_url)
            return resource_type, request_url

        def _on_route(route: Any) -> None:
            playwright_request = getattr(route, "request", None)
            resource_type, request_url = _record_request(playwright_request)
            if _should_block(request_url, resource_type, config):
                if request_url and request_url not in blocked_urls:
                    blocked_urls.append(request_url)
                route.abort()
                return
            route.continue_()

        def _on_response(response: Any) -> None:
            nonlocal capture_count
            if capture_count >= config.max_captures:
                return

            playwright_request = getattr(response, "request", None)
            response_url = str(getattr(response, "url", "") or "")
            if response_url not in seen_request_urls:
                _record_request(playwright_request)

            resource_type = str(getattr(playwright_request, "resource_type", "") or "")
            status_code = int(getattr(response, "status", 0) or 0)
            headers = dict(getattr(response, "headers", {}) or {})
            content_type = _header_value(headers, "content-type").lower()
            if _should_block(response_url, resource_type, config):
                if response_url and response_url not in blocked_urls:
                    blocked_urls.append(response_url)

            should_capture_api = config.capture_api and _looks_like_api_response(
                request.capture_xhr,
                response_url,
                resource_type,
                content_type,
            )
            should_capture_js = config.capture_js and resource_type == "script"

            if should_capture_api:
                captured_xhr.append(_capture_response_preview(
                    response=response,
                    url=response_url,
                    status_code=status_code,
                    content_type=content_type,
                    resource_type=resource_type,
                    method=str(getattr(playwright_request, "method", "GET") or "GET"),
                    max_chars=config.max_body_preview_chars,
                    errors=errors,
                ))
                capture_count += 1
            elif should_capture_js:
                js_assets.append(_capture_response_preview(
                    response=response,
                    url=response_url,
                    status_code=status_code,
                    content_type=content_type,
                    resource_type=resource_type,
                    method=str(getattr(playwright_request, "method", "GET") or "GET"),
                    max_chars=config.max_body_preview_chars,
                    errors=errors,
                ))
                capture_count += 1

        pool_id = str((request.browser_config or {}).get("pool_id") or "")
        pool_lease: BrowserContextLease | None = None

        try:
            use_pool = bool(self._pool and pool_id)
            if use_pool:
                # Keep Playwright instance alive for pool reuse
                if self._pw is None:
                    self._pw_cm = sync_playwright()
                    self._pw = self._pw_cm.__enter__()
                pw = self._pw
            else:
                cm = sync_playwright()
                pw = cm.__enter__()
            try:
                if use_pool:
                    fingerprint = self._pool.compute_fingerprint(
                        context_config.context_options(),
                        _launch_options(context_config, config),
                        session_mode,
                        config.user_data_dir,
                    )
                    pool_lease = self._pool.acquire(
                        profile_id=pool_id,
                        fingerprint=fingerprint,
                        session_mode=session_mode,
                        user_data_dir=config.user_data_dir,
                    )
                    if pool_lease.context is not None:
                        browser = pool_lease.browser
                        context = pool_lease.context
                        session = {"mode": pool_lease.session_mode, "context": context, "browser": browser}
                        events.append(RuntimeEvent(
                            type="pool_reuse",
                            message=f"reused pool context for {pool_id}",
                            data={"pool_id": pool_id, "pool_request_count": pool_lease.request_count},
                        ))
                    else:
                        session = _open_browser_session(pw, context_config, config, request.timeout_ms)
                        browser = session.get("browser")
                        context = session["context"]
                        pool_lease.context = context
                        pool_lease.browser = browser
                        pool_lease.session_mode = session.get("mode", "ephemeral")
                        events.append(RuntimeEvent(
                            type="pool_acquire",
                            message=f"acquired new pool context for {pool_id}",
                            data={"pool_id": pool_id, "fingerprint": fingerprint},
                        ))
                else:
                    session = _open_browser_session(pw, context_config, config, request.timeout_ms)
                    browser = session.get("browser")
                    context = session["context"]
                try:
                    _add_request_cookies(context, request)
                    page = context.new_page()
                    if config.init_script:
                        page.add_init_script(script=config.init_script)
                    page.route("**/*", _on_route)
                    page.on("response", _on_response)

                    wait_until = normalize_wait_until(request.wait_until)
                    nav_response = page.goto(
                        request.url,
                        wait_until=wait_until,
                        timeout=request.timeout_ms,
                    )
                    if request.wait_selector:
                        page.wait_for_selector(
                            request.wait_selector,
                            timeout=request.timeout_ms,
                            state=config.wait_selector_state,
                        )
                    if config.render_time_ms > 0:
                        page.wait_for_timeout(config.render_time_ms)

                    final_url = str(getattr(page, "url", "") or request.url)
                    html = str(page.content() or "")
                    status_code = int(getattr(nav_response, "status", 0) or 0)
                    headers = dict(getattr(nav_response, "headers", {}) or {})
                    cookies = _cookies_from_context(context)
                    storage_state_path = _persist_storage_state(context, config)
                    artifacts = _capture_artifacts(page, final_url, config, storage_state_path)
                    visual_recon = analyze_runtime_artifacts(artifacts) if config.visual_recon else []
                finally:
                    if pool_lease is not None:
                        pool_lease.record_use()
                        if self._pool:
                            self._pool.release(pool_id)
                            events.append(RuntimeEvent(
                                type="pool_release",
                                message=f"released pool context for {pool_id}",
                                data={"pool_id": pool_id, "pool_request_count": pool_lease.request_count},
                            ))
                    else:
                        _close_browser_session(session, config)
            finally:
                if not use_pool:
                    cm.__exit__(None, None, None)
        except Exception as exc:
            elapsed = time.time() - start_time
            if pool_lease is not None and self._pool:
                self._pool.mark_failed(pool_id, error=str(exc))
                events.append(RuntimeEvent(
                    type="pool_mark_failed",
                    message=f"marked pool context failed for {pool_id}",
                    data={"pool_id": pool_id, "error": str(exc)[:200]},
                ))
            # Update profile health on error
            health_update: dict[str, Any] | None = None
            if self._rotator is not None and active_profile is not None:
                failure = _classify_browser_failure(
                    error=f"{type(exc).__name__}: {exc}",
                    status_code=0,
                    html="",
                    headers={},
                    proxy_selected=proxy_trace.selected,
                )
                self._rotator.update_health(
                    active_profile.profile_id,
                    ok=False,
                    elapsed_seconds=elapsed,
                    failure_category=failure.get("category", "unknown"),
                )
                health_update = self._rotator.get_health(active_profile.profile_id).to_dict()
                events.append(RuntimeEvent(
                    type="profile_health_update",
                    message=f"health updated for {active_profile.profile_id} (error)",
                    data=health_update,
                ))
            failure = _classify_browser_failure(
                error=f"{type(exc).__name__}: {exc}",
                status_code=0,
                html="",
                headers={},
                proxy_selected=proxy_trace.selected,
            )
            events.append(RuntimeEvent(
                type="browser_render_error",
                message=f"{type(exc).__name__}: {exc}",
                data={
                    "resource_counts": resource_counts,
                    "blocked_urls": blocked_urls[:20],
                    "failure_classification": failure,
                },
            ))
            return _browser_failure_response(
                final_url=request.url,
                error=f"{type(exc).__name__}: {exc}",
                engine=self.name,
                config=config,
                context_config=context_config,
                session_mode=session_mode,
                fingerprint_report=fingerprint_report,
                failure_classification=failure,
                events=events,
                proxy_trace=proxy_trace,
                profile_health_update=health_update,
            )

        elapsed = time.time() - start_time
        failure_classification = _classify_browser_failure(
            error="",
            status_code=status_code,
            html=html,
            headers=headers,
            proxy_selected=proxy_trace.selected,
        )

        # Update profile health if rotator is active
        health_update: dict[str, Any] | None = None
        if self._rotator is not None and active_profile is not None:
            render_ok = (status_code == 0 or 200 <= status_code < 400) and failure_classification["category"] == "none"
            self._rotator.update_health(
                active_profile.profile_id,
                ok=render_ok,
                elapsed_seconds=elapsed,
                failure_category=failure_classification.get("category", "none"),
            )
            health_update = self._rotator.get_health(active_profile.profile_id).to_dict()
            events.append(RuntimeEvent(
                type="profile_health_update",
                message=f"health updated for {active_profile.profile_id}",
                data=health_update,
            ))

        events.append(RuntimeEvent(
            type="browser_render_complete",
            message="native browser render completed",
            data={
                "status_code": status_code,
                "final_url": final_url,
                "html_chars": len(html),
                "captured_xhr": len(captured_xhr),
                "blocked_urls": len(blocked_urls),
                "session_mode": session_mode,
                "failure_classification": failure_classification,
            },
        ))
        body = html.encode("utf-8", errors="replace")
        return RuntimeResponse(
            ok=(status_code == 0 or 200 <= status_code < 400) and failure_classification["category"] == "none",
            final_url=final_url,
            status_code=status_code,
            headers=headers,
            cookies=cookies,
            body=body,
            html=html,
            text=html,
            captured_xhr=captured_xhr,
            artifacts=artifacts,
            proxy_trace=proxy_trace,
            runtime_events=events,
            engine_result={
                "engine": self.name,
                "mode": config.mode,
                "session_mode": session_mode,
                "context": context_config.to_safe_dict(),
                "config": config.to_safe_dict(),
                "fingerprint_report": fingerprint_report,
                "failure_classification": failure_classification,
                "resource_counts": resource_counts,
                "blocked_urls": blocked_urls[:200],
                "js_assets": js_assets[:200],
                "capture_errors": errors[:50],
                "visual_recon": visual_recon,
                "pool": self._pool.to_safe_dict() if self._pool and pool_id else None,
                "pool_id": pool_id or None,
                "pool_request_count": pool_lease.request_count if pool_lease else None,
                "profile": active_profile.to_safe_dict() if active_profile else None,
                "profile_id": active_profile.profile_id if active_profile else None,
                "rotator": self._rotator.to_safe_dict() if self._rotator else None,
                "profile_health_update": health_update,
            },
        )


def resolve_native_browser_config(request: RuntimeRequest) -> NativeBrowserConfig:
    """Resolve native browser options from a runtime request."""
    bc = request.browser_config or {}
    mode = request.mode if request.mode in VALID_BROWSER_MODES else "dynamic"
    wait_state = str(bc.get("wait_selector_state") or "attached")
    if wait_state not in VALID_WAIT_STATES:
        wait_state = "attached"

    block_types = _string_set(bc.get("block_resource_types"))
    if bool(bc.get("disable_resources", False)):
        block_types = frozenset(set(block_types) | {"image", "media", "font", "stylesheet"})

    extra_flags = bc.get("extra_flags") or bc.get("args") or []
    if not isinstance(extra_flags, (list, tuple)):
        extra_flags = []
    extra_flags_tuple = tuple(str(item) for item in extra_flags if item)
    init_script = str(bc.get("init_script") or "")
    if mode == "protected":
        extra_flags_tuple = tuple(dict.fromkeys((*extra_flags_tuple, *PROTECTED_MODE_FLAGS)))
        if not init_script:
            init_script = PROTECTED_MODE_INIT_SCRIPT

    return NativeBrowserConfig(
        mode=mode,
        wait_selector_state=wait_state,
        render_time_ms=_bounded_int(
            bc.get("render_time_ms", bc.get("wait_ms", 0)),
            default=0,
            minimum=0,
            maximum=120000,
        ),
        block_resource_types=block_types,
        blocked_domains=_string_set(bc.get("blocked_domains")),
        capture_api=bool(bc.get("capture_api", True)),
        capture_js=bool(bc.get("capture_js", False)),
        max_captures=_bounded_int(bc.get("max_captures"), default=200, minimum=1, maximum=10000),
        max_body_preview_chars=_bounded_int(
            bc.get("max_body_preview_chars"),
            default=2000,
            minimum=0,
            maximum=200000,
        ),
        screenshot=bool(bc.get("screenshot", request.meta.get("screenshot", False))),
        init_script=init_script,
        cdp_url=str(bc.get("cdp_url") or ""),
        executable_path=str(bc.get("executable_path") or ""),
        channel=str(bc.get("channel") or ("chrome" if bc.get("real_chrome") else "")),
        extra_flags=extra_flags_tuple,
        user_data_dir=str(bc.get("user_data_dir") or request.session_profile.get("user_data_dir", "")),
        storage_state_output_path=str(
            bc.get("storage_state_output_path")
            or request.session_profile.get("storage_state_output_path", "")
        ),
        close_persistent_context=bool(bc.get("close_persistent_context", True)),
        visual_recon=bool(bc.get("visual_recon", False)),
    )


def _browser_context_for_request(request: RuntimeRequest) -> BrowserContextConfig:
    bc = request.browser_config or {}
    payload = {
        "headless": bc.get("headless", True),
        "user_agent": bc.get("user_agent") or bc.get("useragent"),
        "viewport": bc.get("viewport"),
        "locale": bc.get("locale", "en-US"),
        "timezone_id": bc.get("timezone_id", "UTC"),
        "extra_http_headers": bc.get("extra_http_headers") or bc.get("extra_headers") or {},
        "storage_state_path": bc.get("storage_state_path") or request.session_profile.get("storage_state_path", ""),
        "proxy_url": bc.get("proxy_url") or _proxy_url_for(request),
        "java_script_enabled": bc.get("java_script_enabled", True),
        "ignore_https_errors": bc.get("ignore_https_errors", False),
        "color_scheme": bc.get("color_scheme", "light"),
    }
    context_config = BrowserContextConfig.from_dict(payload)
    session_headers = request.session_profile.get("headers")
    headers = dict(request.headers)
    if isinstance(session_headers, dict):
        headers.update({str(key): str(value) for key, value in session_headers.items()})
    return context_config.with_runtime_overrides(
        headers=headers,
        storage_state_path=str(request.session_profile.get("storage_state_path") or ""),
        proxy_url=_proxy_url_for(request),
    )


def _open_browser_session(
    pw: Any,
    context_config: BrowserContextConfig,
    config: NativeBrowserConfig,
    timeout_ms: int,
) -> dict[str, Any]:
    if config.user_data_dir:
        context = _open_persistent_context(pw, context_config, config, timeout_ms)
        return {"mode": "persistent", "context": context, "browser": None}
    if config.cdp_url:
        browser = pw.chromium.connect_over_cdp(config.cdp_url, timeout=timeout_ms)
        context = browser.new_context(**context_config.context_options())
        return {"mode": "cdp", "context": context, "browser": browser}
    launch_options = _launch_options(context_config, config)
    browser = pw.chromium.launch(**launch_options)
    context = browser.new_context(**context_config.context_options())
    return {"mode": "ephemeral", "context": context, "browser": browser}


def _open_persistent_context(
    pw: Any,
    context_config: BrowserContextConfig,
    config: NativeBrowserConfig,
    timeout_ms: int,
) -> Any:
    user_data_path = Path(config.user_data_dir)
    user_data_path.mkdir(parents=True, exist_ok=True)
    options = context_config.context_options()
    options.pop("storage_state", None)
    options.update(_launch_options(context_config, config))
    options["timeout"] = timeout_ms
    return pw.chromium.launch_persistent_context(str(user_data_path), **options)


def _close_browser_session(session: dict[str, Any], config: NativeBrowserConfig) -> None:
    context = session.get("context")
    browser = session.get("browser")
    mode = session.get("mode", "ephemeral")
    if mode == "persistent":
        if config.close_persistent_context and context is not None:
            context.close()
        return
    if browser is not None:
        browser.close()
        return
    if context is not None:
        context.close()


def _launch_options(
    context_config: BrowserContextConfig,
    config: NativeBrowserConfig,
) -> dict[str, Any]:
    options: dict[str, Any] = {"headless": context_config.headless}
    if context_config.proxy_url:
        options["proxy"] = _playwright_proxy(context_config.proxy_url)
    if config.executable_path:
        options["executable_path"] = config.executable_path
    if config.channel:
        options["channel"] = config.channel
    if config.extra_flags:
        options["args"] = list(config.extra_flags)
    return options


def _playwright_proxy(proxy_url: str) -> dict[str, str]:
    parsed = urlparse(proxy_url)
    if not parsed.hostname:
        return {"server": proxy_url}
    server = f"{parsed.scheme or 'http'}://{parsed.hostname}"
    if parsed.port:
        server += f":{parsed.port}"
    proxy: dict[str, str] = {"server": server}
    if parsed.username:
        proxy["username"] = parsed.username
    if parsed.password:
        proxy["password"] = parsed.password
    return proxy


def _add_request_cookies(context: Any, request: RuntimeRequest) -> None:
    cookies = dict(request.cookies or {})
    session_cookies = request.session_profile.get("cookies")
    if isinstance(session_cookies, dict):
        cookies.update({str(key): str(value) for key, value in session_cookies.items()})
    if not cookies:
        return
    payload = [
        {"name": str(name), "value": str(value), "url": request.url}
        for name, value in cookies.items()
    ]
    try:
        context.add_cookies(payload)
    except Exception:
        return


def _capture_artifacts(
    page: Any,
    final_url: str,
    config: NativeBrowserConfig,
    storage_state_path: str = "",
) -> list[RuntimeArtifact]:
    artifacts: list[RuntimeArtifact] = []
    if storage_state_path:
        artifacts.append(RuntimeArtifact(
            kind="storage_state",
            path=storage_state_path,
            url=final_url,
            meta={"source": "native_browser"},
        ))
    if not config.screenshot:
        return artifacts
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = (
        final_url.replace("https://", "")
        .replace("http://", "")
        .replace("/", "_")
        .replace("?", "_")
        .replace("&", "_")[:100]
    ) or "page"
    path = SCREENSHOT_DIR / f"{safe_name}.png"
    page.screenshot(path=str(path), full_page=True)
    artifacts.append(RuntimeArtifact(kind="screenshot", path=str(path), url=final_url))
    return artifacts


def _persist_storage_state(context: Any, config: NativeBrowserConfig) -> str:
    if not config.storage_state_output_path:
        return ""
    path = Path(config.storage_state_output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        context.storage_state(path=str(path))
    except Exception:
        return ""
    return str(path)


def _session_mode_for(config: NativeBrowserConfig, context_config: BrowserContextConfig) -> str:
    if config.user_data_dir:
        return "persistent"
    if config.cdp_url:
        return "cdp"
    if context_config.storage_state_path or config.storage_state_output_path:
        return "storage_state"
    return "ephemeral"


def _capture_response_preview(
    *,
    response: Any,
    url: str,
    status_code: int,
    content_type: str,
    resource_type: str,
    method: str,
    max_chars: int,
    errors: list[str],
) -> dict[str, Any]:
    body_preview = ""
    body_truncated = False
    size_bytes = 0
    if max_chars > 0:
        try:
            body = response.body()
            if isinstance(body, str):
                body_bytes = body.encode("utf-8", errors="replace")
            else:
                body_bytes = bytes(body or b"")
            size_bytes = len(body_bytes)
            body_text = body_bytes.decode("utf-8", errors="replace")
            body_preview = body_text[:max_chars]
            body_truncated = len(body_text) > max_chars
        except Exception as exc:
            errors.append(f"body_read_error:{url}:{type(exc).__name__}:{exc}")
    return {
        "url": url,
        "method": method,
        "status_code": status_code,
        "content_type": content_type,
        "resource_type": resource_type,
        "body_preview": body_preview,
        "body_truncated": body_truncated,
        "size_bytes": size_bytes,
    }


def _looks_like_api_response(
    capture_pattern: str,
    response_url: str,
    resource_type: str,
    content_type: str,
) -> bool:
    if capture_pattern:
        try:
            if re.search(capture_pattern, response_url):
                return True
        except re.error:
            return False
    return resource_type in API_RESOURCE_TYPES or "application/json" in content_type


def _should_block(url: str, resource_type: str, config: NativeBrowserConfig) -> bool:
    if resource_type in config.block_resource_types:
        return True
    if not url or not config.blocked_domains:
        return False
    hostname = (urlparse(url).hostname or "").lower()
    return any(hostname == domain or hostname.endswith("." + domain) for domain in config.blocked_domains)


def _proxy_url_for(request: RuntimeRequest) -> str:
    return str(
        request.proxy_config.get("proxy")
        or request.proxy_config.get("url")
        or request.proxy_config.get("default_proxy")
        or ""
    )


def _proxy_trace_for(request: RuntimeRequest) -> RuntimeProxyTrace:
    proxy_url = _proxy_url_for(request)
    if not proxy_url:
        return RuntimeProxyTrace(selected=False, source="none")
    return RuntimeProxyTrace(
        selected=True,
        proxy=proxy_url,
        source=str(request.proxy_config.get("source") or "request"),
        provider=str(request.proxy_config.get("provider") or ""),
        strategy=str(request.proxy_config.get("strategy") or ""),
    )


def _cookies_from_context(context: Any) -> dict[str, str]:
    try:
        raw = context.cookies()
    except Exception:
        return {}
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    if isinstance(raw, list):
        result: dict[str, str] = {}
        for item in raw:
            if isinstance(item, dict) and item.get("name") is not None:
                result[str(item.get("name"))] = str(item.get("value") or "")
        return result
    return {}


def _header_value(headers: dict[str, Any], name: str) -> str:
    target = name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return str(value)
    return ""


def _string_set(value: Any) -> frozenset[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(str(item).strip().lower() for item in value if str(item).strip())


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _browser_failure_response(
    *,
    final_url: str,
    error: str,
    engine: str,
    config: NativeBrowserConfig,
    context_config: BrowserContextConfig,
    session_mode: str,
    fingerprint_report: dict[str, Any],
    failure_classification: dict[str, Any],
    events: list[RuntimeEvent],
    proxy_trace: RuntimeProxyTrace,
    profile_health_update: dict[str, Any] | None = None,
) -> RuntimeResponse:
    return RuntimeResponse(
        ok=False,
        final_url=final_url,
        proxy_trace=proxy_trace,
        runtime_events=events,
        error=redact_error_message(error),
        engine_result={
            "engine": engine,
            "mode": config.mode,
            "session_mode": session_mode,
            "context": context_config.to_safe_dict(),
            "config": config.to_safe_dict(),
            "fingerprint_report": fingerprint_report,
            "failure_classification": failure_classification,
            "profile_health_update": profile_health_update,
        },
    )


def _classify_browser_failure(
    *,
    error: str,
    status_code: int,
    html: str,
    headers: dict[str, Any],
    proxy_selected: bool,
) -> dict[str, Any]:
    lowered = (error or "").lower()
    if "playwright is not installed" in lowered:
        return _failure("playwright_missing", "high", "playwright_missing")

    if _looks_like_browser_install_error(lowered):
        return _failure("browser_install_or_launch", "high", _first_error_token(error))

    if "timeout" in lowered or "timed out" in lowered:
        return _failure("navigation_timeout", "medium", _first_error_token(error))

    if _looks_like_proxy_error(lowered):
        return _failure("proxy_error", "medium", _first_error_token(error), proxy_selected=proxy_selected)

    challenge = detect_challenge_signal(html, status_code=status_code or None, response_headers=headers)
    if challenge.detected:
        category = "challenge_like" if challenge.kind in {"managed_challenge", "captcha"} else "http_blocked"
        return {
            "category": category,
            "severity": challenge.severity,
            "reason": challenge.primary_marker or challenge.kind,
            "status_code": status_code,
            "challenge": challenge.to_dict(),
            "proxy_selected": proxy_selected,
        }

    if status_code in BLOCKED_STATUS_CODES:
        severity = "medium" if status_code in {401, 407, 429} else "high"
        return _failure("http_blocked", severity, f"status:{status_code}", status_code=status_code)

    if error:
        return _failure("unknown", "medium", _first_error_token(error), proxy_selected=proxy_selected)

    return _failure("none", "low", "", status_code=status_code)


def _failure(
    category: str,
    severity: str,
    reason: str,
    *,
    status_code: int = 0,
    proxy_selected: bool = False,
) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "reason": redact_error_message(reason),
        "status_code": status_code,
        "proxy_selected": proxy_selected,
    }


def _looks_like_browser_install_error(lowered_error: str) -> bool:
    markers = (
        "executable doesn't exist",
        "browser has not been installed",
        "please run playwright install",
        "failed to launch",
        "browser closed",
        "target page, context or browser has been closed",
    )
    return any(marker in lowered_error for marker in markers)


def _looks_like_proxy_error(lowered_error: str) -> bool:
    markers = (
        "proxy",
        "net::err_proxy",
        "tunnel connection failed",
        "socks",
        "407 proxy authentication",
    )
    return any(marker in lowered_error for marker in markers)


def _first_error_token(error: str) -> str:
    text = str(error or "").strip().splitlines()[0] if error else ""
    return text[:200]


def _apply_profile_to_request(request: RuntimeRequest, profile: BrowserProfile) -> RuntimeRequest:
    """Merge a BrowserProfile's options into a RuntimeRequest's browser_config."""
    bc = dict(request.browser_config or {})
    ctx_opts = profile.to_context_options()
    launch_opts = profile.to_launch_options()

    # Apply context options
    if ctx_opts.get("user_agent"):
        bc["user_agent"] = ctx_opts["user_agent"]
    if ctx_opts.get("viewport"):
        bc["viewport"] = ctx_opts["viewport"]
    if ctx_opts.get("locale"):
        bc["locale"] = ctx_opts["locale"]
    if ctx_opts.get("timezone_id"):
        bc["timezone_id"] = ctx_opts["timezone_id"]
    if ctx_opts.get("color_scheme"):
        bc["color_scheme"] = ctx_opts["color_scheme"]

    # Apply launch options
    if launch_opts.get("channel"):
        bc["channel"] = launch_opts["channel"]
    if launch_opts.get("proxy"):
        bc["proxy_url"] = launch_opts["proxy"]
    if launch_opts.get("args"):
        bc["extra_flags"] = launch_opts["args"]

    # Apply resource blocking
    if profile.block_resource_types:
        bc["block_resource_types"] = list(profile.block_resource_types)

    # Apply mode
    if profile.protected_mode:
        request = RuntimeRequest(
            url=request.url,
            method=request.method,
            mode="protected",
            headers=request.headers,
            cookies=request.cookies,
            params=request.params,
            data=request.data,
            json=request.json,
            selectors=request.selectors,
            selector_config=request.selector_config,
            browser_config=bc,
            session_profile=request.session_profile,
            proxy_config=request.proxy_config,
            capture_xhr=request.capture_xhr,
            wait_selector=request.wait_selector,
            wait_until=request.wait_until,
            timeout_ms=request.timeout_ms,
            max_items=request.max_items,
            meta=request.meta,
        )
    else:
        request = RuntimeRequest(
            url=request.url,
            method=request.method,
            mode=request.mode,
            headers=request.headers,
            cookies=request.cookies,
            params=request.params,
            data=request.data,
            json=request.json,
            selectors=request.selectors,
            selector_config=request.selector_config,
            browser_config=bc,
            session_profile=request.session_profile,
            proxy_config=request.proxy_config,
            capture_xhr=request.capture_xhr,
            wait_selector=request.wait_selector,
            wait_until=request.wait_until,
            timeout_ms=request.timeout_ms,
            max_items=request.max_items,
            meta=request.meta,
        )

    # Auto-set pool_id from profile_id if pool is in use
    if "pool_id" not in bc:
        bc["pool_id"] = profile.profile_id
        request = RuntimeRequest(
            url=request.url,
            method=request.method,
            mode=request.mode,
            headers=request.headers,
            cookies=request.cookies,
            params=request.params,
            data=request.data,
            json=request.json,
            selectors=request.selectors,
            selector_config=request.selector_config,
            browser_config=bc,
            session_profile=request.session_profile,
            proxy_config=request.proxy_config,
            capture_xhr=request.capture_xhr,
            wait_selector=request.wait_selector,
            wait_until=request.wait_until,
            timeout_ms=request.timeout_ms,
            max_items=request.max_items,
            meta=request.meta,
        )

    return request
