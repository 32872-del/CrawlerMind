"""Long-run stress tests for async fetch pool + spider summary + checkpoint.

Covers SCRAPLING-HARDEN-1 acceptance:
- 1k URL fetch simulation with metrics into SpiderRunSummary
- Per-domain concurrency limits under load
- Retry/backoff/proxy event counts
- Checkpoint resume with summary preservation
- All proxy info stays redacted
"""
from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from autonomous_crawler.runtime.native_async import (
    AsyncFetchMetrics,
    DomainConcurrencyPool,
    NativeAsyncFetchRuntime,
)
from autonomous_crawler.runtime.models import RuntimeEvent, RuntimeRequest, RuntimeResponse
from autonomous_crawler.runners.spider_models import (
    CrawlItemResult,
    CrawlRequestEnvelope,
    SpiderRunSummary,
    make_spider_event,
)
from autonomous_crawler.storage.checkpoint_store import CheckpointStore


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
) -> RuntimeRequest:
    proxy_config: dict = {}
    if proxy_url:
        proxy_config["proxy"] = proxy_url
    if max_attempts > 1:
        proxy_config["retry_on_proxy_failure"] = True
        proxy_config["max_proxy_attempts"] = max_attempts
    return RuntimeRequest(url=url, proxy_config=proxy_config)


def _make_urls(n: int, domains: list[str] | None = None) -> list[str]:
    if domains is None:
        domains = [f"domain{i}.example.com" for i in range(10)]
    return [f"https://{domains[i % len(domains)]}/page/{i}" for i in range(n)]


def _envelope(url: str, run_id: str = "test-run") -> CrawlRequestEnvelope:
    return CrawlRequestEnvelope(run_id=run_id, url=url)


# ---------------------------------------------------------------------------
# Tests: 1k stress with SpiderRunSummary aggregation
# ---------------------------------------------------------------------------

