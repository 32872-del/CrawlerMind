"""Stress and metrics tests for async fetch pool.

Covers SCRAPLING-ABSORB-1G / CAP-1.3 / CAP-3.3 / CAP-3.5 acceptance:
- 1,000 URL fetch simulation
- Per-domain concurrency limits
- Retry/backoff event counts
- Proxy failures and recovery
- Aggregate AsyncFetchMetrics report
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from autonomous_crawler.runtime.native_async import (
    AsyncFetchMetrics,
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
    content: bytes = b"<html>OK</html>",
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.url = url
    resp.headers = {"Content-Type": "text/html"}
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


def _make_urls(
    n: int,
    *,
    domains: list[str] | None = None,
) -> list[str]:
    """Generate n URLs spread across domains."""
    if domains is None:
        domains = [f"domain{i}.example.com" for i in range(10)]
    urls = []
    for i in range(n):
        domain = domains[i % len(domains)]
        urls.append(f"https://{domain}/page/{i}")
    return urls


# ---------------------------------------------------------------------------
# Tests: 1000 URL fetch simulation
# ---------------------------------------------------------------------------

class TestThousandUrlSimulation(unittest.IsolatedAsyncioTestCase):
    """Simulate 1,000 URL fetches with mocked httpx."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_1000_urls_all_succeed(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime(max_per_domain=4, max_global=16)
        urls = _make_urls(1000)
        requests = [_make_request(u) for u in urls]

        import time
        start = time.monotonic()
        responses = await runtime.fetch_many(requests)
        elapsed = time.monotonic() - start

        self.assertEqual(len(responses), 1000)
        ok_count = sum(1 for r in responses if r.ok)
        self.assertEqual(ok_count, 1000)

        metrics = AsyncFetchMetrics.from_responses(responses)
        self.assertEqual(metrics.total, 1000)
        self.assertEqual(metrics.ok_count, 1000)
        self.assertEqual(metrics.fail_count, 0)

        # Verify metrics report is inspectable
        report = metrics.to_dict()
        self.assertEqual(report["total"], 1000)
        self.assertEqual(report["ok_count"], 1000)
        self.assertIsInstance(report["domains"], dict)
        self.assertIsInstance(report["event_type_counts"], dict)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_1000_urls_metrics_has_domain_counts(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime(max_per_domain=4, max_global=16)
        urls = _make_urls(100, domains=["a.com", "b.com", "c.com"])
        requests = [_make_request(u) for u in urls]
        responses = await runtime.fetch_many(requests)

        metrics = AsyncFetchMetrics.from_responses(responses)
        # 100 URLs across 3 domains
        self.assertEqual(sum(metrics.domains.values()), 100)
        self.assertTrue(all(d in metrics.domains for d in ["a.com", "b.com", "c.com"]))


# ---------------------------------------------------------------------------
# Tests: per-domain concurrency limits
# ---------------------------------------------------------------------------

class TestConcurrencyLimits(unittest.IsolatedAsyncioTestCase):
    """Verify per-domain concurrency is bounded."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_max_concurrency_observed(self, mock_client_cls: MagicMock) -> None:
        # Slow fetch to observe concurrency
        active = {"count": 0, "max": 0}
        gate = asyncio.Event()

        async def _slow(*args, **kwargs):
            active["count"] += 1
            active["max"] = max(active["max"], active["count"])
            await gate.wait()
            active["count"] -= 1
            return _httpx_response()

        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=_slow)

        runtime = NativeAsyncFetchRuntime(max_per_domain=3, max_global=10)
        # 6 URLs on same domain, max_per_domain=3
        requests = [_make_request(f"https://example.com/{i}") for i in range(6)]
        task = asyncio.create_task(runtime.fetch_many(requests))

        # Let tasks start and block
        await asyncio.sleep(0.05)
        gate.set()
        responses = await task

        self.assertEqual(len(responses), 6)
        # Max concurrency should be at most 3 (the per-domain limit)
        self.assertLessEqual(active["max"], 3)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_different_domains_parallel(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime(max_per_domain=2, max_global=20)
        # 5 different domains, 4 URLs each = 20 total
        domains = [f"site{i}.com" for i in range(5)]
        urls = []
        for d in domains:
            urls.extend([f"https://{d}/p{i}" for i in range(4)])
        requests = [_make_request(u) for u in urls]

        responses = await runtime.fetch_many(requests)

        metrics = AsyncFetchMetrics.from_responses(responses)
        self.assertEqual(metrics.total, 20)
        self.assertEqual(metrics.ok_count, 20)
        # All 5 domains should have requests
        self.assertEqual(len(metrics.domains), 5)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_backpressure_events_in_metrics(self, mock_client_cls: MagicMock) -> None:
        # Slow fetch so concurrency builds up
        gate = asyncio.Event()

        async def _slow(*args, **kwargs):
            await gate.wait()
            return _httpx_response()

        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=_slow)

        runtime = NativeAsyncFetchRuntime(max_per_domain=2, max_global=10)
        # 4 URLs on same domain, max_per_domain=2 → 2 will see backpressure
        requests = [_make_request(f"https://example.com/{i}") for i in range(4)]
        task = asyncio.create_task(runtime.fetch_many(requests))

        await asyncio.sleep(0.05)
        gate.set()
        responses = await task

        metrics = AsyncFetchMetrics.from_responses(responses)
        # At least 2 of the 4 requests should have seen backpressure
        self.assertGreaterEqual(metrics.backpressure_events, 2)


# ---------------------------------------------------------------------------
# Tests: retry/backoff event counts
# ---------------------------------------------------------------------------

class TestRetryBackoffCounts(unittest.IsolatedAsyncioTestCase):
    """Verify retry and backoff events are counted correctly."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_retry_events_counted(self, mock_client_cls: MagicMock) -> None:
        fail_count = 0

        async def _fail_then_succeed(*args, **kwargs):
            nonlocal fail_count
            fail_count += 1
            if fail_count <= 2:
                raise ConnectionError("refused")
            return _httpx_response()

        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=_fail_then_succeed)

        runtime = NativeAsyncFetchRuntime()
        requests = [
            _make_request(
                f"https://example.com/{i}",
                proxy_url="http://u:p@proxy:8080",
                max_attempts=3,
            )
            for i in range(3)
        ]
        responses = await runtime.fetch_many(requests)

        metrics = AsyncFetchMetrics.from_responses(responses)
        # 3 requests, first 2 fail once then succeed, 3rd succeeds on first try
        # Total proxy attempts: 2 (fail) + 2 (success after retry) + 1 (direct success) = 5
        self.assertGreaterEqual(metrics.proxy_attempts_total, 3)
        self.assertGreaterEqual(metrics.proxy_failures, 2)
        self.assertGreaterEqual(metrics.proxy_retries, 2)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_all_fail_no_success_events(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=ConnectionError("refused"))

        runtime = NativeAsyncFetchRuntime()
        requests = [
            _make_request(
                f"https://example.com/{i}",
                proxy_url="http://u:p@proxy:8080",
                max_attempts=2,
            )
            for i in range(5)
        ]
        responses = await runtime.fetch_many(requests)

        metrics = AsyncFetchMetrics.from_responses(responses)
        self.assertEqual(metrics.fail_count, 5)
        self.assertEqual(metrics.proxy_successes, 0)
        self.assertEqual(metrics.proxy_failures, 10)  # 5 requests * 2 attempts
        self.assertEqual(metrics.proxy_retries, 5)    # 5 requests * 1 retry


