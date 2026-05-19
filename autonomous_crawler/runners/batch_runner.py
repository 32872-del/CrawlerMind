"""Generic resumable batch runner.

The runner owns queue mechanics only: claim a bounded frontier batch, hand each
item to a processor, checkpoint successful records, and mark the frontier item
done or failed. It deliberately does not know about site-specific selectors or
scraping strategy.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..models.product import ProductRecord
from ..storage.frontier import URLFrontier
from ..storage.product_store import ProductStore
from .backpressure import BackpressureMonitor


FrontierItem = dict[str, Any]
ItemProcessor = Callable[[FrontierItem], "ItemProcessResult"]


class CheckpointSink(Protocol):
    """Persist records produced by a runner item."""

    def save_records(self, records: list[Any]) -> dict[str, int]:
        ...


@dataclass(frozen=True)
class BatchRunnerConfig:
    run_id: str
    worker_id: str = "batch-runner"
    batch_size: int = 20
    max_batches: int = 0
    lease_seconds: int = 300
    retry_failed: bool = False
    item_workers: int = 1

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id is required")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.max_batches < 0:
            raise ValueError("max_batches must be >= 0")
        if self.lease_seconds < 0:
            raise ValueError("lease_seconds must be >= 0")
        if self.item_workers < 1:
            raise ValueError("item_workers must be >= 1")


@dataclass
class ItemProcessResult:
    """Result returned by a user-provided item processor."""

    ok: bool
    records: list[Any] = field(default_factory=list)
    discovered_urls: list[str] = field(default_factory=list)
    discovered_requests: list[Any] = field(default_factory=list)
    discovered_kind: str = "page"
    discovered_priority: int = 0
    error: str = ""
    retry: bool = False
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(
        cls,
        records: Iterable[Any] | None = None,
        discovered_urls: Iterable[str] | None = None,
        discovered_requests: Iterable[Any] | None = None,
        **metrics: Any,
    ) -> "ItemProcessResult":
        return cls(
            ok=True,
            records=list(records or []),
            discovered_urls=list(discovered_urls or []),
            discovered_requests=list(discovered_requests or []),
            metrics=dict(metrics),
        )

    @classmethod
    def failure(cls, error: str, retry: bool = False, **metrics: Any) -> "ItemProcessResult":
        return cls(ok=False, error=error, retry=retry, metrics=dict(metrics))


@dataclass
class BatchRunnerSummary:
    run_id: str
    batches: int = 0
    claimed: int = 0
    succeeded: int = 0
    failed: int = 0
    retried: int = 0
    records_saved: int = 0
    discovered_urls: int = 0
    checkpoint_errors: int = 0
    status: str = "completed"
    item_errors: list[dict[str, Any]] = field(default_factory=list)
    frontier_stats: dict[str, int] = field(default_factory=dict)
    backpressure: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        result = {
            "run_id": self.run_id,
            "batches": self.batches,
            "claimed": self.claimed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "retried": self.retried,
            "records_saved": self.records_saved,
            "discovered_urls": self.discovered_urls,
            "checkpoint_errors": self.checkpoint_errors,
            "status": self.status,
            "item_errors": self.item_errors,
            "frontier_stats": self.frontier_stats,
        }
        if self.backpressure is not None:
            result["backpressure"] = self.backpressure
        return result


class ProductRecordCheckpoint:
    """Checkpoint sink for ProductRecord batches.

    This adapter keeps ecommerce storage outside the generic runner. Other
    domains can provide their own sink with the same save_records method.
    """

    def __init__(self, store: ProductStore) -> None:
        self.store = store

    def save_records(self, records: list[Any]) -> dict[str, int]:
        product_records = [record for record in records if isinstance(record, ProductRecord)]
        if not product_records:
            return {"inserted": 0, "updated": 0, "total": 0}
        return self.store.upsert_many(product_records)


class BatchRunner:
    """Run bounded, resumable work from a URLFrontier."""

    def __init__(
        self,
        frontier: URLFrontier,
        processor: ItemProcessor,
        config: BatchRunnerConfig,
        checkpoint: CheckpointSink | None = None,
        backpressure: BackpressureMonitor | None = None,
    ) -> None:
        self.frontier = frontier
        self.processor = processor
        self.config = config
        self.checkpoint = checkpoint
        self.backpressure = backpressure

    def run(self) -> BatchRunnerSummary:
        summary = BatchRunnerSummary(run_id=self.config.run_id)
        workers = max(1, int(self.config.item_workers))
        while True:
            if self.config.max_batches and summary.batches >= self.config.max_batches:
                break

            batch = self.frontier.next_batch(
                limit=self.config.batch_size,
                worker_id=self.config.worker_id,
                lease_seconds=self.config.lease_seconds,
            )
            if not batch:
                break

            summary.batches += 1
            summary.claimed += len(batch)

            # Track per-batch metrics for backpressure
            batch_succeeded_before = summary.succeeded
            batch_failed_before = summary.failed
            batch_retried_before = summary.retried
            batch_ckpt_errors_before = summary.checkpoint_errors

            timer = self.backpressure.time_batch() if self.backpressure else None
            if timer:
                timer.__enter__()
            try:
                if workers == 1 or len(batch) == 1:
                    for item in batch:
                        processed_item, result = self._process_item(item)
                        self._apply_result(processed_item, result, summary)
                else:
                    with ThreadPoolExecutor(max_workers=min(workers, len(batch))) as executor:
                        futures = [executor.submit(self._process_item, item) for item in batch]
                        for future in as_completed(futures):
                            processed_item, result = future.result()
                            self._apply_result(processed_item, result, summary)
            finally:
                if timer:
                    timer.claimed = len(batch)
                    timer.succeeded = summary.succeeded - batch_succeeded_before
                    timer.failed = summary.failed - batch_failed_before
                    timer.retried = summary.retried - batch_retried_before
                    timer.checkpoint_errors = summary.checkpoint_errors - batch_ckpt_errors_before
                    timer.__exit__(None, None, None)

            if self.backpressure:
                signals = self.backpressure.current_signals()
                if signals.recommendation == "abort":
                    summary.status = "aborted"
                    break
                if signals.recommendation == "pause":
                    summary.status = "paused"
                    break

        summary.frontier_stats = self.frontier.stats()
        if self.backpressure:
            summary.backpressure = self.backpressure.current_signals().as_dict()
        return summary

    def _process_one(self, item: FrontierItem, summary: BatchRunnerSummary) -> None:
        """Process and persist one item.

        Kept for compatibility with tests/extensions that may call the helper
        directly. The main runner uses `_process_item` + `_apply_result` so
        expensive runtime work can happen in parallel while SQLite writes stay
        serialized.
        """
        processed_item, result = self._process_item(item)
        self._apply_result(processed_item, result, summary)

    def _process_item(self, item: FrontierItem) -> tuple[FrontierItem, ItemProcessResult]:
        try:
            return item, self.processor(item)
        except Exception as exc:
            return item, ItemProcessResult.failure(str(exc), retry=self.config.retry_failed)

    def _apply_result(
        self,
        item: FrontierItem,
        result: ItemProcessResult,
        summary: BatchRunnerSummary,
    ) -> None:
        item_id = int(item["id"])

        if result.ok:
            if result.records and self.checkpoint:
                try:
                    saved = self.checkpoint.save_records(result.records)
                    summary.records_saved += int(saved.get("total", 0))
                except Exception as exc:
                    summary.checkpoint_errors += 1
                    summary.failed += 1
                    summary.item_errors.append({"id": item_id, "url": item.get("url"), "error": str(exc)})
                    self.frontier.mark_failed([item_id], error=f"checkpoint failed: {exc}", retry=False)
                    return

            summary.discovered_urls += self._enqueue_discovered(item, result)

            self.frontier.mark_done([item_id])
            summary.succeeded += 1
            return

        retry = bool(result.retry or self.config.retry_failed)
        self.frontier.mark_failed([item_id], error=result.error, retry=retry)
        if retry:
            summary.retried += 1
        else:
            summary.failed += 1
        summary.item_errors.append({"id": item_id, "url": item.get("url"), "error": result.error})

    def _enqueue_discovered(self, item: FrontierItem, result: ItemProcessResult) -> int:
        added_total = 0
        if result.discovered_requests:
            for request in result.discovered_requests:
                url = str(getattr(request, "url", "") or "")
                if not url:
                    continue
                payload = _payload_from_discovered_request(request)
                added = self.frontier.add_urls(
                    [url],
                    priority=int(getattr(request, "priority", result.discovered_priority) or 0),
                    kind=str(getattr(request, "kind", result.discovered_kind) or "page"),
                    depth=int(getattr(request, "depth", int(item.get("depth", 0)) + 1) or 0),
                    parent_url=str(getattr(request, "parent_url", str(item.get("url", ""))) or ""),
                    payload=payload,
                )
                added_total += int(added.get("added", 0))
            return added_total

        if result.discovered_urls:
            added = self.frontier.add_urls(
                result.discovered_urls,
                priority=result.discovered_priority,
                kind=result.discovered_kind,
                depth=int(item.get("depth", 0)) + 1,
                parent_url=str(item.get("url", "")),
                payload=item.get("payload") or {},
            )
            return int(added.get("added", 0))

        return 0


def _payload_from_discovered_request(request: Any) -> dict[str, Any]:
    if hasattr(request, "to_safe_dict"):
        data = dict(request.to_safe_dict())
    else:
        data = {
            "request_id": getattr(request, "request_id", ""),
            "method": getattr(request, "method", "GET"),
            "priority": getattr(request, "priority", 0),
            "kind": getattr(request, "kind", "page"),
            "depth": getattr(request, "depth", 0),
            "parent_url": getattr(request, "parent_url", ""),
            "session_id": getattr(request, "session_id", ""),
            "session_profile_id": getattr(request, "session_profile_id", ""),
            "headers": dict(getattr(request, "headers", {}) or {}),
            "cookies": dict(getattr(request, "cookies", {}) or {}),
            "params": dict(getattr(request, "params", {}) or {}),
            "data": getattr(request, "data", None),
            "json": getattr(request, "json", None),
            "meta": dict(getattr(request, "meta", {}) or {}),
            "dont_filter": bool(getattr(request, "dont_filter", False)),
            "retry_count": int(getattr(request, "retry_count", 0) or 0),
            "max_retries": int(getattr(request, "max_retries", 3) or 3),
            "fingerprint": getattr(request, "fingerprint", ""),
        }
    data.pop("canonical_url", None)
    data.pop("url", None)
    return data