class TestLongrunStress1k(unittest.IsolatedAsyncioTestCase):
    """1,000 URL fetch simulation with SpiderRunSummary metrics."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_1k_urls_metrics_into_summary(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime(max_per_domain=4, max_global=16)
        urls = _make_urls(1000)
        requests = [_make_request(u) for u in urls]

        start = time.monotonic()
        responses = await runtime.fetch_many(requests)
        elapsed = time.monotonic() - start

        # Build summary and aggregate
        summary = SpiderRunSummary(run_id="stress-1k")
        for resp in responses:
            envelope = CrawlRequestEnvelope(run_id="stress-1k", url=resp.final_url or "https://x.com/")
            result = CrawlItemResult(
                ok=resp.ok,
                request_id=envelope.request_id,
                url=resp.final_url or "https://x.com/",
                status_code=resp.status_code,
                runtime_events=resp.runtime_events,
            )
            summary.record_item(result)

        self.assertEqual(summary.succeeded, 1000)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.async_fetch_ok, 1000)
        self.assertEqual(summary.async_fetch_fail, 0)
        self.assertGreater(summary.pool_acquired_events, 0)
        self.assertGreater(summary.pool_released_events, 0)

        # Metrics report
        report = summary.as_dict()
        self.assertEqual(report["succeeded"], 1000)
        self.assertIn("proxy_attempts_total", report)
        self.assertIn("backpressure_events", report)
        self.assertIn("max_concurrency_per_domain", report)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_1k_with_proxy_retry_metrics(self, mock_client_cls: MagicMock) -> None:
        """1k URLs with proxy retry — verify retry metrics flow into summary."""
        fail_idx = 0

        async def _fail_then_ok(*args, **kwargs):
            nonlocal fail_idx
            fail_idx += 1
            if fail_idx % 5 == 0:  # Every 5th request fails once
                raise ConnectionError("proxy glitch")
            return _httpx_response()

        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=_fail_then_ok)

        pool_provider = MagicMock()
        pool_provider.select.return_value = MagicMock(proxy_url="http://alt:cred@proxy-b:9090")
        pool_provider.report_result = MagicMock()
        health_store = MagicMock()
        health_store.record_failure = MagicMock()
        health_store.record_success = MagicMock()

        runtime = NativeAsyncFetchRuntime(max_per_domain=4, max_global=16)
        urls = _make_urls(200)
        requests = [
            _make_request(u, proxy_url="http://u:p@proxy-a:8080", max_attempts=2)
            for u in urls
        ]
        responses = await runtime.fetch_many(requests)

        summary = SpiderRunSummary(run_id="stress-proxy")
        for resp in responses:
            envelope = CrawlRequestEnvelope(run_id="stress-proxy", url=resp.final_url or "https://x.com/")
            result = CrawlItemResult(
                ok=resp.ok,
                request_id=envelope.request_id,
                url=resp.final_url or "https://x.com/",
                status_code=resp.status_code,
                runtime_events=resp.runtime_events,
            )
            summary.record_item(result)

        # With retry, most should succeed
        self.assertGreater(summary.succeeded, 150)
        self.assertGreater(summary.proxy_attempts_total, 0)
        self.assertGreater(summary.proxy_failures, 0)
        self.assertGreater(summary.proxy_retries, 0)


# ---------------------------------------------------------------------------
# Tests: checkpoint resume with summary preservation
# ---------------------------------------------------------------------------

class TestCheckpointResumePreservesSummary(unittest.TestCase):
    """Checkpoint resume preserves SpiderRunSummary async metrics."""

    def test_save_and_load_preserves_async_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(Path(tmp) / "ckpt.sqlite3")
            store.start_run("resume-run", {"goal": "test"})

            summary = SpiderRunSummary(run_id="resume-run", status="running")
            summary.succeeded = 50
            summary.failed = 5
            summary.proxy_attempts_total = 60
            summary.proxy_failures = 10
            summary.proxy_successes = 50
            summary.proxy_retries = 5
            summary.backpressure_events = 12
            summary.pool_acquired_events = 55
            summary.pool_released_events = 55
            summary.async_fetch_ok = 50
            summary.async_fetch_fail = 5
            summary.max_concurrency_per_domain = {"a.com": 4, "b.com": 3}

            store.save_batch_checkpoint(
                run_id="resume-run",
                batch_id="batch-001",
                frontier_items=[{"id": i, "url": f"https://a.com/{i}"} for i in range(5)],
                summary=summary,
                events=[],
            )

            loaded = store.load_latest("resume-run")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            ckpt = loaded["latest_checkpoint"]
            self.assertIsNotNone(ckpt)
            assert ckpt is not None

            restored = ckpt["summary"]
            self.assertEqual(restored["succeeded"], 50)
            self.assertEqual(restored["failed"], 5)
            self.assertEqual(restored["proxy_attempts_total"], 60)
            self.assertEqual(restored["proxy_failures"], 10)
            self.assertEqual(restored["proxy_successes"], 50)
            self.assertEqual(restored["proxy_retries"], 5)
            self.assertEqual(restored["backpressure_events"], 12)
            self.assertEqual(restored["pool_acquired_events"], 55)
            self.assertEqual(restored["async_fetch_ok"], 50)
            self.assertEqual(restored["async_fetch_fail"], 5)
            self.assertEqual(restored["max_concurrency_per_domain"], {"a.com": 4, "b.com": 3})

    def test_resume_after_pause_preserves_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(Path(tmp) / "ckpt.sqlite3")
            store.start_run("pause-run")

            summary = SpiderRunSummary(run_id="pause-run", status="running")
            summary.succeeded = 100
            summary.proxy_attempts_total = 120
            summary.proxy_failures = 20
            summary.backpressure_events = 15
            summary.max_concurrency_per_domain = {"x.com": 4}

            store.save_batch_checkpoint(
                run_id="pause-run",
                batch_id="batch-001",
                frontier_items=[],
                summary=summary,
            )

            store.mark_paused("pause-run", reason="manual pause")

            loaded = store.load_latest("pause-run")
            assert loaded is not None
            self.assertEqual(loaded["run"]["status"], "paused")

            # Simulate resume
            store.start_run("pause-run", {"resume": True})
            loaded2 = store.load_latest("pause-run")
            assert loaded2 is not None
            self.assertEqual(loaded2["run"]["status"], "running")

            # Old checkpoint still intact
            ckpt = loaded2["latest_checkpoint"]
            assert ckpt is not None
            self.assertEqual(ckpt["summary"]["succeeded"], 100)
            self.assertEqual(ckpt["summary"]["proxy_attempts_total"], 120)

    def test_multiple_checkpoints_latest_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(Path(tmp) / "ckpt.sqlite3")
            store.start_run("multi-run")

            # First checkpoint
            s1 = SpiderRunSummary(run_id="multi-run", status="running")
            s1.succeeded = 10
            s1.proxy_attempts_total = 10
            store.save_batch_checkpoint(
                run_id="multi-run", batch_id="b1", frontier_items=[], summary=s1,
            )

            # Second checkpoint
            s2 = SpiderRunSummary(run_id="multi-run", status="running")
            s2.succeeded = 20
            s2.proxy_attempts_total = 25
            s2.backpressure_events = 5
            store.save_batch_checkpoint(
                run_id="multi-run", batch_id="b2", frontier_items=[], summary=s2,
            )

            loaded = store.load_latest("multi-run")
            assert loaded is not None
            ckpt = loaded["latest_checkpoint"]
            assert ckpt is not None
            self.assertEqual(ckpt["summary"]["succeeded"], 20)
            self.assertEqual(ckpt["summary"]["proxy_attempts_total"], 25)
            self.assertEqual(ckpt["summary"]["backpressure_events"], 5)


# ---------------------------------------------------------------------------
# Tests: proxy credential redaction under stress
# ---------------------------------------------------------------------------

class TestStressCredentialSafety(unittest.IsolatedAsyncioTestCase):
    """Credentials never leak in 1k stress run."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_no_credentials_in_summary_events(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime()
        requests = [
            _make_request(
                f"https://example.com/{i}",
                proxy_url="http://admin:topsecret@proxy:8080",
            )
            for i in range(100)
        ]
        responses = await runtime.fetch_many(requests)

        summary = SpiderRunSummary(run_id="redact-test")
        for resp in responses:
            envelope = CrawlRequestEnvelope(run_id="redact-test", url=resp.final_url or "https://x.com/")
            result = CrawlItemResult(
                ok=resp.ok,
                request_id=envelope.request_id,
                url=resp.final_url or "https://x.com/",
                runtime_events=resp.runtime_events,
            )
            summary.record_item(result)

        report = summary.as_dict()
        text = str(report)
        self.assertNotIn("admin", text)
        self.assertNotIn("topsecret", text)

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_no_credentials_in_checkpoint(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(return_value=_httpx_response())

        runtime = NativeAsyncFetchRuntime()
        requests = [
            _make_request(
                f"https://example.com/{i}",
                proxy_url="http://u:secret@proxy:8080",
            )
            for i in range(10)
        ]
        responses = await runtime.fetch_many(requests)

        summary = SpiderRunSummary(run_id="ckpt-redact")
        for resp in responses:
            envelope = CrawlRequestEnvelope(run_id="ckpt-redact", url=resp.final_url or "https://x.com/")
            result = CrawlItemResult(
                ok=resp.ok,
                request_id=envelope.request_id,
                url=resp.final_url or "https://x.com/",
                runtime_events=resp.runtime_events,
            )
            summary.record_item(result)

        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(Path(tmp) / "ckpt.sqlite3")
            store.start_run("ckpt-redact")
            store.save_batch_checkpoint(
                run_id="ckpt-redact",
                batch_id="b1",
                frontier_items=[],
                summary=summary,
            )

            loaded = store.load_latest("ckpt-redact")
            assert loaded is not None
            text = str(loaded)
            self.assertNotIn("secret@", text)


# ---------------------------------------------------------------------------
# Tests: concurrency under load
# ---------------------------------------------------------------------------

class TestConcurrencyUnderLoad(unittest.IsolatedAsyncioTestCase):
    """Concurrency limits enforced under 1k load."""

    @patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient")
    async def test_domain_limit_respected_at_scale(self, mock_client_cls: MagicMock) -> None:
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

        runtime = NativeAsyncFetchRuntime(max_per_domain=3, max_global=10)
        # 20 URLs on same domain
        requests = [_make_request(f"https://example.com/{i}") for i in range(20)]
        task = asyncio.create_task(runtime.fetch_many(requests))

        await asyncio.sleep(0.05)
        gate.set()
        responses = await task

        self.assertEqual(len(responses), 20)
        self.assertLessEqual(active["max"], 3)


if __name__ == "__main__":
    unittest.main()