# ---------------------------------------------------------------------------
# Tests: proxy failures and recovery
# ---------------------------------------------------------------------------

class TestProxyFailureRecovery(unittest.IsolatedAsyncioTestCase):
    """Proxy failure and recovery in batch context."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_partial_proxy_failure_recovery(self, mock_client_cls: MagicMock) -> None:
        """Some requests fail on proxy, others succeed — metrics reflect both."""
        call_idx = 0

        async def _alternating(*args, **kwargs):
            nonlocal call_idx
            call_idx += 1
            # Odd calls fail, even calls succeed
            if call_idx % 2 == 1:
                raise ConnectionError("proxy down")
            return _httpx_response()

        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=_alternating)

        pool_provider = MagicMock()
        pool_provider.select.return_value = MagicMock(
            proxy_url="http://alt:cred@proxy-b:9090"
        )
        pool_provider.report_result = MagicMock()

        health_store = MagicMock()
        health_store.record_failure = MagicMock()
        health_store.record_success = MagicMock()

        runtime = NativeAsyncFetchRuntime()
        requests = [
            _make_request(
                f"https://example.com/{i}",
                proxy_url="http://u:p@proxy-a:8080",
                max_attempts=2,
                pool_provider=pool_provider,
                health_store=health_store,
            )
            for i in range(10)
        ]
        responses = await runtime.fetch_many(requests)

        metrics = AsyncFetchMetrics.from_responses(responses)
        # With retry, alternating failures should recover
        self.assertGreater(metrics.proxy_successes, 0)
        self.assertGreater(metrics.proxy_failures, 0)
        self.assertEqual(metrics.total, 10)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_health_store_called_in_batch(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=ConnectionError("refused"))

        health_store = MagicMock()
        health_store.record_failure = MagicMock()
        health_store.record_success = MagicMock()

        runtime = NativeAsyncFetchRuntime()
        requests = [
            _make_request(
                f"https://example.com/{i}",
                proxy_url="http://u:p@proxy:8080",
                max_attempts=1,
                health_store=health_store,
            )
            for i in range(5)
        ]
        await runtime.fetch_many(requests)

        # 5 requests, each fails once → 5 record_failure calls
        self.assertEqual(health_store.record_failure.call_count, 5)
        self.assertEqual(health_store.record_success.call_count, 0)


# ---------------------------------------------------------------------------
# Tests: AsyncFetchMetrics report object
# ---------------------------------------------------------------------------

class TestAsyncFetchMetrics(unittest.TestCase):
    """AsyncFetchMetrics report object."""

    def test_from_empty_responses(self) -> None:
        metrics = AsyncFetchMetrics.from_responses([])
        self.assertEqual(metrics.total, 0)
        self.assertEqual(metrics.ok_count, 0)
        self.assertEqual(metrics.fail_count, 0)

    def test_from_responses_counts_status_codes(self) -> None:
        from autonomous_crawler.runtime.models import RuntimeResponse

        responses = [
            RuntimeResponse(ok=True, status_code=200),
            RuntimeResponse(ok=True, status_code=200),
            RuntimeResponse(ok=False, status_code=404),
            RuntimeResponse(ok=False, status_code=500),
        ]
        metrics = AsyncFetchMetrics.from_responses(responses)
        self.assertEqual(metrics.status_codes[200], 2)
        self.assertEqual(metrics.status_codes[404], 1)
        self.assertEqual(metrics.status_codes[500], 1)

    def test_to_dict_structure(self) -> None:
        metrics = AsyncFetchMetrics(total=10, ok_count=8, fail_count=2)
        d = metrics.to_dict()
        self.assertIn("total", d)
        self.assertIn("ok_count", d)
        self.assertIn("fail_count", d)
        self.assertIn("domains", d)
        self.assertIn("status_codes", d)
        self.assertIn("proxy_attempts_total", d)
        self.assertIn("proxy_failures", d)
        self.assertIn("proxy_successes", d)
        self.assertIn("proxy_retries", d)
        self.assertIn("backpressure_events", d)
        self.assertIn("event_type_counts", d)
        self.assertIn("errors", d)
        self.assertIn("max_concurrency_per_domain", d)

    def test_errors_capped_at_100(self) -> None:
        from autonomous_crawler.runtime.models import RuntimeResponse

        responses = [
            RuntimeResponse(ok=False, error=f"error {i}")
            for i in range(200)
        ]
        metrics = AsyncFetchMetrics.from_responses(responses)
        self.assertEqual(len(metrics.errors), 100)

    def test_max_concurrency_tracked(self) -> None:
        from autonomous_crawler.runtime.models import RuntimeResponse, RuntimeEvent

        # Simulate responses with pool_acquired events
        events = [
            RuntimeEvent(type="pool_acquired", data={"domain": "a.com", "active_per_domain": 2}),
            RuntimeEvent(type="pool_acquired", data={"domain": "a.com", "active_per_domain": 4}),
            RuntimeEvent(type="pool_acquired", data={"domain": "b.com", "active_per_domain": 1}),
        ]
        responses = [
            RuntimeResponse(ok=True, runtime_events=[e])
            for e in events
        ]
        metrics = AsyncFetchMetrics.from_responses(responses)
        self.assertEqual(metrics.max_concurrency_per_domain["a.com"], 4)
        self.assertEqual(metrics.max_concurrency_per_domain["b.com"], 1)


# ---------------------------------------------------------------------------
# Tests: throughput characteristics
# ---------------------------------------------------------------------------

class TestThroughputCharacteristics(unittest.IsolatedAsyncioTestCase):
    """Verify throughput characteristics of the async pool."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_fetch_many_completes_within_timeout(self, mock_client_cls: MagicMock) -> None:
        """100 URLs should complete well under 10 seconds with mocked responses."""
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime(max_per_domain=4, max_global=16)
        requests = [_make_request(u) for u in _make_urls(100)]

        import time
        start = time.monotonic()
        responses = await runtime.fetch_many(requests)
        elapsed = time.monotonic() - start

        self.assertEqual(len(responses), 100)
        self.assertLess(elapsed, 10.0)  # Should be fast with mocks

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_global_limit_enforced(self, mock_client_cls: MagicMock) -> None:
        """Global concurrency limit is enforced across domains."""
        active = {"count": 0, "max": 0}
        gate = asyncio.Event()

        async def _track(*args, **kwargs):
            active["count"] += 1
            active["max"] = max(active["max"], active["count"])
            await gate.wait()
            active["count"] -= 1
            return _httpx_response()

        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=_track)

        runtime = NativeAsyncFetchRuntime(max_per_domain=10, max_global=5)
        # 20 URLs across different domains, global limit=5
        requests = [_make_request(f"https://site{i}.com/") for i in range(20)]
        task = asyncio.create_task(runtime.fetch_many(requests))

        await asyncio.sleep(0.05)
        gate.set()
        responses = await task

        self.assertEqual(len(responses), 20)
        # Global max should not exceed 5
        self.assertLessEqual(active["max"], 5)


if __name__ == "__main__":
    unittest.main()
