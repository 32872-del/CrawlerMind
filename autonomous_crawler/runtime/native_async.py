"""CLM-native async fetch runtime with per-domain concurrency and backpressure.

This module extends the static fetch runtime into an async-capable pool that
supports long-running crawls with bounded per-domain concurrency, structured
backpressure evidence, and proxy-health integration.  It does not import or
call ``scrapling``.
"""
from __future__ import annotations

import asyncio
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from autonomous_crawler.tools.proxy_manager import redact_proxy_url

from .models import RuntimeEvent, RuntimeProxyTrace, RuntimeRequest, RuntimeResponse
from .native_static import (
    DEFAULT_IMPERSONATE,
    DEFAULT_TRANSPORT,
    SUPPORTED_TRANSPORTS,
    _PROXY_RETRYABLE_ERRORS,
    _RetryConfig,
    _record_proxy_failure,
    _record_proxy_success,
    _response_from_http_response,
    _select_proxy_for_attempt,
    _transport_for,
    _proxy_url_for,
    _proxy_trace_for,
)


@dataclass(frozen=True)
class AsyncFetchMetrics:
    """Inspectable aggregate report from a batch of async fetch responses.

    Built via ``AsyncFetchMetrics.from_responses()``.  All proxy URLs are
    redacted in ``to_dict()`` output.
    """

    total: int = 0
    ok_count: int = 0
    fail_count: int = 0
    domains: dict[str, int] = field(default_factory=dict)
    status_codes: dict[int, int] = field(default_factory=dict)
    proxy_attempts_total: int = 0
    proxy_failures: int = 0
    proxy_successes: int = 0
    proxy_retries: int = 0
    backpressure_events: int = 0
    pool_acquired_events: int = 0
    event_type_counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    max_concurrency_per_domain: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_responses(cls, responses: list[RuntimeResponse]) -> "AsyncFetchMetrics":
        """Build metrics from a list of RuntimeResponse objects."""
        ok = 0
        fail = 0
        domains: Counter[str] = Counter()
        status_codes: Counter[int] = Counter()
        proxy_attempts = 0
        proxy_failures = 0
        proxy_successes = 0
        proxy_retries = 0
        backpressure = 0
        pool_acquired = 0
        event_counts: Counter[str] = Counter()
        errors: list[str] = []
        max_concurrency: dict[str, int] = {}

        for resp in responses:
            if resp.ok:
                ok += 1
            else:
                fail += 1
                if resp.error:
                    errors.append(resp.error)

            if resp.status_code:
                status_codes[resp.status_code] += 1

            for event in resp.runtime_events:
                event_counts[event.type] += 1

                if event.type == "pool_acquired":
                    pool_acquired += 1
                    domain = event.data.get("domain", "")
                    if domain:
                        domains[domain] += 1
                        active = event.data.get("active_per_domain", 0)
                        max_concurrency[domain] = max(
                            max_concurrency.get(domain, 0), active
                        )

                elif event.type == "pool_backpressure":
                    backpressure += 1

                elif event.type == "proxy_attempt":
                    proxy_attempts += 1

                elif event.type == "proxy_failure_recorded":
                    proxy_failures += 1

                elif event.type == "proxy_success_recorded":
                    proxy_successes += 1

                elif event.type == "proxy_retry":
                    proxy_retries += 1

        return cls(
            total=len(responses),
            ok_count=ok,
            fail_count=fail,
            domains=dict(domains),
            status_codes=dict(status_codes),
            proxy_attempts_total=proxy_attempts,
            proxy_failures=proxy_failures,
            proxy_successes=proxy_successes,
            proxy_retries=proxy_retries,
            backpressure_events=backpressure,
            pool_acquired_events=pool_acquired,
            event_type_counts=dict(event_counts),
            errors=errors[:100],  # cap to avoid huge output
            max_concurrency_per_domain=max_concurrency,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "ok_count": self.ok_count,
            "fail_count": self.fail_count,
            "domains": dict(self.domains),
            "status_codes": {str(k): v for k, v in self.status_codes.items()},
            "proxy_attempts_total": self.proxy_attempts_total,
            "proxy_failures": self.proxy_failures,
            "proxy_successes": self.proxy_successes,
            "proxy_retries": self.proxy_retries,
            "backpressure_events": self.backpressure_events,
            "pool_acquired_events": self.pool_acquired_events,
            "event_type_counts": dict(self.event_type_counts),
            "errors": list(self.errors),
            "max_concurrency_per_domain": dict(self.max_concurrency_per_domain),
        }


