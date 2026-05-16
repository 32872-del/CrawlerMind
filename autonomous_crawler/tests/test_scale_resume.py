"""Tests for SCALE-HARDEN-2: Resumable Checkpoint Restart.

Uses small fixtures (200 URLs) for fast default tests. 30k runs are in the
script runner (run_scale_resume_2026_05_15.py).
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from autonomous_crawler.runtime.native_async import NativeAsyncFetchRuntime
from autonomous_crawler.runtime.models import RuntimeRequest
from autonomous_crawler.runners.spider_models import (
    CrawlItemResult,
    CrawlRequestEnvelope,
    SpiderRunSummary,
)
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from run_scale_resume_2026_05_15 import combine_summaries


def _httpx_response(status_code: int = 200, url: str = "https://example.com/") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.url = url
    resp.headers = {"Content-Type": "text/html"}
    resp.cookies = {}
    resp.content = b"<html>OK</html>"
    resp.text = "<html>OK</html>"
    resp.http_version = "HTTP/2"
    return resp


def _make_urls(n: int, num_domains: int = 5) -> list[str]:
    domains = [f"domain{i}.example.com" for i in range(num_domains)]
    return [f"https://{domains[i % num_domains]}/page/{i}" for i in range(n)]


class TestResumableCheckpointRestart(unittest.TestCase):
    """Resumable checkpoint restart with small fixtures."""

    def _run_resume(self, total: int, pause_at: int) -> dict:
        """Run a resume scenario and return results."""

        async def _inner():
            with tempfile.TemporaryDirectory() as tmp:
                store = CheckpointStore(Path(tmp) / "test_resume.sqlite3")
                run_id = f"test-resume-{total}"
                store.start_run(run_id)

                all_urls = _make_urls(total)
                pool_provider = MagicMock()
                pool_provider.select.return_value = MagicMock(proxy_url="http://proxy:9090")
                pool_provider.report_result = MagicMock()
                health_store = MagicMock()

                with patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient") as mock_cls:
                    client = mock_cls.return_value.__aenter__.return_value
                    client.request = AsyncMock(return_value=_httpx_response())
                    runtime = NativeAsyncFetchRuntime(max_per_domain=2, max_global=8)

                    # Phase 1
                    summary1 = SpiderRunSummary(run_id=run_id, status="running")
                    reqs1 = [RuntimeRequest(url=u, proxy_config={
                        "proxy": "http://p:p@proxy:8080",
                        "pool_provider": pool_provider,
                        "health_store": health_store,
                    }) for u in all_urls[:pause_at]]

                    resps1 = await runtime.fetch_many(reqs1)
                    for resp in resps1:
                        env = CrawlRequestEnvelope(run_id=run_id, url=resp.final_url or "https://x.com/")
                        result = CrawlItemResult(ok=resp.ok, request_id=env.request_id,
                                                url=resp.final_url or "https://x.com/",
                                                status_code=resp.status_code,
                                                runtime_events=resp.runtime_events)
                        summary1.record_item(result)

                    store.save_batch_checkpoint(
                        run_id=run_id, batch_id="phase1",
                        frontier_items=[{"url": u} for u in all_urls[pause_at:]],
                        summary=summary1,
                    )
                    store.mark_paused(run_id, reason="test_pause")

                    # Phase 2: Resume
                    loaded = store.load_latest(run_id)
                    ckpt = loaded["latest_checkpoint"]["summary"]
                    remaining = [item["url"] for item in loaded["latest_checkpoint"]["frontier_items"]]

                    store.start_run(run_id)
                    summary2 = SpiderRunSummary(run_id=run_id, status="running")
                    reqs2 = [RuntimeRequest(url=u, proxy_config={
                        "proxy": "http://p:p@proxy:8080",
                        "pool_provider": pool_provider,
                        "health_store": health_store,
                    }) for u in remaining]

                    resps2 = await runtime.fetch_many(reqs2)
                    for resp in resps2:
                        env = CrawlRequestEnvelope(run_id=run_id, url=resp.final_url or "https://x.com/")
                        result = CrawlItemResult(ok=resp.ok, request_id=env.request_id,
                                                url=resp.final_url or "https://x.com/",
                                                status_code=resp.status_code,
                                                runtime_events=resp.runtime_events)
                        summary2.record_item(result)

                    store.save_batch_checkpoint(
                        run_id=run_id, batch_id="phase2",
                        frontier_items=[], summary=combine_summaries(run_id, summary1, summary2),
                    )
                    store.mark_completed(run_id)

                    final = store.load_latest(run_id)
                    final_ckpt = final["latest_checkpoint"]["summary"] if final and final["latest_checkpoint"] else {}

                    return {
                        "total": total,
                        "phase1_succeeded": summary1.succeeded,
                        "phase2_succeeded": summary2.succeeded,
                        "total_succeeded": summary1.succeeded + summary2.succeeded,
                        "loaded_status": loaded["run"]["status"],
                        "final_status": final["run"]["status"],
                        "ckpt_succeeded": final_ckpt.get("succeeded"),
                        "remaining_urls": len(remaining),
                    }

        return asyncio.run(_inner())

    def test_resume_basic(self) -> None:
        """200 URLs, pause at 120, resume remaining 80."""
        r = self._run_resume(200, 120)
        self.assertEqual(r["total"], 200)
        self.assertEqual(r["phase1_succeeded"], 120)
        self.assertEqual(r["phase2_succeeded"], 80)
        self.assertEqual(r["total_succeeded"], 200)
        self.assertEqual(r["loaded_status"], "paused")
        self.assertEqual(r["final_status"], "completed")

    def test_resume_at_boundary(self) -> None:
        """Pause at exact midpoint."""
        r = self._run_resume(100, 50)
        self.assertEqual(r["phase1_succeeded"], 50)
        self.assertEqual(r["phase2_succeeded"], 50)
        self.assertEqual(r["total_succeeded"], 100)

    def test_resume_no_remaining(self) -> None:
        """Pause at end — nothing to resume."""
        r = self._run_resume(50, 50)
        self.assertEqual(r["total_succeeded"], 50)

    def test_checkpoint_roundtrip(self) -> None:
        """Checkpoint summary fields roundtrip correctly — final checkpoint has totals."""
        r = self._run_resume(200, 100)
        self.assertEqual(r["total_succeeded"], 200)
        self.assertEqual(r["ckpt_succeeded"], r["total_succeeded"])

    def test_combine_summaries_keeps_final_totals(self) -> None:
        first = SpiderRunSummary(run_id="combined", status="running")
        first.succeeded = 120
        first.failed = 3
        first.proxy_attempts_total = 130
        first.async_fetch_ok = 120
        first.response_status_count = {"200": 120, "503": 3}
        first.max_concurrency_per_domain = {"a.example": 2}
        second = SpiderRunSummary(run_id="combined", status="running")
        second.succeeded = 80
        second.failed = 1
        second.proxy_attempts_total = 90
        second.async_fetch_ok = 80
        second.response_status_count = {"200": 80, "503": 1}
        second.max_concurrency_per_domain = {"a.example": 3, "b.example": 1}

        combined = combine_summaries("combined", first, second)

        self.assertEqual(combined.status, "completed")
        self.assertEqual(combined.succeeded, 200)
        self.assertEqual(combined.failed, 4)
        self.assertEqual(combined.proxy_attempts_total, 220)
        self.assertEqual(combined.async_fetch_ok, 200)
        self.assertEqual(combined.response_status_count, {"200": 200, "503": 4})
        self.assertEqual(combined.max_concurrency_per_domain, {"a.example": 3, "b.example": 1})


class TestResumableWithFailures(unittest.TestCase):
    """Resume with simulated failures (5% rate)."""

    def test_resume_with_failures(self) -> None:
        async def _inner():
            async def _fail(*args, **kwargs):
                raise ConnectionError("persistent_glitch")

            with tempfile.TemporaryDirectory() as tmp:
                store = CheckpointStore(Path(tmp) / "fail_resume.sqlite3")
                run_id = "fail-resume"
                store.start_run(run_id)
                all_urls = _make_urls(200)
                pool_provider = MagicMock()
                pool_provider.select.return_value = MagicMock(proxy_url="http://proxy:9090")
                pool_provider.report_result = MagicMock()
                health_store = MagicMock()

                with patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient") as mock_cls:
                    client = mock_cls.return_value.__aenter__.return_value
                    client.request = AsyncMock(side_effect=_fail)
                    runtime = NativeAsyncFetchRuntime(max_per_domain=2, max_global=8)

                    # Phase 1: 120 URLs
                    summary1 = SpiderRunSummary(run_id=run_id, status="running")
                    reqs1 = [RuntimeRequest(url=u, proxy_config={
                        "proxy": "http://p:p@proxy:8080",
                        "retry_on_proxy_failure": True, "max_proxy_attempts": 2,
                        "pool_provider": pool_provider, "health_store": health_store,
                    }) for u in all_urls[:120]]
                    resps1 = await runtime.fetch_many(reqs1)
                    for resp in resps1:
                        env = CrawlRequestEnvelope(run_id=run_id, url=resp.final_url or "https://x.com/")
                        result = CrawlItemResult(ok=resp.ok, request_id=env.request_id,
                                                url=resp.final_url or "https://x.com/",
                                                status_code=resp.status_code,
                                                runtime_events=resp.runtime_events)
                        summary1.record_item(result)

                    store.save_batch_checkpoint(
                        run_id=run_id, batch_id="phase1",
                        frontier_items=[{"url": u} for u in all_urls[120:]],
                        summary=summary1,
                    )
                    store.mark_paused(run_id)

                    # Phase 2: Resume remaining 80
                    loaded = store.load_latest(run_id)
                    remaining = [item["url"] for item in loaded["latest_checkpoint"]["frontier_items"]]
                    store.start_run(run_id)
                    summary2 = SpiderRunSummary(run_id=run_id, status="running")
                    reqs2 = [RuntimeRequest(url=u, proxy_config={
                        "proxy": "http://p:p@proxy:8080",
                        "retry_on_proxy_failure": True, "max_proxy_attempts": 2,
                        "pool_provider": pool_provider, "health_store": health_store,
                    }) for u in remaining]
                    resps2 = await runtime.fetch_many(reqs2)
                    for resp in resps2:
                        env = CrawlRequestEnvelope(run_id=run_id, url=resp.final_url or "https://x.com/")
                        result = CrawlItemResult(ok=resp.ok, request_id=env.request_id,
                                                url=resp.final_url or "https://x.com/",
                                                status_code=resp.status_code,
                                                runtime_events=resp.runtime_events)
                        summary2.record_item(result)

                    store.save_batch_checkpoint(
                        run_id=run_id, batch_id="phase2",
                        frontier_items=[], summary=summary2,
                    )
                    store.mark_completed(run_id)

                    final = store.load_latest(run_id)
                    final_ckpt = final["latest_checkpoint"]["summary"]

                    total_succeeded = summary1.succeeded + summary2.succeeded
                    total_failed = summary1.failed + summary2.failed

                    return {
                        "total_succeeded": total_succeeded,
                        "total_failed": total_failed,
                        "total_processed": total_succeeded + total_failed,
                        "ckpt_succeeded": final_ckpt.get("succeeded"),
                        "ckpt_failed": final_ckpt.get("failed"),
                    }

        r = asyncio.run(_inner())
        self.assertEqual(r["total_processed"], 200)
        self.assertGreater(r["total_failed"], 0)
        self.assertEqual(r["total_failed"], 200)  # all fail (persistent glitch)


class TestCheckpointStoreResume(unittest.TestCase):
    """Unit tests for CheckpointStore resume capabilities."""

    def test_pause_and_resume_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(Path(tmp) / "status.sqlite3")
            store.start_run("run-1")
            store.mark_paused("run-1", reason="test")
            loaded = store.load_latest("run-1")
            self.assertEqual(loaded["run"]["status"], "paused")
            self.assertEqual(loaded["run"]["pause_reason"], "test")

            store.start_run("run-1")  # resume
            loaded = store.load_latest("run-1")
            self.assertEqual(loaded["run"]["status"], "running")

    def test_frontier_items_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(Path(tmp) / "frontier.sqlite3")
            store.start_run("run-2")
            summary = SpiderRunSummary(run_id="run-2", status="running")
            store.save_batch_checkpoint(
                run_id="run-2", batch_id="b1",
                frontier_items=[{"url": "https://a.com"}, {"url": "https://b.com"}],
                summary=summary,
            )
            loaded = store.load_latest("run-2")
            frontier = loaded["latest_checkpoint"]["frontier_items"]
            self.assertEqual(len(frontier), 2)
            self.assertEqual(frontier[0]["url"], "https://a.com")


if __name__ == "__main__":
    unittest.main()
