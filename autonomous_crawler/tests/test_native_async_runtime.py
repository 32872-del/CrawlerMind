"""Tests for CLM-native async fetch runtime with per-domain concurrency.

Covers SCRAPLING-ABSORB-1F / CAP-1.3 / CAP-3.3 acceptance criteria:
- Async fetch returns RuntimeResponse
- Batch fetch with concurrency pool
- Per-domain concurrency limits enforced
- Backpressure events emitted
- Proxy retry works in async context
- Credentials never leak in async events/responses
- Rate limiter integration with async sleep
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from autonomous_crawler.runtime.native_async import (
    DomainConcurrencyPool,
    NativeAsyncFetchRuntime,
)
from autonomous_crawler.runtime.models import RuntimeRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _httpx_response(
    *,
    status_code: int = 200,
    url: str = "https://example.com/",
    content: bytes = b"<html><body>OK</body></html>",
    headers: dict[str, str] | None = None,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.url = url
    resp.headers = headers or {"Content-Type": "text/html"}
    resp.cookies = {}
    resp.content = content
    resp.text = content.decode("utf-8", errors="replace")
    resp.http_version = "HTTP/2"
    return resp


def _make_request(
    url: str = "https://example.com/",
    *,
    proxy_url: str = "",
    max_attempts: int = 1,
    pool_provider: object | None = None,
    health_store: object | None = None,
) -> RuntimeRequest:
    proxy_config: dict = {}
    if proxy_url:
        proxy_config["proxy"] = proxy_url
    if max_attempts > 1:
        proxy_config["retry_on_proxy_failure"] = True
        proxy_config["max_proxy_attempts"] = max_attempts
    if pool_provider is not None:
        proxy_config["pool_provider"] = pool_provider
    if health_store is not None:
        proxy_config["health_store"] = health_store
    return RuntimeRequest(url=url, proxy_config=proxy_config)


def _all_event_types(response) -> list[str]:
    return [e.type for e in response.runtime_events]


def _all_event_dicts(response) -> list[dict]:
    return [e.to_dict() for e in response.runtime_events]


# ---------------------------------------------------------------------------
# Tests: basic async fetch
# ---------------------------------------------------------------------------

class TestAsyncFetchBasic(unittest.IsolatedAsyncioTestCase):
    """Single async fetch returns a valid RuntimeResponse."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_single_fetch_returns_ok(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime()
        response = await runtime.fetch(_make_request())

        self.assertTrue(response.ok)
        self.assertEqual(response.status_code, 200)
        self.assertIn("OK", response.html)
        self.assertEqual(response.engine_result["engine"], "native_async")

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_fetch_emits_start_and_complete_events(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime()
        response = await runtime.fetch(_make_request())

        event_types = _all_event_types(response)
        self.assertIn("fetch_start", event_types)
        self.assertIn("fetch_complete", event_types)
        self.assertIn("pool_acquired", event_types)
        self.assertIn("pool_released", event_types)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_fetch_with_proxy(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime()
        response = await runtime.fetch(
            _make_request(proxy_url="http://user:pass@proxy:8080")
        )

        self.assertTrue(response.ok)
        self.assertTrue(response.proxy_trace.selected)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_fetch_error_returns_failure(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=ValueError("bad request"))

        runtime = NativeAsyncFetchRuntime()
        response = await runtime.fetch(_make_request())

        self.assertFalse(response.ok)
        self.assertIn("ValueError", response.error)


# ---------------------------------------------------------------------------
# Tests: fetch_many batch
# ---------------------------------------------------------------------------

class TestAsyncFetchMany(unittest.IsolatedAsyncioTestCase):
    """Batch fetch returns correct number of responses."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_fetch_many_returns_all_responses(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime()
        requests = [_make_request(f"https://example.com/{i}") for i in range(5)]
        responses = await runtime.fetch_many(requests)

        self.assertEqual(len(responses), 5)
        for resp in responses:
            self.assertTrue(resp.ok)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_fetch_many_emits_batch_events(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime()
        requests = [_make_request(f"https://example.com/{i}") for i in range(3)]
        responses = await runtime.fetch_many(requests)

        for resp in responses:
            event_types = _all_event_types(resp)
            self.assertIn("fetch_many_start", event_types)
            self.assertIn("fetch_many_complete", event_types)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_fetch_many_partial_failure(self, mock_client_cls: MagicMock) -> None:
        call_count = 0

        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ConnectionError("refused")
            return _httpx_response()

        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=_side_effect)

        runtime = NativeAsyncFetchRuntime()
        requests = [_make_request(f"https://example.com/{i}") for i in range(3)]
        responses = await runtime.fetch_many(requests)

        self.assertEqual(len(responses), 3)
        ok_count = sum(1 for r in responses if r.ok)
        fail_count = sum(1 for r in responses if not r.ok)
        self.assertEqual(ok_count, 2)
        self.assertEqual(fail_count, 1)


# ---------------------------------------------------------------------------
# Tests: DomainConcurrencyPool
# ---------------------------------------------------------------------------

class TestDomainConcurrencyPool(unittest.IsolatedAsyncioTestCase):
    """Per-domain semaphore limits concurrency."""

    async def test_acquire_release_cycle(self) -> None:
        pool = DomainConcurrencyPool(max_per_domain=2, max_global=10)
        domain, sem, at_limit = await pool.acquire("https://example.com/")
        self.assertEqual(domain, "example.com")
        self.assertFalse(at_limit)
        self.assertEqual(pool.active_count("example.com"), 1)
        pool.release(domain, sem)
        self.assertEqual(pool.active_count("example.com"), 0)

    async def test_per_domain_limit_reached(self) -> None:
        pool = DomainConcurrencyPool(max_per_domain=2, max_global=10)

        # First two acquires succeed without blocking
        d1, s1, at1 = await pool.acquire("https://example.com/a")
        self.assertFalse(at1)
        d2, s2, at2 = await pool.acquire("https://example.com/b")
        self.assertFalse(at2)

        # Third acquire will block because domain semaphore is full.
        # Use a task with timeout to verify it blocks.
        task = asyncio.create_task(pool.acquire("https://example.com/c"))
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(task, timeout=0.05)

        # Release one slot — now third acquire can proceed
        pool.release(d1, s1)
        self.assertEqual(pool.active_count("example.com"), 1)

        d3, s3, at3 = await pool.acquire("https://example.com/c")
        # After releasing d1, domain has 1 active (d2) which is below max=2
        self.assertFalse(at3)
        pool.release(d2, s2)
        pool.release(d3, s3)

    async def test_different_domains_independent(self) -> None:
        pool = DomainConcurrencyPool(max_per_domain=1, max_global=10)

        d1, s1, _ = await pool.acquire("https://alpha.com/")
        d2, s2, _ = await pool.acquire("https://beta.com/")

        self.assertEqual(d1, "alpha.com")
        self.assertEqual(d2, "beta.com")
        self.assertEqual(pool.active_count("alpha.com"), 1)
        self.assertEqual(pool.active_count("beta.com"), 1)

        pool.release(d1, s1)
        pool.release(d2, s2)

    async def test_global_limit_reached(self) -> None:
        pool = DomainConcurrencyPool(max_per_domain=10, max_global=2)

        d1, s1, _ = await pool.acquire("https://a.com/")
        d2, s2, _ = await pool.acquire("https://b.com/")

        self.assertEqual(pool.active_count_global(), 2)

        # Third acquire should block — test with timeout
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(
                pool.acquire("https://c.com/"),
                timeout=0.05,
            )

        pool.release(d1, s1)
        pool.release(d2, s2)

    async def test_properties(self) -> None:
        pool = DomainConcurrencyPool(max_per_domain=3, max_global=7)
        self.assertEqual(pool.max_per_domain, 3)
        self.assertEqual(pool.max_global, 7)


# ---------------------------------------------------------------------------
# Tests: backpressure events
# ---------------------------------------------------------------------------

class TestBackpressureEvents(unittest.IsolatedAsyncioTestCase):
    """Structured events emitted on concurrency limits."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_backpressure_event_when_at_limit(self, mock_client_cls: MagicMock) -> None:
        # Use a gate so the first request stays in-flight while the second arrives
        gate = asyncio.Event()

        async def _slow_fetch(*args, **kwargs):
            await gate.wait()
            return _httpx_response()

        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=_slow_fetch)

        runtime = NativeAsyncFetchRuntime(max_per_domain=1, max_global=10)

        # Start both concurrently — first holds the slot, second sees at_limit
        task1 = asyncio.create_task(runtime.fetch(_make_request("https://example.com/")))
        # Let task1 acquire the slot
        await asyncio.sleep(0.01)
        task2 = asyncio.create_task(runtime.fetch(_make_request("https://example.com/")))
        await asyncio.sleep(0.01)

        # Release both
        gate.set()
        r1 = await task1
        r2 = await task2

        # r2 should have backpressure event because domain was at limit (1)
        event_types = _all_event_types(r2)
        self.assertIn("pool_backpressure", event_types)

        backpressure_events = [
            e for e in r2.runtime_events if e.type == "pool_backpressure"
        ]
        self.assertEqual(len(backpressure_events), 1)
        self.assertEqual(backpressure_events[0].data["domain"], "example.com")
        self.assertEqual(backpressure_events[0].data["max_per_domain"], 1)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_pool_events_in_response(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime()
        response = await runtime.fetch(_make_request())

        pool_events = [
            e for e in response.runtime_events
            if e.type in ("pool_acquired", "pool_released")
        ]
        self.assertEqual(len(pool_events), 2)
        self.assertEqual(pool_events[0].type, "pool_acquired")
        self.assertEqual(pool_events[1].type, "pool_released")


# ---------------------------------------------------------------------------
# Tests: async proxy retry
# ---------------------------------------------------------------------------

class TestAsyncProxyRetry(unittest.IsolatedAsyncioTestCase):
    """Proxy retry works in async context."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_first_fail_second_success(self, mock_client_cls: MagicMock) -> None:
        pool_provider = MagicMock()
        pool_provider.select.return_value = MagicMock(
            proxy_url="http://alt:cred@proxy-b:9090"
        )
        pool_provider.report_result = MagicMock()

        health_store = MagicMock()
        health_store.record_failure = MagicMock()
        health_store.record_success = MagicMock()

        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(
            side_effect=[
                ConnectionError("proxy-a refused"),
                _httpx_response(),
            ]
        )

        runtime = NativeAsyncFetchRuntime()
        response = await runtime.fetch(
            _make_request(
                proxy_url="http://user:pass@proxy-a:8080",
                max_attempts=2,
                pool_provider=pool_provider,
                health_store=health_store,
            )
        )

        self.assertTrue(response.ok)
        event_types = _all_event_types(response)
        self.assertIn("proxy_failure_recorded", event_types)
        self.assertIn("proxy_retry", event_types)
        self.assertIn("proxy_success_recorded", event_types)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_all_attempts_fail(self, mock_client_cls: MagicMock) -> None:
        pool_provider = MagicMock()
        pool_provider.select.return_value = MagicMock(
            proxy_url="http://alt:cred@proxy-b:9090"
        )
        pool_provider.report_result = MagicMock()

        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(
            side_effect=[
                ConnectionError("a"),
                ConnectionError("b"),
            ]
        )

        runtime = NativeAsyncFetchRuntime()
        response = await runtime.fetch(
            _make_request(
                proxy_url="http://user:pass@proxy-a:8080",
                max_attempts=2,
                pool_provider=pool_provider,
            )
        )

        self.assertFalse(response.ok)
        self.assertIn("all 2 proxy attempts failed", response.error)


# ---------------------------------------------------------------------------
# Tests: credential safety
# ---------------------------------------------------------------------------

class TestAsyncCredentialSafety(unittest.IsolatedAsyncioTestCase):
    """Credentials never leak in async events or responses."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_credentials_not_in_events(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime()
        response = await runtime.fetch(
            _make_request(proxy_url="http://admin:topsecret@proxy:8080")
        )

        for event_dict in _all_event_dicts(response):
            text = str(event_dict)
            self.assertNotIn("admin", text)
            self.assertNotIn("topsecret", text)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_credentials_not_in_response_to_dict(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime()
        response = await runtime.fetch(
            _make_request(proxy_url="http://u:p@proxy:8080")
        )

        resp_dict = response.to_dict()
        text = str(resp_dict)
        self.assertNotIn("u:p@", text)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_credentials_not_in_error_response(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=ConnectionError("refused"))

        runtime = NativeAsyncFetchRuntime()
        response = await runtime.fetch(
            _make_request(
                proxy_url="http://admin:topsecret@proxy:8080",
                max_attempts=1,
            )
        )

        resp_dict = response.to_dict()
        text = str(resp_dict)
        self.assertNotIn("admin", text)
        self.assertNotIn("topsecret", text)


# ---------------------------------------------------------------------------
# Tests: rate limiter integration
# ---------------------------------------------------------------------------

class TestAsyncRateLimitIntegration(unittest.IsolatedAsyncioTestCase):
    """DomainRateLimiter integration with async sleep."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_rate_limiter_called_before_each_fetch(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        limiter = MagicMock()
        decision = MagicMock()
        decision.domain = "example.com"
        decision.delay_seconds = 1.0
        limiter.policy.decide.return_value = decision
        limiter._compute_sleep.return_value = 0.0  # No actual delay

        runtime = NativeAsyncFetchRuntime()
        requests = [_make_request(f"https://example.com/{i}") for i in range(3)]
        responses = await runtime.fetch_many(requests, rate_limiter=limiter)

        self.assertEqual(len(responses), 3)
        self.assertEqual(limiter.policy.decide.call_count, 3)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_fetch_many_without_rate_limiter(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime()
        requests = [_make_request(f"https://example.com/{i}") for i in range(2)]
        responses = await runtime.fetch_many(requests)

        self.assertEqual(len(responses), 2)
        for resp in responses:
            self.assertTrue(resp.ok)


# ---------------------------------------------------------------------------
# Tests: runtime protocol compatibility
# ---------------------------------------------------------------------------

class TestAsyncRuntimeProperties(unittest.IsolatedAsyncioTestCase):
    """Verify runtime metadata and properties."""

    def test_name_is_native_async(self) -> None:
        runtime = NativeAsyncFetchRuntime()
        self.assertEqual(runtime.name, "native_async")

    def test_pool_accessible(self) -> None:
        runtime = NativeAsyncFetchRuntime(max_per_domain=5, max_global=20)
        self.assertEqual(runtime.pool.max_per_domain, 5)
        self.assertEqual(runtime.pool.max_global, 20)


if __name__ == "__main__":
    unittest.main()
