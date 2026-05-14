"""Scrapling browser runtime adapter.

Wraps Scrapling's ``DynamicFetcher`` / ``StealthyFetcher`` and their session
variants behind the CLM ``BrowserRuntime`` protocol.  Also provides proxy
format conversion helpers mapping CLM ``ProxyConfig`` to Scrapling's
``proxy`` / ``ProxyRotator`` interfaces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .models import RuntimeEvent, RuntimeProxyTrace, RuntimeRequest, RuntimeResponse

_HAS_SCRAPLING = True
try:
    from scrapling import DynamicFetcher, StealthyFetcher
    from scrapling.fetchers import DynamicSession, StealthySession
    from scrapling.engines.toolbelt.proxy_rotation import ProxyRotator
except ImportError:
    _HAS_SCRAPLING = False

# ---------------------------------------------------------------------------
# Browser mode constants
# ---------------------------------------------------------------------------
MODE_DYNAMIC = "dynamic"
MODE_PROTECTED = "protected"
VALID_BROWSER_MODES = {MODE_DYNAMIC, MODE_PROTECTED}

# Playwright wait-for-selector states
VALID_WAIT_STATES = {"attached", "detached", "visible", "hidden"}

# Scrapling block status codes (from proxy-blocking.md)
BLOCK_STATUS_CODES = {401, 403, 407, 429, 444, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# CLM → Scrapling browser config mapping
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScraplingBrowserConfig:
    """Resolved browser configuration ready to pass to Scrapling fetchers."""

    mode: str = MODE_DYNAMIC
    headless: bool = True
    real_chrome: bool = False
    cdp_url: str = ""
    wait_selector: str = ""
    wait_selector_state: str = "attached"
    network_idle: bool = False
    load_dom: bool = True
    timeout_ms: int = 30000
    wait_ms: int = 0
    disable_resources: bool = False
    capture_xhr: str = ""
    blocked_domains: frozenset[str] = field(default_factory=frozenset)
    block_ads: bool = False
    google_search: bool = True
    dns_over_https: bool = False
    retries: int = 3
    retry_delay: float = 1.0
    locale: str = ""
    timezone_id: str = ""
    useragent: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)
    executable_path: str = ""
    init_script: str = ""
    extra_flags: list[str] = field(default_factory=list)
    selector_config: dict[str, Any] = field(default_factory=dict)

    # Protected-mode only (StealthyFetcher)
    solve_cloudflare: bool = True
    block_webrtc: bool = True
    hide_canvas: bool = True
    allow_webgl: bool = True

    # Session continuity
    user_data_dir: str = ""
    max_pages: int = 0

    def to_fetch_kwargs(self) -> dict[str, Any]:
        """Convert to kwargs dict for DynamicFetcher.fetch() / StealthyFetcher.fetch()."""
        kwargs: dict[str, Any] = {
            "headless": self.headless,
            "network_idle": self.network_idle,
            "load_dom": self.load_dom,
            "timeout": self.timeout_ms,
            "google_search": self.google_search,
            "retries": self.retries,
            "retry_delay": self.retry_delay,
        }
        if self.real_chrome:
            kwargs["real_chrome"] = True
        if self.cdp_url:
            kwargs["cdp_url"] = self.cdp_url
        if self.wait_selector:
            kwargs["wait_selector"] = self.wait_selector
            kwargs["wait_selector_state"] = self.wait_selector_state
        if self.wait_ms > 0:
            kwargs["wait"] = self.wait_ms
        if self.disable_resources:
            kwargs["disable_resources"] = True
        if self.capture_xhr:
            kwargs["capture_xhr"] = self.capture_xhr
        if self.blocked_domains:
            kwargs["blocked_domains"] = set(self.blocked_domains)
        if self.block_ads:
            kwargs["block_ads"] = True
        if self.dns_over_https:
            kwargs["dns_over_https"] = True
        if self.locale:
            kwargs["locale"] = self.locale
        if self.timezone_id:
            kwargs["timezone_id"] = self.timezone_id
        if self.useragent:
            kwargs["useragent"] = self.useragent
        if self.extra_headers:
            kwargs["extra_headers"] = dict(self.extra_headers)
        if self.executable_path:
            kwargs["executable_path"] = self.executable_path
        if self.init_script:
            kwargs["init_script"] = self.init_script
        if self.extra_flags:
            kwargs["extra_flags"] = list(self.extra_flags)
        if self.selector_config:
            kwargs["selector_config"] = dict(self.selector_config)

        # Protected-mode extras (StealthyFetcher only)
        if self.mode == MODE_PROTECTED:
            kwargs["solve_cloudflare"] = self.solve_cloudflare
            kwargs["block_webrtc"] = self.block_webrtc
            kwargs["hide_canvas"] = self.hide_canvas
            kwargs["allow_webgl"] = self.allow_webgl

        return kwargs

    def to_session_kwargs(self) -> dict[str, Any]:
        """Convert to kwargs for DynamicSession / StealthySession constructor."""
        kwargs = self.to_fetch_kwargs()
        # Session constructor doesn't accept 'wait' per-request
        kwargs.pop("wait", None)
        if self.max_pages > 0:
            kwargs["max_pages"] = self.max_pages
        if self.user_data_dir:
            kwargs["user_data_dir"] = self.user_data_dir
        return kwargs


def resolve_browser_config(request: RuntimeRequest) -> ScraplingBrowserConfig:
    """Extract ScraplingBrowserConfig from a CLM RuntimeRequest."""
    bc = request.browser_config
    mode = request.mode if request.mode in VALID_BROWSER_MODES else MODE_DYNAMIC

    wait_selector = request.wait_selector or bc.get("wait_selector", "")
    wait_state = bc.get("wait_selector_state", "attached")
    if wait_state not in VALID_WAIT_STATES:
        wait_state = "attached"

    network_idle = request.wait_until == "networkidle" or bool(bc.get("network_idle", False))

    blocked = bc.get("blocked_domains")
    if isinstance(blocked, (list, tuple, set)):
        blocked_domains = frozenset(str(d) for d in blocked)
    else:
        blocked_domains = frozenset()

    extra_flags = bc.get("extra_flags")
    if isinstance(extra_flags, (list, tuple)):
        extra_flags_list = [str(f) for f in extra_flags]
    else:
        extra_flags_list = []

    return ScraplingBrowserConfig(
        mode=mode,
        headless=bool(bc.get("headless", True)),
        real_chrome=bool(bc.get("real_chrome", False)),
        cdp_url=str(bc.get("cdp_url", "")),
        wait_selector=wait_selector,
        wait_selector_state=wait_state,
        network_idle=network_idle,
        load_dom=bool(bc.get("load_dom", True)),
        timeout_ms=int(request.timeout_ms or 30000),
        wait_ms=int(bc.get("wait_ms", 0)),
        disable_resources=bool(bc.get("disable_resources", False)),
        capture_xhr=request.capture_xhr or str(bc.get("capture_xhr", "")),
        blocked_domains=blocked_domains,
        block_ads=bool(bc.get("block_ads", False)),
        google_search=bool(bc.get("google_search", True)),
        dns_over_https=bool(bc.get("dns_over_https", False)),
        retries=int(bc.get("retries", 3)),
        retry_delay=float(bc.get("retry_delay", 1.0)),
        locale=str(bc.get("locale", "")),
        timezone_id=str(bc.get("timezone_id", "")),
        useragent=str(bc.get("useragent", "")),
        extra_headers=_string_dict(bc.get("extra_headers")),
        executable_path=str(bc.get("executable_path", "")),
        init_script=str(bc.get("init_script", "")),
        extra_flags=extra_flags_list,
        selector_config=dict(bc.get("selector_config") or {}),
        solve_cloudflare=bool(bc.get("solve_cloudflare", True)),
        block_webrtc=bool(bc.get("block_webrtc", True)),
        hide_canvas=bool(bc.get("hide_canvas", True)),
        allow_webgl=bool(bc.get("allow_webgl", True)),
        user_data_dir=str(bc.get("user_data_dir", "")),
        max_pages=int(bc.get("max_pages", 0)),
    )


# ---------------------------------------------------------------------------
# Proxy format conversion: CLM ProxyConfig → Scrapling proxy / ProxyRotator
# ---------------------------------------------------------------------------

def clm_proxy_to_scrapling(proxy_url: str) -> str | dict[str, str]:
    """Convert a CLM proxy URL string to Scrapling's proxy format.

    Scrapling accepts either:
    - ``"http://user:pass@host:port"`` (string)
    - ``{"server": "...", "username": "...", "password": "..."}`` (dict)

    This function returns the dict form for credential isolation.
    Returns empty string if proxy_url is empty.
    """
    if not proxy_url:
        return ""
    from urllib.parse import urlparse
    parsed = urlparse(proxy_url)
    if not parsed.hostname:
        return proxy_url
    server = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        server += f":{parsed.port}"
    result: dict[str, str] = {"server": server}
    if parsed.username:
        result["username"] = parsed.username
    if parsed.password:
        result["password"] = parsed.password
    return result


def clm_proxy_dict_for_browser(proxy_url: str) -> dict[str, str]:
    """Convert proxy URL to Playwright/Scrapling browser proxy dict format.

    Same as ``clm_proxy_to_scrapling`` but always returns a dict (or empty dict).
    """
    result = clm_proxy_to_scrapling(proxy_url)
    if isinstance(result, dict):
        return result
    return {}


def build_proxy_rotator(
    proxy_urls: list[str],
    strategy: str = "cyclic",
) -> Any:
    """Build a Scrapling ``ProxyRotator`` from a list of CLM proxy URLs.

    Args:
        proxy_urls: List of proxy URL strings (``http://user:pass@host:port``).
        strategy: Rotation strategy — ``"cyclic"`` (default) or ``"random"``.

    Returns:
        A ``ProxyRotator`` instance, or ``None`` if Scrapling is not installed
        or proxy_urls is empty.
    """
    if not proxy_urls or not _HAS_SCRAPLING:
        return None

    proxies: list[str | dict[str, str]] = []
    for url in proxy_urls:
        converted = clm_proxy_to_scrapling(url)
        proxies.append(converted if converted else url)

    if strategy == "random":
        import random
        def random_strategy(proxies_list: list, current_index: int) -> tuple:
            idx = random.randint(0, len(proxies_list) - 1)
            return proxies_list[idx], idx
        return ProxyRotator(proxies, strategy=random_strategy)

    # Default: cyclic (Scrapling's built-in default)
    return ProxyRotator(proxies)


def select_scrapling_proxy(
    proxy_url: str,
    *,
    use_rotator: bool = False,
    proxy_rotator: Any = None,
) -> tuple[str | dict[str, str] | None, dict[str, Any]]:
    """Select proxy format for a Scrapling fetch call.

    Returns (proxy_arg, trace_info) where:
    - proxy_arg: value to pass to Scrapling's ``proxy`` kwarg, or None
    - trace_info: dict with selection metadata for RuntimeProxyTrace
    """
    if proxy_rotator is not None:
        return None, {"source": "rotator", "selected": True}

    if not proxy_url:
        return None, {"source": "disabled", "selected": False}

    scrapling_proxy = clm_proxy_to_scrapling(proxy_url)
    return scrapling_proxy, {"source": "direct", "selected": True}


# ---------------------------------------------------------------------------
# BrowserRuntime adapter
# ---------------------------------------------------------------------------

class ScraplingBrowserRuntime:
    """``BrowserRuntime`` adapter backed by Scrapling's fetchers."""

    name: str = "scrapling_browser"

    def render(self, request: RuntimeRequest) -> RuntimeResponse:
        if not _HAS_SCRAPLING:
            return RuntimeResponse.failure(
                final_url=request.url,
                error="scrapling package is not installed",
                engine=self.name,
            )

        config = resolve_browser_config(request)
        kwargs = config.to_fetch_kwargs()

        # Wire proxy
        proxy_url = request.proxy_config.get("proxy") or request.proxy_config.get("url") or ""
        proxy_rotator = request.proxy_config.get("proxy_rotator")
        proxy_arg, trace_info = select_scrapling_proxy(
            proxy_url, proxy_rotator=proxy_rotator,
        )
        if proxy_arg is not None:
            kwargs["proxy"] = proxy_arg
        elif proxy_rotator is not None:
            kwargs["proxy_rotator"] = proxy_rotator

        # Wire session cookies / headers from session_profile
        session = request.session_profile
        if session.get("cookies") and isinstance(session["cookies"], dict):
            kwargs["cookies"] = session["cookies"]
        if session.get("headers") and isinstance(session["headers"], dict):
            merged = dict(session["headers"])
            merged.update(kwargs.get("extra_headers", {}))
            kwargs["extra_headers"] = merged

        events: list[RuntimeEvent] = []
        try:
            response = self._fetch(config.mode, request.url, kwargs, config, session)
        except Exception as exc:
            return RuntimeResponse.failure(
                final_url=request.url,
                error=f"{type(exc).__name__}: {exc}",
                engine=self.name,
                events=events,
                proxy_trace=RuntimeProxyTrace(
                    selected=trace_info.get("selected", False),
                    source=trace_info.get("source", "none"),
                ),
            )

        return self._build_response(request.url, response, events, trace_info)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch(
        self,
        mode: str,
        url: str,
        kwargs: dict[str, Any],
        config: ScraplingBrowserConfig,
        session_profile: dict[str, Any],
    ) -> Any:
        """Dispatch to the appropriate Scrapling fetcher/session."""
        # Use session if user_data_dir or max_pages is set
        use_session = bool(config.user_data_dir or config.max_pages > 0)

        if use_session:
            return self._fetch_with_session(mode, url, kwargs, config)

        if mode == MODE_PROTECTED:
            return StealthyFetcher.fetch(url, **kwargs)
        return DynamicFetcher.fetch(url, **kwargs)

    def _fetch_with_session(
        self,
        mode: str,
        url: str,
        kwargs: dict[str, Any],
        config: ScraplingBrowserConfig,
    ) -> Any:
        """Fetch using a session context manager for browser reuse."""
        session_kwargs = config.to_session_kwargs()
        # Per-request overrides
        for key in ("timeout", "wait_selector", "wait_selector_state",
                     "network_idle", "load_dom", "disable_resources",
                     "capture_xhr", "proxy", "extra_headers"):
            if key in kwargs:
                session_kwargs.pop(key, None)

        if mode == MODE_PROTECTED:
            with StealthySession(**session_kwargs) as session:
                per_req = {k: v for k, v in kwargs.items() if k not in session_kwargs}
                return session.fetch(url, **per_req)
        else:
            with DynamicSession(**session_kwargs) as session:
                per_req = {k: v for k, v in kwargs.items() if k not in session_kwargs}
                return session.fetch(url, **per_req)

    @staticmethod
    def _build_response(
        url: str,
        resp: Any,
        events: list[RuntimeEvent],
        trace_info: dict[str, Any],
    ) -> RuntimeResponse:
        """Convert Scrapling response to CLM RuntimeResponse."""
        headers = dict(resp.headers) if hasattr(resp, "headers") else {}
        raw_cookies = getattr(resp, "cookies", {})
        cookies = dict(raw_cookies) if isinstance(raw_cookies, dict) else {}
        status = getattr(resp, "status", 0)
        body = getattr(resp, "body", b"")
        if isinstance(body, str):
            body = body.encode("utf-8", errors="replace")

        html = ""
        try:
            html = body.decode("utf-8", errors="replace")
        except Exception:
            pass

        text = str(getattr(resp, "text", "") or "")

        # Capture XHR responses if available
        captured_xhr: list[dict[str, Any]] = []
        raw_xhr = getattr(resp, "captured_xhr", [])
        if raw_xhr:
            for xhr in raw_xhr:
                xhr_dict: dict[str, Any] = {
                    "url": getattr(xhr, "url", ""),
                    "status": getattr(xhr, "status", 0),
                }
                xhr_body = getattr(xhr, "body", b"")
                if isinstance(xhr_body, bytes):
                    try:
                        xhr_dict["body"] = xhr_body.decode("utf-8", errors="replace")
                    except Exception:
                        xhr_dict["body"] = ""
                captured_xhr.append(xhr_dict)

        final_url = getattr(resp, "url", url) or url

        return RuntimeResponse(
            ok=200 <= status < 400,
            final_url=final_url,
            status_code=status,
            headers=headers,
            cookies=cookies,
            body=body,
            html=html,
            text=text,
            captured_xhr=captured_xhr,
            proxy_trace=RuntimeProxyTrace(
                selected=trace_info.get("selected", False),
                source=trace_info.get("source", "none"),
            ),
            runtime_events=events,
            engine_result={"engine": "scrapling_browser"},
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items()}