class DomainConcurrencyPool:
    """Bounded per-domain concurrency with global capacity limit.

    Each domain gets its own ``asyncio.Semaphore`` so that requests to
    different origins can proceed in parallel while a single origin cannot
    starve the pool.  A global semaphore caps total in-flight requests.
    """

    def __init__(self, max_per_domain: int = 4, max_global: int = 16) -> None:
        self._max_per_domain = max(1, max_per_domain)
        self._max_global = max(1, max_global)
        self._global_sem = asyncio.Semaphore(self._max_global)
        self._domain_sems: dict[str, asyncio.Semaphore] = {}
        self._active_per_domain: dict[str, int] = {}

    @property
    def max_per_domain(self) -> int:
        return self._max_per_domain

    @property
    def max_global(self) -> int:
        return self._max_global

    def _domain_for(self, url: str) -> str:
        return (urlparse(url).hostname or "").lower()

    def _get_domain_sem(self, domain: str) -> asyncio.Semaphore:
        if domain not in self._domain_sems:
            self._domain_sems[domain] = asyncio.Semaphore(self._max_per_domain)
        return self._domain_sems[domain]

    async def acquire(self, url: str) -> tuple[str, asyncio.Semaphore]:
        """Acquire both global and domain semaphores.

        Returns ``(domain, domain_semaphore)`` so the caller can release later.
        """
        domain = self._domain_for(url)
        domain_sem = self._get_domain_sem(domain)

        # Check if domain is at capacity before acquiring global
        domain_active = self._active_per_domain.get(domain, 0)
        at_domain_limit = domain_active >= self._max_per_domain

        await self._global_sem.acquire()
        await domain_sem.acquire()

        self._active_per_domain[domain] = domain_active + 1
        return domain, domain_sem, at_domain_limit

    def release(self, domain: str, domain_sem: asyncio.Semaphore) -> None:
        """Release both domain and global semaphores."""
        domain_sem.release()
        self._global_sem.release()
        current = self._active_per_domain.get(domain, 0)
        if current > 0:
            self._active_per_domain[domain] = current - 1

    def active_count(self, domain: str) -> int:
        """Return the number of in-flight requests for a domain."""
        return self._active_per_domain.get(domain, 0)

    def active_count_global(self) -> int:
        """Return total in-flight requests across all domains."""
        return sum(self._active_per_domain.values())


