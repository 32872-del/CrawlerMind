"""Generic resumable batch runner.

The runner owns queue mechanics only: claim a bounded frontier batch, hand each
item to a processor, checkpoint successful records, and mark the frontier item
done or failed. It deliberately does not know about site-specific selectors or
scraping strategy.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..models.product import ProductRecord
from ..storage.frontier import URLFrontier
from ..storage.product_store import ProductStore


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

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id is required")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.max_batches < 0:
            raise ValueError("max_batches must be >= 0")
        if self.lease_seconds < 0:
            raise ValueError("lease_seconds must be >= 0")


@dataclass
class ItemProcessResult:
    """Result returned by a user-provided item processor."""

    ok: bool
    records: list[Any] = field(default_factory=list)
    discovered_urls: list[str] = field(default_factory=list)
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
        **metrics: Any,
    ) -> "ItemProcessResult":
        return cls(
            ok=True,
            records=list(records or []),
            discovered_urls=list(discovered_urls or []),
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
    item_errors: list[dict[str, Any]] = field(default_factory=list)
    frontier_stats: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "batches": self.batches,
            "claimed": self.claimed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "retried": self.retried,
            "records_saved": self.records_saved,
            "discovered_urls": self.discovered_urls,
            "checkpoint_errors": self.checkpoint_errors,
            "item_errors": self.item_errors,
            "frontier_stats": self.frontier_stats,
        }


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
    ) -> None:
        self.frontier = frontier
        self.processor = processor
        self.config = config
        self.checkpoint = checkpoint

    def run(self) -> BatchRunnerSummary:
        summary = BatchRunnerSummary(run_id=self.config.run_id)
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
            for item in batch:
                self._process_one(item, summary)

        summary.frontier_stats = self.frontier.stats()
        return summary

    def _process_one(self, item: FrontierItem, summary: BatchRunnerSummary) -> None:
        item_id = int(item["id"])
        try:
            result = self.processor(item)
        except Exception as exc:
            result = ItemProcessResult.failure(str(exc), retry=self.config.retry_failed)

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

            if result.discovered_urls:
                added = self.frontier.add_urls(
                    result.discovered_urls,
                    priority=result.discovered_priority,
                    kind=result.discovered_kind,
                    depth=int(item.get("depth", 0)) + 1,
                    parent_url=str(item.get("url", "")),
                    payload=item.get("payload") or {},
                )
                summary.discovered_urls += int(added.get("added", 0))

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
