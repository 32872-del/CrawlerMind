"""Scrapling static HTTP runtime adapter.

Wraps Scrapling's ``Fetcher`` (curl_cffi-based) behind the CLM
``FetchRuntime`` protocol so workflow layers never import Scrapling
directly.
"""
from __future__ import annotations

from typing import Any

from .models import RuntimeEvent, RuntimeProxyTrace, RuntimeRequest, RuntimeResponse

_HAS_SCRAPLING = True
try:
    from scrapling import Fetcher
except ImportError:
    _HAS_SCRAPLING = False


class ScraplingStaticRuntime:
    """``FetchRuntime`` adapter backed by Scrapling's ``Fetcher``."""

    name: str = "scrapling_static"

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        if not _HAS_SCRAPLING:
            return RuntimeResponse.failure(
                final_url=request.url,
                error="scrapling package is not installed",
                engine=self.name,
            )

        kwargs: dict[str, Any] = {}
        if request.headers:
            kwargs["headers"] = dict(request.headers)
        if request.cookies:
            kwargs["cookies"] = dict(request.cookies)
        if request.timeout_ms:
            kwargs["timeout"] = request.timeout_ms / 1000
        proxy_url = request.proxy_config.get("proxy") or request.proxy_config.get("url") or ""
        if proxy_url:
            kwargs["proxy"] = proxy_url

        try:
            response = self._dispatch(request, kwargs)
        except Exception as exc:
            return RuntimeResponse.failure(
                final_url=request.url,
                error=f"{type(exc).__name__}: {exc}",
                engine=self.name,
            )

        return self._build_response(request.url, response)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dispatch(self, request: RuntimeRequest, kwargs: dict[str, Any]) -> Any:
        method = request.method.upper()
        if method == "GET":
            return Fetcher.get(request.url, **kwargs)
        if method == "POST":
            if request.json is not None:
                kwargs["json"] = request.json
            elif request.data is not None:
                kwargs["data"] = request.data
            return Fetcher.post(request.url, **kwargs)
        if method == "PUT":
            if request.json is not None:
                kwargs["json"] = request.json
            elif request.data is not None:
                kwargs["data"] = request.data
            return Fetcher.put(request.url, **kwargs)
        if method == "DELETE":
            return Fetcher.delete(request.url, **kwargs)
        return Fetcher.get(request.url, **kwargs)

    @staticmethod
    def _build_response(url: str, resp: Any) -> RuntimeResponse:
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

        return RuntimeResponse(
            ok=200 <= status < 400,
            final_url=getattr(resp, "url", url) or url,
            status_code=status,
            headers=headers,
            cookies=cookies,
            body=body,
            html=html,
            text=str(getattr(resp, "text", "") or ""),
            engine_result={"engine": "scrapling_static"},
        )
