from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_crawler.runners import CrawlItemResult, CrawlRequestEnvelope, SpiderRunSummary, make_spider_event
from autonomous_crawler.storage.checkpoint_store import CheckpointStore


class CheckpointStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CheckpointStore(Path(self.tmp.name) / "checkpoints.sqlite3")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_start_run_is_idempotent_and_load_latest_without_checkpoint(self) -> None:
        self.store.start_run("run-1", {"site": "example"})
        self.store.start_run("run-1", {"site": "example", "mode": "resume"})

        latest = self.store.load_latest("run-1")

        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["run"]["status"], "running")
        self.assertEqual(latest["run"]["config"], {"site": "example", "mode": "resume"})
        self.assertIsNone(latest["latest_checkpoint"])

    def test_save_batch_checkpoint_and_load_latest(self) -> None:
        self.store.start_run("run-batch", {"goal": "products"})
        summary = SpiderRunSummary(run_id="run-batch", status="running")
        summary.batches = 2
        summary.claimed = 10
        event = make_spider_event("batch_claimed", "batch claimed", size=5)

        self.store.save_batch_checkpoint(
            run_id="run-batch",
            batch_id="batch-002",
            frontier_items=[{"id": 1, "url": "https://example.com/a"}],
            summary=summary,
            events=[event],
        )

        latest = self.store.load_latest("run-batch")

        self.assertIsNotNone(latest)
        assert latest is not None
        checkpoint = latest["latest_checkpoint"]
        self.assertEqual(checkpoint["batch_id"], "batch-002")
        self.assertEqual(checkpoint["summary"]["claimed"], 10)
        self.assertEqual(checkpoint["frontier_items"][0]["url"], "https://example.com/a")
        self.assertEqual(checkpoint["events"][0]["type"], "spider.batch_claimed")

    def test_save_item_checkpoint_persists_records_events_and_failures(self) -> None:
        request = CrawlRequestEnvelope(run_id="run-items", url="https://example.com/product")
        ok_result = CrawlItemResult.success(
            request,
            status_code=200,
            records=[{
                "record_type": "product",
                "title": "Alpha",
                "dedupe_key": "alpha",
            }],
            runtime_events=[make_spider_event("request_succeeded", "ok")],
        )
        failed_result = CrawlItemResult.failure(
            request,
            error="proxy=http://user:pass@proxy.example:8080 failed",
            status_code=429,
            retry=True,
            failure_bucket="rate_limited",
            runtime_events=[make_spider_event("request_retried", "retry")],
        )

        self.store.save_item_checkpoint(run_id="run-items", request=request, result=ok_result)
        self.store.save_item_checkpoint(run_id="run-items", request=request, result=failed_result)

        latest = self.store.load_latest("run-items")
        failures = self.store.list_failures("run-items")
        rate_limited = self.store.list_failures("run-items", bucket="rate_limited")
        items = self.store.list_items("run-items")

        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["item_count"], 1)
        self.assertEqual(latest["failure_count"], 1)
        self.assertEqual(len(failures), 1)
        self.assertEqual(len(rate_limited), 1)
        self.assertTrue(rate_limited[0]["retryable"])
        self.assertNotIn("pass", rate_limited[0]["error"])
        self.assertEqual(items[0]["record_type"], "product")
        self.assertEqual(items[0]["record"]["title"], "Alpha")
        self.assertEqual(items[0]["dedupe_key"], "alpha")

    def test_save_failure_auto_starts_run_and_filters_bucket(self) -> None:
        request = CrawlRequestEnvelope(
            run_id="run-auto",
            url="https://example.com/blocked",
            retry_count=2,
        )

        self.store.save_failure(
            run_id="run-auto",
            request=request,
            bucket="http_blocked",
            error="status 403",
            retryable=False,
        )

        latest = self.store.load_latest("run-auto")
        failures = self.store.list_failures("run-auto", bucket="http_blocked")

        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["run"]["status"], "running")
        self.assertEqual(latest["failure_count"], 1)
        self.assertEqual(failures[0]["attempts"], 2)

    def test_mark_paused_and_completed(self) -> None:
        self.store.start_run("run-state", {})

        self.store.mark_paused("run-state", "operator pause")
        paused = self.store.load_latest("run-state")
        self.store.mark_completed("run-state")
        completed = self.store.load_latest("run-state")

        self.assertIsNotNone(paused)
        self.assertIsNotNone(completed)
        assert paused is not None
        assert completed is not None
        self.assertEqual(paused["run"]["status"], "paused")
        self.assertEqual(paused["run"]["pause_reason"], "operator pause")
        self.assertEqual(completed["run"]["status"], "completed")
        self.assertTrue(completed["run"]["completed_at"])

    def test_validation_requires_run_id(self) -> None:
        with self.assertRaises(ValueError):
            self.store.start_run("", {})
        with self.assertRaises(ValueError):
            self.store.load_latest("")


if __name__ == "__main__":
    unittest.main()