class NativeAsyncFetchRuntime:
    """CLM-owned async fetch runtime with per-domain concurrency pool."""

    name: str = "native_async"

    def __init__(
        self,
        max_per_domain: int = 4,
        max_global: int = 16,
    ) -> None:
        self._pool = DomainConcurrencyPool(
            max_per_domain=max_per_domain,
            max_global=max_global,
        )

    @property
    def pool(self) -> DomainConcurrencyPool:
        return self._pool

    async def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        """Single async fetch with proxy retry and concurrency pool."""
        retry_cfg = _RetryConfig.from_proxy_config(request.proxy_config)
        transport = _transport_for(request)
        events: list[RuntimeEvent] = [
            RuntimeEvent(
                type="fetch_start",
                message="native async fetch started",
                data={
                    "transport": transport,
                    "method": request.method,
                    "url": request.url,
                    "proxy": redact_proxy_url(_proxy_url_for(request)),
                    "max_proxy_attempts": retry_cfg.max_attempts,
                },
            )
        ]

        # Acquire concurrency pool
        domain, domain_sem, at_limit = await self._pool.acquire(request.url)
        events.append(
            RuntimeEvent(
                type="pool_acquired",
                message=f"concurrency slot acquired for {domain}",
                data={
                    "domain": domain,
                    "active_per_domain": self._pool.active_count(domain),
                    "active_global": self._pool.active_count_global(),
                    "was_at_domain_limit": at_limit,
                },
            )
        )
        if at_limit:
            events.append(
                RuntimeEvent(
                    type="pool_backpressure",
                    message=f"domain {domain} was at concurrency limit",
                    data={
                        "domain": domain,
                        "max_per_domain": self._pool.max_per_domain,
                    },
                )
            )

        try:
            return await self._fetch_with_retry(request, retry_cfg, transport, events, domain)
        finally:
            self._pool.release(domain, domain_sem)
            events.append(
                RuntimeEvent(
                    type="pool_released",
                    message=f"concurrency slot released for {domain}",
                    data={
                        "domain": domain,
                        "active_per_domain": self._pool.active_count(domain),
                        "active_global": self._pool.active_count_global(),
                    },
                )
            )

    async def fetch_many(
        self,
        requests: list[RuntimeRequest],
        *,
        rate_limiter: Any | None = None,
    ) -> list[RuntimeResponse]:
        """Concurrent batch fetch with per-domain backpressure.

        Each request runs through the concurrency pool.  An optional
        ``rate_limiter`` (``DomainRateLimiter``-like) enforces per-domain
        delays via ``asyncio.sleep`` instead of blocking ``time.sleep``.
        """
        batch_events: list[RuntimeEvent] = [
            RuntimeEvent(
                type="fetch_many_start",
                message=f"batch fetch started: {len(requests)} requests",
                data={
                    "count": len(requests),
                    "max_per_domain": self._pool.max_per_domain,
                    "max_global": self._pool.max_global,
                },
            )
        ]

        async def _one(req: RuntimeRequest) -> RuntimeResponse:
            if rate_limiter is not None:
                await self._async_before_request(req.url, rate_limiter)
            return await self.fetch(req)

        results = await asyncio.gather(
            *(_one(r) for r in requests),
            return_exceptions=True,
        )

        responses: list[RuntimeResponse] = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                responses.append(
                    RuntimeResponse.failure(
                        final_url=requests[i].url,
                        error=f"{type(result).__name__}: {result}",
                        engine=self.name,
                        events=list(batch_events),
                    )
                )
            else:
                result.runtime_events[:0] = batch_events
                responses.append(result)

        complete_event = RuntimeEvent(
            type="fetch_many_complete",
            message=f"batch fetch completed: {len(responses)} responses",
            data={
                "count": len(responses),
                "ok_count": sum(1 for r in responses if r.ok),
                "fail_count": sum(1 for r in responses if not r.ok),
            },
        )
        for resp in responses:
            resp.runtime_events.append(complete_event)

        return responses

    async def _fetch_with_retry(
        self,
        request: RuntimeRequest,
        retry_cfg: _RetryConfig,
        transport: str,
        events: list[RuntimeEvent],
        domain: str,
    ) -> RuntimeResponse:
        """Execute fetch with proxy retry loop."""
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
                response = await self._do_fetch_async(request, transport, proxy_url)
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
                break
            except Exception as exc:
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

            # Success
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
            runtime_response.engine_result["engine"] = self.name
            runtime_response.runtime_events.append(
                RuntimeEvent(
                    type="fetch_complete",
                    message="native async fetch completed",
                    data={
                        "transport": transport,
                        "status_code": runtime_response.status_code,
                        "final_url": runtime_response.final_url,
                        "body_bytes": len(runtime_response.body),
                        "proxy_attempts": attempt + 1,
                        "domain": domain,
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

    async def _do_fetch_async(
        self,
        request: RuntimeRequest,
        transport: str,
        proxy_url: str,
    ) -> Any:
        """Dispatch to the appropriate transport asynchronously."""
        if transport == "curl_cffi":
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._fetch_curl_cffi_sync, request, proxy_url
            )
        return await self._fetch_httpx_async(request, proxy_url)

    async def _fetch_httpx_async(
        self, request: RuntimeRequest, proxy_url: str = ""
    ) -> httpx.Response:
        if not proxy_url:
            proxy_url = _proxy_url_for(request) or ""
        timeout = max(request.timeout_ms / 1000, 1.0)
        client_kwargs: dict[str, Any] = {
            "follow_redirects": True,
            "timeout": httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            "headers": dict(request.headers),
            "cookies": dict(request.cookies),
        }
        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        async with httpx.AsyncClient(**client_kwargs) as client:
            return await client.request(
                request.method,
                request.url,
                params=request.params or None,
                content=request.data if request.json is None else None,
                json=request.json,
            )

    def _fetch_curl_cffi_sync(
        self, request: RuntimeRequest, proxy_url: str = ""
    ) -> Any:
        """Synchronous curl_cffi fetch for use in executor."""
        import curl_cffi.requests as curl_requests

        if not proxy_url:
            proxy_url = _proxy_url_for(request)
        kwargs: dict[str, Any] = {
            "headers": dict(request.headers) or None,
            "cookies": dict(request.cookies) or None,
            "timeout": max(request.timeout_ms / 1000, 1.0),
            "allow_redirects": True,
            "impersonate": str(
                request.meta.get("impersonate") or DEFAULT_IMPERSONATE
            ),
        }
        if proxy_url:
            kwargs["proxy"] = proxy_url
        if request.params:
            kwargs["params"] = request.params
        if request.json is not None:
            kwargs["json"] = request.json
        elif request.data is not None:
            kwargs["data"] = request.data

        clean_kwargs = {
            key: value for key, value in kwargs.items() if value is not None
        }
        return curl_requests.request(request.method, request.url, **clean_kwargs)

    async def _async_before_request(self, url: str, limiter: Any) -> None:
        """Async equivalent of DomainRateLimiter.before_request().

        Calls limiter.policy.decide(url) to compute the delay, then sleeps
        with ``asyncio.sleep`` instead of blocking ``time.sleep``.
        """
        decision = limiter.policy.decide(url)
        sleep_for = limiter._compute_sleep(decision)
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)
