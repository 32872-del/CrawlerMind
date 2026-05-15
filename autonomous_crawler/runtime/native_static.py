"""CLM-native static HTTP runtime.

This runtime is the first step of SCRAPLING-ABSORB-1.  It absorbs the useful
static-fetch behavior proven by the Scrapling transition adapter into a
CLM-owned backend contract.  It does not import or call ``scrapling``.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from autonomous_crawler.tools.proxy_manager import redact_proxy_url

from .models import RuntimeEvent, RuntimeProxyTrace, RuntimeRequest, RuntimeResponse


DEFAULT_TRANSPORT = "httpx"
SUPPORTED_TRANSPORTS = {"httpx", "curl_cffi"}
DEFAULT_IMPERSONATE = "chrome124"

# Connection-level errors that indicate a proxy may be broken (not an application-level issue).
_PROXY_RETRYABLE_ERRORS = (
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
    TimeoutError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)


class NativeFetchRuntime:
    """CLM-owned ``FetchRuntime`` implementation for static HTTP/API requests."""

    name: str = "native_static"

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        retry_cfg = _RetryConfig.from_proxy_config(request.proxy_config)
        transport = _transport_for(request)
        events: list[RuntimeEvent] = [
            RuntimeEvent(
                type="fetch_start",
                message="native static fetch started",
                data={
                    "transport": transport,
                    "method": request.method,
                    "url": request.url,
                    "proxy": redact_proxy_url(_proxy_url_for(request)),
                    "max_proxy_attempts": retry_cfg.max_attempts,
                },
            )
        ]

        last_error: str = ""
        last_proxy_url: str = ""

        for attempt in range(retry_cfg.max_attempts):
            proxy_url = _select_proxy_for_attempt(request, retry_cfg, attempt)
            last_proxy_url = proxy_url

            events.append(
                RuntimeEvent(
                    type="proxy_attempt",
                    message=f"proxy attempt {attempt + 1}/{retry_cfg.max_attempts}",
                    data={
                        "attempt": attempt + 1,
                        "proxy": redact_proxy_url(proxy_url),
                    },
                )
            )

            try:
                response = self._do_fetch(request, transport, proxy_url)
            except _PROXY_RETRYABLE_ERRORS as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                _record_proxy_failure(retry_cfg, proxy_url, last_error)
                events.append(
                    RuntimeEvent(
                        type="proxy_failure_recorded",
                        message=f"proxy failure recorded: {type(exc).__name__}",
                        data={"proxy": redact_proxy_url(proxy_url)},
                    )
                )
                if attempt + 1 < retry_cfg.max_attempts:
                    events.append(
                        RuntimeEvent(
                            type="proxy_retry",
                            message=f"retrying with next proxy (attempt {attempt + 2})",
                            data={"failed_proxy": redact_proxy_url(proxy_url)},
                        )
                    )
                    continue
                # Last attempt failed — fall through to error return below
                break
            except Exception as exc:
                # Non-proxy error (e.g. programming error) — do not retry
                last_error = f"{type(exc).__name__}: {exc}"
                events.append(
                    RuntimeEvent(
                        type="fetch_error",
                        message=f"{type(exc).__name__}: {exc}",
                        data={"transport": transport},
                    )
                )
                return RuntimeResponse.failure(
                    final_url=request.url,
                    error=last_error,
                    engine=self.name,
                    events=events,
                    proxy_trace=_proxy_trace_for(request, proxy_url),
                )

            # Success path
            _record_proxy_success(retry_cfg, proxy_url)
            events.append(
                RuntimeEvent(
                    type="proxy_success_recorded",
                    message="proxy success recorded",
                    data={"proxy": redact_proxy_url(proxy_url)},
                )
            )
            runtime_response = _response_from_http_response(
                request_url=request.url,
                response=response,
                transport=transport,
                events=events,
                proxy_trace=_proxy_trace_for(request, proxy_url),
            )
            runtime_response.runtime_events.append(
                RuntimeEvent(
                    type="fetch_complete",
                    message="native static fetch completed",
                    data={
                        "transport": transport,
                        "status_code": runtime_response.status_code,
                        "final_url": runtime_response.final_url,
                        "body_bytes": len(runtime_response.body),
                        "proxy_attempts": attempt + 1,
                    },
                )
            )
            return runtime_response

        # All attempts exhausted
        events.append(
            RuntimeEvent(
                type="fetch_error",
                message=f"all {retry_cfg.max_attempts} proxy attempts failed",
                data={"transport": transport, "last_error": last_error},
            )
        )
        return RuntimeResponse.failure(
            final_url=request.url,
            error=f"all {retry_cfg.max_attempts} proxy attempts failed: {last_error}",
            engine=self.name,
            events=events,
            proxy_trace=_proxy_trace_for(request, last_proxy_url),
        )

    def _fetch_httpx(self, request: RuntimeRequest, proxy_url: str = "") -> httpx.Response:
        if not proxy_url:
            proxy_url = _proxy_url_for(request) or None
        timeout = max(request.timeout_ms / 1000, 1.0)
        client_kwargs: dict[str, Any] = {
            "follow_redirects": True,
            "timeout": httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            "headers": dict(request.headers),
            "cookies": dict(request.cookies),
        }
        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        with httpx.Client(**client_kwargs) as client:
            return client.request(
                request.method,
                request.url,
                params=request.params or None,
                content=request.data if request.json is None else None,
                json=request.json,
            )

    def _fetch_curl_cffi(self, request: RuntimeRequest, proxy_url: str = "") -> Any:
        import curl_cffi.requests as curl_requests

        if not proxy_url:
            proxy_url = _proxy_url_for(request)
        kwargs: dict[str, Any] = {
            "headers": dict(request.headers) or None,
            "cookies": dict(request.cookies) or None,
            "timeout": max(request.timeout_ms / 1000, 1.0),
            "allow_redirects": True,
            "impersonate": str(request.meta.get("impersonate") or DEFAULT_IMPERSONATE),
        }
        if proxy_url:
            kwargs["proxy"] = proxy_url
        if request.params:
            kwargs["params"] = request.params
        if request.json is not None:
            kwargs["json"] = request.json
        elif request.data is not None:
            kwargs["data"] = request.data

        clean_kwargs = {key: value for key, value in kwargs.items() if value is not None}
        return curl_requests.request(request.method, request.url, **clean_kwargs)

    def _do_fetch(self, request: RuntimeRequest, transport: str, proxy_url: str) -> Any:
        """Dispatch to the appropriate transport with a specific proxy URL."""
        if transport == "curl_cffi":
            return self._fetch_curl_cffi(request, proxy_url=proxy_url)
        return self._fetch_httpx(request, proxy_url=proxy_url)


# ======================================================================
# Retry orchestration helpers
# ======================================================================

class _RetryConfig:
    """Parsed retry policy from request.proxy_config."""

    __slots__ = ("enabled", "max_attempts", "pool_provider", "health_store")

    def __init__(
        self,
        *,
        enabled: bool = False,
        max_attempts: int = 1,
        pool_provider: Any = None,
        health_store: Any = None,
    ) -> None:
        self.enabled = enabled
        self.max_attempts = max(1, max_attempts)
        self.pool_provider = pool_provider
        self.health_store = health_store

    @classmethod
    def from_proxy_config(cls, proxy_config: dict[str, Any]) -> "_RetryConfig":
        return cls(
            enabled=bool(proxy_config.get("retry_on_proxy_failure", False)),
            max_attempts=int(proxy_config.get("max_proxy_attempts") or 1),
            pool_provider=proxy_config.get("pool_provider"),
            health_store=proxy_config.get("health_store"),
        )


def _select_proxy_for_attempt(
    request: RuntimeRequest,
    retry_cfg: _RetryConfig,
    attempt: int,
) -> str:
    """Select a proxy URL for the given attempt number.

    On attempt 0, use the request's configured proxy.  On subsequent attempts,
    ask the pool provider for an alternative (skipping cooldown proxies).
    """
    if attempt == 0:
        return _proxy_url_for(request)

    # Ask pool provider for the next available proxy
    if retry_cfg.pool_provider is not None:
        try:
            selection = retry_cfg.pool_provider.select(request.url, now=time.time())
            if selection.proxy_url:
                return selection.proxy_url
        except Exception:
            pass

    # Fallback to request's configured proxy
    return _proxy_url_for(request)


def _record_proxy_failure(retry_cfg: _RetryConfig, proxy_url: str, error: str) -> None:
    """Record a proxy failure into the health store and pool provider."""
    if not proxy_url:
        return
    now = time.time()
    if retry_cfg.health_store is not None:
        retry_cfg.health_store.record_failure(proxy_url, error=error, now=now)
    if retry_cfg.pool_provider is not None:
        try:
            retry_cfg.pool_provider.report_result(proxy_url, ok=False, error=error, now=now)
        except Exception:
            pass


def _record_proxy_success(retry_cfg: _RetryConfig, proxy_url: str) -> None:
    """Record a proxy success into the health store and pool provider."""
    if not proxy_url:
        return
    now = time.time()
    if retry_cfg.health_store is not None:
        retry_cfg.health_store.record_success(proxy_url, now=now)
    if retry_cfg.pool_provider is not None:
        try:
            retry_cfg.pool_provider.report_result(proxy_url, ok=True, now=now)
        except Exception:
            pass


def _transport_for(request: RuntimeRequest) -> str:
    transport = str(
        request.meta.get("transport")
        or request.meta.get("static_transport")
        or request.selector_config.get("transport")
        or DEFAULT_TRANSPORT
    ).strip().lower()
    return transport if transport in SUPPORTED_TRANSPORTS else DEFAULT_TRANSPORT


def _proxy_url_for(request: RuntimeRequest) -> str:
    return str(
        request.proxy_config.get("proxy")
        or request.proxy_config.get("url")
        or request.proxy_config.get("default_proxy")
        or ""
    )


def _proxy_trace_for(request: RuntimeRequest, proxy_url: str = "") -> RuntimeProxyTrace:
    if not proxy_url:
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


def _response_from_http_response(
    *,
    request_url: str,
    response: Any,
    transport: str,
    events: list[RuntimeEvent],
    proxy_trace: RuntimeProxyTrace,
) -> RuntimeResponse:
    status_code = int(getattr(response, "status_code", getattr(response, "status", 0)) or 0)
    final_url = str(getattr(response, "url", "") or request_url)
    headers = dict(getattr(response, "headers", {}) or {})
    cookies = _cookies_from_response(response)
    body = _body_from_response(response)
    text = _text_from_response(response, body)
    html = text if _looks_textual(headers, text) else ""
    http_version = str(getattr(response, "http_version", "") or "")
    return RuntimeResponse(
        ok=200 <= status_code < 400,
        final_url=final_url,
        status_code=status_code,
        headers=headers,
        cookies=cookies,
        body=body,
        html=html,
        text=text,
        proxy_trace=proxy_trace,
        runtime_events=events,
        engine_result={
            "engine": "native_static",
            "transport": transport,
            "http_version": http_version,
        },
    )


def _cookies_from_response(response: Any) -> dict[str, str]:
    raw = getattr(response, "cookies", {}) or {}
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    try:
        return {str(key): str(value) for key, value in raw.items()}
    except Exception:
        return {}


def _body_from_response(response: Any) -> bytes:
    for attr in ("content", "body"):
        value = getattr(response, attr, None)
        if value is None:
            continue
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode("utf-8", errors="replace")
    text = str(getattr(response, "text", "") or "")
    return text.encode("utf-8", errors="replace")


def _text_from_response(response: Any, body: bytes) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    try:
        return body.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _looks_textual(headers: dict[str, str], text: str) -> bool:
    content_type = ""
    for key, value in headers.items():
        if str(key).lower() == "content-type":
            content_type = str(value).lower()
            break
    if any(marker in content_type for marker in ("text/", "html", "xml", "json", "javascript")):
        return True
    stripped = (text or "").lstrip()
    return stripped.startswith(("<", "{", "["))

