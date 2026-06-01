from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

from autonomous_crawler.models.product import ProductRecord
from autonomous_crawler.runners.batch_runner import (
    BatchRunner,
    BatchRunnerConfig,
    ItemProcessResult,
    ProductRecordCheckpoint,
    RuleBasedBatchSupervisor,
)
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.storage.product_store import ProductStore


class FailingCheckpoint:
    def save_records(self, records: list[Any]) -> dict[str, int]:
        raise RuntimeError("checkpoint unavailable")


class BatchRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.frontier = URLFrontier(root / "frontier.sqlite3")
        self.product_store = ProductStore(root / "products.sqlite3")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_empty_frontier_returns_zero_summary(self) -> None:
        runner = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult.success(),
            config=BatchRunnerConfig(run_id="run-empty"),
        )

        summary = runner.run()

        self.assertEqual(summary.claimed, 0)
        self.assertEqual(summary.batches, 0)
        self.assertEqual(summary.frontier_stats, {})

    def test_successful_items_are_marked_done(self) -> None:
        self.frontier.add_urls(["https://example.test/a", "https://example.test/b"])
        seen: list[str] = []

        def processor(item: dict[str, Any]) -> ItemProcessResult:
            seen.append(item["url"])
            return ItemProcessResult.success()

        summary = BatchRunner(
            frontier=self.frontier,
            processor=processor,
            config=BatchRunnerConfig(run_id="run-ok", batch_size=1),
        ).run()

        self.assertEqual(summary.batches, 2)
        self.assertEqual(summary.claimed, 2)
        self.assertEqual(summary.succeeded, 2)
        self.assertEqual(self.frontier.stats(), {"done": 2})
        self.assertEqual(len(seen), 2)

    def test_failed_item_is_marked_failed(self) -> None:
        self.frontier.add_urls(["https://example.test/fail"])

        summary = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult.failure("boom"),
            config=BatchRunnerConfig(run_id="run-fail"),
        ).run()

        self.assertEqual(summary.failed, 1)
        self.assertEqual(summary.item_errors[0]["error"], "boom")
        self.assertEqual(self.frontier.stats(), {"failed": 1})

    def test_processor_exception_is_captured(self) -> None:
        self.frontier.add_urls(["https://example.test/raise"])

        def processor(item: dict[str, Any]) -> ItemProcessResult:
            raise ValueError("bad item")

        summary = BatchRunner(
            frontier=self.frontier,
            processor=processor,
            config=BatchRunnerConfig(run_id="run-exc"),
        ).run()

        self.assertEqual(summary.failed, 1)
        self.assertIn("bad item", summary.item_errors[0]["error"])
        self.assertEqual(self.frontier.stats(), {"failed": 1})

    def test_retry_failure_requeues_item(self) -> None:
        self.frontier.add_urls(["https://example.test/retry"])

        summary = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult.failure("temporary", retry=True),
            config=BatchRunnerConfig(run_id="run-retry", max_batches=1),
        ).run()

        self.assertEqual(summary.retried, 1)
        self.assertEqual(self.frontier.stats(), {"queued": 1})

    def test_max_batches_limits_run_for_resume(self) -> None:
        self.frontier.add_urls([
            "https://example.test/1",
            "https://example.test/2",
            "https://example.test/3",
        ])

        first = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult.success(),
            config=BatchRunnerConfig(run_id="run-resume", batch_size=1, max_batches=1),
        ).run()
        second = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult.success(),
            config=BatchRunnerConfig(run_id="run-resume", batch_size=10),
        ).run()

        self.assertEqual(first.succeeded, 1)
        self.assertEqual(second.succeeded, 2)
        self.assertEqual(self.frontier.stats(), {"done": 3})

    def test_item_workers_process_batch_concurrently(self) -> None:
        self.frontier.add_urls([
            "https://example.test/1",
            "https://example.test/2",
            "https://example.test/3",
            "https://example.test/4",
        ])

        def processor(item: dict[str, Any]) -> ItemProcessResult:
            time.sleep(0.05)
            return ItemProcessResult.success()

        started = time.perf_counter()
        summary = BatchRunner(
            frontier=self.frontier,
            processor=processor,
            config=BatchRunnerConfig(
                run_id="run-workers",
                batch_size=4,
                item_workers=4,
            ),
        ).run()
        elapsed = time.perf_counter() - started

        self.assertEqual(summary.succeeded, 4)
        self.assertLess(elapsed, 0.22)
        self.assertEqual(self.frontier.stats(), {"done": 4})

    def test_adaptive_item_workers_scale_up_on_healthy_batches(self) -> None:
        self.frontier.add_urls([f"https://example.test/{idx}" for idx in range(6)])

        summary = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult.success(records=[
                ProductRecord(
                    run_id="run-adaptive-up",
                    source_site="example.test",
                    source_url=item["url"],
                    canonical_url=item["url"],
                    title=f"Product {item['id']}",
                )
            ]),
            config=BatchRunnerConfig(
                run_id="run-adaptive-up",
                batch_size=2,
                item_workers=1,
                min_item_workers=1,
                max_item_workers=4,
            ),
            checkpoint=ProductRecordCheckpoint(self.product_store),
        ).run()

        self.assertEqual(summary.succeeded, 6)
        self.assertEqual(summary.worker_history[:3], [1, 2, 3])
        self.assertEqual(summary.batch_history[0]["workers"], 1)

    def test_adaptive_item_workers_scale_down_on_failed_batches(self) -> None:
        self.frontier.add_urls([f"https://example.test/{idx}" for idx in range(4)])

        summary = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult.failure("blocked"),
            config=BatchRunnerConfig(
                run_id="run-adaptive-down",
                batch_size=2,
                item_workers=3,
                min_item_workers=1,
                max_item_workers=3,
            ),
        ).run()

        self.assertEqual(summary.failed, 4)
        self.assertEqual(summary.worker_history[:2], [3, 2])

    def test_discovered_urls_are_added_to_frontier(self) -> None:
        self.frontier.add_urls(["https://example.test/list"])

        summary = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult(
                ok=True,
                discovered_urls=[
                    "https://example.test/detail/1",
                    "https://example.test/detail/2",
                    "not-a-url",
                ],
                discovered_kind="detail_page",
            ),
            config=BatchRunnerConfig(run_id="run-discovery", max_batches=1),
        ).run()

        self.assertEqual(summary.discovered_urls, 2)
        self.assertEqual(self.frontier.stats(), {"done": 1, "queued": 2})

    def test_product_checkpoint_saves_records(self) -> None:
        self.frontier.add_urls(["https://shop.example/products/a"])

        def processor(item: dict[str, Any]) -> ItemProcessResult:
            return ItemProcessResult.success(records=[
                ProductRecord(
                    run_id="run-products",
                    source_site="shop.example",
                    source_url=item["url"],
                    canonical_url=item["url"],
                    title="Alpha Product",
                    highest_price=12.5,
                    image_urls=["https://shop.example/a.jpg"],
                    category="training",
                )
            ])

        summary = BatchRunner(
            frontier=self.frontier,
            processor=processor,
            config=BatchRunnerConfig(run_id="run-products"),
            checkpoint=ProductRecordCheckpoint(self.product_store),
        ).run()

        self.assertEqual(summary.records_saved, 1)
        self.assertEqual(summary.succeeded, 1)
        self.assertEqual(self.product_store.count_total("run-products"), 1)
        self.assertEqual(self.frontier.stats(), {"done": 1})

    def test_checkpoint_failure_marks_item_failed(self) -> None:
        self.frontier.add_urls(["https://shop.example/products/a"])

        summary = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult.success(records=[object()]),
            config=BatchRunnerConfig(run_id="run-checkpoint-fail"),
            checkpoint=FailingCheckpoint(),
        ).run()

        self.assertEqual(summary.checkpoint_errors, 1)
        self.assertEqual(summary.failed, 1)
        self.assertEqual(self.frontier.stats(), {"failed": 1})

    def test_config_validation(self) -> None:
        with self.assertRaises(ValueError):
            BatchRunnerConfig(run_id="")
        with self.assertRaises(ValueError):
            BatchRunnerConfig(run_id="x", batch_size=0)
        with self.assertRaises(ValueError):
            BatchRunnerConfig(run_id="x", max_batches=-1)
        with self.assertRaises(ValueError):
            BatchRunnerConfig(run_id="x", lease_seconds=-1)
        with self.assertRaises(ValueError):
            BatchRunnerConfig(run_id="x", item_workers=0)

    def test_rule_based_supervisor_records_repair_warning_on_empty_batch(self) -> None:
        self.frontier.add_urls(["https://example.test/list"])

        summary = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult.success(),
            config=BatchRunnerConfig(run_id="run-supervise", max_batches=1),
            supervisor=RuleBasedBatchSupervisor(),
        ).run()

        self.assertEqual(summary.status, "completed")
        self.assertEqual(len(summary.supervision_events), 1)
        self.assertEqual(summary.supervision_events[0]["action"], "repair_after_run")
        self.assertIn("snapshot", summary.supervision_events[0])

    def test_rule_based_supervisor_pauses_after_consecutive_empty_batches(self) -> None:
        self.frontier.add_urls(["https://example.test/1", "https://example.test/2", "https://example.test/3"])

        summary = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult.success(),
            config=BatchRunnerConfig(run_id="run-supervise-pause", batch_size=1),
            supervisor=RuleBasedBatchSupervisor(zero_record_batches_before_pause=2),
        ).run()

        self.assertEqual(summary.status, "paused")
        self.assertEqual(len(summary.supervision_events), 2)
        self.assertEqual(summary.supervision_events[-1]["action"], "pause")
        self.assertEqual(self.frontier.stats(), {"done": 2, "queued": 1})

    def test_rule_based_supervisor_aborts_on_high_failure_rate(self) -> None:
        self.frontier.add_urls(["https://example.test/1", "https://example.test/2"])

        summary = BatchRunner(
            frontier=self.frontier,
            processor=lambda item: ItemProcessResult.failure("blocked"),
            config=BatchRunnerConfig(run_id="run-supervise-abort", batch_size=2),
            supervisor=RuleBasedBatchSupervisor(failure_rate_abort=0.5),
        ).run()

        self.assertEqual(summary.status, "aborted")
        self.assertEqual(summary.supervision_events[-1]["action"], "abort")


if __name__ == "__main__":
    unittest.main()
